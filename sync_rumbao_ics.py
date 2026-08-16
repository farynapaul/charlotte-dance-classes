"""
Sync recurring public classes from Rumbao Latin Dance's Punchpass ICS feed
into the Firestore `events` collection.

The feed lists one VEVENT per individual class occurrence (not RRULE-based),
so this script groups occurrences by (weekday, start time, location) to
detect recurring weekly classes, skips kids/team/private/social entries,
and upserts using a deterministic document ID (derived from the studio +
day + time + location) so re-running this script updates existing entries
instead of duplicating them, even as Punchpass series IDs change every
semester.

Usage:
    python sync_rumbao_ics.py --dry-run
    python sync_rumbao_ics.py --write <path-to-service-account-key.json>
"""
import argparse
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

import icalendar
import requests

ICS_URL = "https://rumbaolatindance.punchpass.com/org/18723/calendars/all_classes.ics"
SITE_LINK = "https://www.rumbaolatindance.com/"
MIN_OCCURRENCES = 4  # occurrences needed across the feed's date range to count as "recurring"

EXCLUDE_KEYWORDS = [
    "kids", "teen", "little movers", "team", "performance challenge",
    "performance team", "canceled", "cancelled", "reservation",
    "open house", "social",
]

STYLE_KEYWORDS = [
    ("zouk", "zouk"),
    ("bachata", "bachata"),
    ("kizomba", "kizomba"),
    ("tango", "tango"),
    ("swing", "swing"),
    ("rueda", "salsa"),
    ("casino", "salsa"),
    ("casineros", "salsa"),
    ("salsa", "salsa"),
    ("body movement", "salsa"),  # general styling class; Rumbao is primarily a salsa/bachata school
]

DAY_ABBR = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}


def detect_styles(summaries):
    styles = []
    text = " ".join(summaries).lower()
    for keyword, style in STYLE_KEYWORDS:
        if keyword in text and style not in styles:
            styles.append(style)
    return styles


def clean_venue(location):
    # Feed locations look like "Camp North End YVY Studio 1701 North Graham Street"
    return re.sub(r"\s+", " ", location).strip()


def build_name(summaries, styles):
    text = " ".join(summaries).lower()
    if "body movement" in text:
        return "Body Movement (Salsa Styling)"
    if "zouk" in text:
        return "Brazilian Zouk"
    if "salsa saturdays" in text:
        return "Salsa Saturdays (Drop-In)"
    if ("rueda" in text or "casino" in text or "casineros" in text) and "bachata" not in text:
        return "Salsa Rueda / Casino"
    if "on2" in text or "on 2" in text:
        if "bachata" in styles and "salsa" not in styles:
            return "Bachata Classes"
        return "Salsa On2 Classes"
    if "bachata" in styles and "salsa" not in styles:
        return "Bachata Classes"
    if "salsa" in styles and "bachata" not in styles:
        return "Salsa Classes"
    if styles:
        return " / ".join(s.capitalize() for s in styles) + " Classes"
    return "Rumbao Class"


def make_doc_id(day, time_str, venue):
    slug = re.sub(r"[^a-z0-9]+", "-", f"rumbao-{day}-{time_str}-{venue}".lower()).strip("-")
    # keep IDs a sane length; hash suffix guards against collisions from truncation
    h = hashlib.sha1(slug.encode()).hexdigest()[:8]
    return f"{slug[:80]}-{h}"


def fetch_and_group():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) charlottedanceclasses.com-sync-script"}
    resp = requests.get(ICS_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    cal = icalendar.Calendar.from_ical(resp.content)

    groups = defaultdict(list)
    skipped_no_style = []

    for comp in cal.walk("VEVENT"):
        summary = str(comp.get("SUMMARY", ""))
        lower = summary.lower()
        if any(kw in lower for kw in EXCLUDE_KEYWORDS):
            continue

        dtstart = comp.get("DTSTART").dt
        location = clean_venue(str(comp.get("LOCATION", "")))
        day = DAY_ABBR[dtstart.weekday()]
        time_str = dtstart.strftime("%I:%M %p").lstrip("0")

        key = (day, time_str, location)
        groups[key].append(summary)

    recurring = {}
    for (day, time_str, location), summaries in groups.items():
        if len(summaries) < MIN_OCCURRENCES:
            continue
        styles = detect_styles(summaries)
        if not styles:
            skipped_no_style.append((day, time_str, location, summaries[0]))
            continue
        name = build_name(summaries, styles)
        doc_id = make_doc_id(day, time_str, location)
        recurring[doc_id] = {
            "name": name,
            "styles": styles,
            "day": day,
            "type": "recurring",
            "time": time_str,
            "venue": location,
            "link": SITE_LINK,
            "status": "approved",
            "_occurrences": len(summaries),
            "_sample_summaries": sorted(set(summaries))[:3],
        }

    return recurring, skipped_no_style


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", metavar="KEY_JSON", help="Upsert to Firestore using this service account key")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written, without writing")
    args = parser.parse_args()

    if not args.write and not args.dry_run:
        args.dry_run = True

    recurring, skipped = fetch_and_group()

    print(f"Found {len(recurring)} recurring public classes:\n")
    for doc_id, ev in sorted(recurring.items(), key=lambda kv: (kv[1]["day"], kv[1]["time"])):
        print(f"  [{doc_id}]")
        print(f"    {ev['day']} {ev['time']} | {ev['name']} | styles={ev['styles']}")
        print(f"    venue: {ev['venue']}")
        print(f"    seen {ev['_occurrences']}x, e.g. {ev['_sample_summaries']}")
        print()

    if skipped:
        print(f"Skipped {len(skipped)} recurring-looking groups with no recognized dance style keyword:")
        for day, time_str, location, sample in skipped:
            print(f"  {day} {time_str} | {location} | e.g. \"{sample}\"")
        print()

    if args.write:
        from google.cloud import firestore
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(args.write)
        db = firestore.Client(credentials=credentials, project=credentials.project_id)
        collection = db.collection("events")

        for doc_id, ev in recurring.items():
            data = {k: v for k, v in ev.items() if not k.startswith("_")}
            collection.document(doc_id).set(data)
        print(f"Upserted {len(recurring)} events into Firestore (project: {credentials.project_id}).")
    else:
        print("Dry run only — nothing written. Re-run with --write <key.json> to upsert.")


if __name__ == "__main__":
    main()
