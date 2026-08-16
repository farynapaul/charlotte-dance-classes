"""
Sync recurring public classes from Punchpass-hosted studio calendars into the
Firestore `events` collection.

Each Punchpass org publishes an ICS feed with one VEVENT per individual class
occurrence (not RRULE-based), so this script groups occurrences by weekday +
start time (+ location, for studios where the feed's LOCATION field is a real
address rather than a room label) to detect recurring weekly classes. It
skips kids/team/private/social entries and upserts using a deterministic
document ID, so re-running it updates existing entries instead of duplicating
them — even as Punchpass series IDs change every semester.

Usage:
    python sync_punchpass_studios.py --dry-run [studio_key ...]
    python sync_punchpass_studios.py --write <path-to-service-account-key.json> [studio_key ...]

With no studio_key args, all configured studios are processed.
"""
import argparse
import hashlib
import re
from collections import defaultdict

import icalendar
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) charlottedanceclasses.com-sync-script"}
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
    ("body movement", "salsa"),
]

DAY_ABBR = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}

STUDIOS = {
    "rumbao": {
        "ics_url": "https://rumbaolatindance.punchpass.com/org/18723/calendars/all_classes.ics",
        "site_link": "https://www.rumbaolatindance.com/",
        "use_feed_location_as_venue": True,
    },
    "rwlatindance": {
        "ics_url": "https://rwlatindance.punchpass.com/org/15814/calendars/all_classes.ics",
        "site_link": "https://rwlatindance.com/",
        "use_feed_location_as_venue": False,
        "fixed_venue": "The Dance Loft, 756 Tyvola Rd Suite 734",
    },
}


def detect_styles(summaries):
    styles = []
    text = " ".join(summaries).lower()
    for keyword, style in STYLE_KEYWORDS:
        if keyword in text and style not in styles:
            styles.append(style)
    return styles


def clean_venue(location):
    return re.sub(r"\s+", " ", location).strip()


def build_name(summaries, styles):
    text = " ".join(summaries).lower()
    if "body movement" in text:
        return "Body Movement (Salsa Styling)"
    if "zouk" in text:
        return "Brazilian Zouk"
    if "salsa saturdays" in text:
        return "Salsa Saturdays (Drop-In)"
    if "tango" in text:
        return "Argentine Tango Drop-In"
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
    return "Class"


def make_doc_id(studio_key, day, time_str, venue):
    slug = re.sub(r"[^a-z0-9]+", "-", f"{studio_key}-{day}-{time_str}-{venue}".lower()).strip("-")
    h = hashlib.sha1(slug.encode()).hexdigest()[:8]
    return f"{slug[:80]}-{h}"


def fetch_and_group(studio_key, config):
    resp = requests.get(config["ics_url"], headers=HEADERS, timeout=30)
    resp.raise_for_status()
    cal = icalendar.Calendar.from_ical(resp.content)

    groups = defaultdict(list)
    for comp in cal.walk("VEVENT"):
        summary = str(comp.get("SUMMARY", ""))
        lower = summary.lower()
        if any(kw in lower for kw in EXCLUDE_KEYWORDS):
            continue

        dtstart = comp.get("DTSTART").dt
        day = DAY_ABBR[dtstart.weekday()]
        time_str = dtstart.strftime("%I:%M %p").lstrip("0")

        if config["use_feed_location_as_venue"]:
            venue = clean_venue(str(comp.get("LOCATION", "")))
            key = (day, time_str, venue)
        else:
            venue = config["fixed_venue"]
            key = (day, time_str)

        groups[key].append((summary, venue))

    recurring = {}
    for key, entries in groups.items():
        if len(entries) < MIN_OCCURRENCES:
            continue
        summaries = [e[0] for e in entries]
        venue = entries[0][1]
        day, time_str = key[0], key[1]
        styles = detect_styles(summaries)
        if not styles:
            continue
        name = build_name(summaries, styles)
        doc_id = make_doc_id(studio_key, day, time_str, venue)
        recurring[doc_id] = {
            "name": name,
            "styles": styles,
            "day": day,
            "type": "recurring",
            "time": time_str,
            "venue": venue,
            "link": config["site_link"],
            "status": "approved",
            "_occurrences": len(entries),
            "_sample_summaries": sorted(set(summaries))[:3],
        }

    return recurring


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", metavar="KEY_JSON", help="Upsert to Firestore using this service account key")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written, without writing")
    parser.add_argument("studios", nargs="*", help="Studio keys to process (default: all)")
    args = parser.parse_args()

    if not args.write and not args.dry_run:
        args.dry_run = True

    keys = args.studios or list(STUDIOS.keys())

    db = None
    if args.write:
        from google.cloud import firestore
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(args.write)
        db = firestore.Client(credentials=credentials, project=credentials.project_id)

    for studio_key in keys:
        config = STUDIOS[studio_key]
        recurring = fetch_and_group(studio_key, config)

        print(f"=== {studio_key}: found {len(recurring)} recurring public classes ===\n")
        for doc_id, ev in sorted(recurring.items(), key=lambda kv: (kv[1]["day"], kv[1]["time"])):
            print(f"  [{doc_id}]")
            print(f"    {ev['day']} {ev['time']} | {ev['name']} | styles={ev['styles']}")
            print(f"    venue: {ev['venue']}")
            print(f"    seen {ev['_occurrences']}x, e.g. {ev['_sample_summaries']}")
            print()

        if db:
            collection = db.collection("events")
            for doc_id, ev in recurring.items():
                data = {k: v for k, v in ev.items() if not k.startswith("_")}
                collection.document(doc_id).set(data)
            print(f"Upserted {len(recurring)} events for {studio_key}.\n")

    if not db:
        print("Dry run only -- nothing written. Re-run with --write <key.json> to upsert.")


if __name__ == "__main__":
    main()
