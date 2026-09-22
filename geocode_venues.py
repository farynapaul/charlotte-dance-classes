"""
Build venues.json: a lookup table from the exact `venue` string on each event
doc to that venue's coordinates, so calendar.js can compute distance without
touching the event data itself.

Geocodes via Nominatim (OpenStreetMap's free search API -- no key, no billing
account needed, unlike Google's Geocoding API). Respects Nominatim's usage
policy of 1 request/second.

A handful of venues have no street address in our data (e.g. "Dynamic
Ballroom, Cornelius") and won't resolve automatically -- those print a
warning and are left out of venues.json; fix them by hand afterward using
the HAND_OVERRIDES dict below (or by editing venues.json directly), then
re-run to fill in the rest.

Usage:
    python geocode_venues.py <path-to-service-account-key.json>
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "charlottedanceclasses.com-venue-geocoder (contact: farynapaul@gmail.com)"}

# Matches a street address starting at the first "<number> <word>" -- lets us strip a
# leading business name (e.g. "Viva Collective Studios 901 N Tryon Street 28206"),
# since Nominatim's free-text search reliably matches addresses but gets confused by an
# arbitrary business name glued onto one with no separator.
ADDRESS_START = re.compile(r"\d+\s+[A-Za-z]")
# Suite/unit numbers, which Nominatim can't resolve to a distinct point anyway --
# building-level precision is all we need for a distance sort.
SUITE = re.compile(r"\b(?:suite|ste\.?|#)\s*\w+\b", re.IGNORECASE)

def build_queries(venue):
    """Yields address-only, then business-name-only, query strings to try in order."""
    m = ADDRESS_START.search(venue)
    if m:
        address = SUITE.sub("", venue[m.start():]).strip(" ,")
        if "," not in address:
            # no city already in the string (e.g. "12210 Copper Way") -- assume Charlotte.
            # If a city IS already present (e.g. "...Blvd, Pineville"), leave it alone --
            # appending ", Charlotte, NC" after a different city breaks the match.
            address += ", Charlotte, NC"
        yield address
    yield venue  # fall back to the raw string as a business/POI name search

# Venues Nominatim can't resolve from the venue string alone (no street
# address in our data) -- looked up by hand. Add entries here as they come up.
HAND_OVERRIDES = {
    # No usable street address in the venue string itself -- real address found via web
    # search and geocoded separately.
    "Dynamic Ballroom, Cornelius": {"lat": 35.4786, "lng": -80.8878, "address": "19625 Bethel Church Rd, Cornelius, NC"},
    "King David Christian Conservatory": {"lat": 35.1419, "lng": -80.7318, "address": "2200 Coronation Blvd, Charlotte, NC 28227"},
    "Levine Senior Center, Matthews": {"lat": 35.1292, "lng": -80.6960, "address": "1050 DeVore Lane, Matthews, NC 28105"},
    "The Long Room, Plaza Midwood": {"lat": 35.2217, "lng": -80.8189, "address": "1111 Central Avenue, Charlotte, NC 28204"},
    # Has a real address, but the trailing unit letter ("...Blvd b,") breaks Nominatim's
    # free-text matching -- geocoded manually with the unit letter dropped.
    "Vista Events, 5028 South Blvd b, Charlotte, NC": {"lat": 35.1684, "lng": -80.8767, "address": "5028 South Blvd, Charlotte, NC"},
}

# Not a real place -- always excluded.
SKIP = {"See Meetup for location"}

def geocode(query):
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1, "countrycodes": "us"},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    return {"lat": float(results[0]["lat"]), "lng": float(results[0]["lon"])}

def main():
    if len(sys.argv) != 2:
        print("Usage: python geocode_venues.py <path-to-service-account-key.json>")
        sys.exit(1)

    from google.cloud import firestore
    from google.oauth2 import service_account

    key_path = Path(sys.argv[1])
    credentials = service_account.Credentials.from_service_account_file(str(key_path))
    db = firestore.Client(credentials=credentials, project=credentials.project_id)

    docs = list(db.collection("events").stream())
    venues = sorted(set((d.to_dict().get("venue") or "").strip() for d in docs) - SKIP - {""})
    print(f"{len(venues)} unique venues to geocode\n")

    out_path = Path(__file__).parent / "venues.json"
    existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}

    result = dict(existing)
    unresolved = []

    for venue in venues:
        if venue in HAND_OVERRIDES:
            result[venue] = HAND_OVERRIDES[venue]
            print(f"  [hand]  {venue}")
            continue
        if venue in result:
            print(f"  [cached] {venue}")
            continue

        coords = None
        for query in build_queries(venue):
            coords = geocode(query)
            if coords is not None:
                break
            time.sleep(1)
        if coords is None:
            unresolved.append(venue)
            print(f"  [FAIL]  {venue}")
        else:
            result[venue] = {**coords, "address": venue}
            print(f"  [ok]    {venue} -> {coords['lat']:.4f}, {coords['lng']:.4f}")
        time.sleep(1)  # Nominatim usage policy: max 1 req/sec

    out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nWrote {len(result)} venues to {out_path}")

    if unresolved:
        print(f"\n{len(unresolved)} venue(s) need a manual fix -- add to HAND_OVERRIDES and re-run:")
        for v in unresolved:
            print(f"  - {v!r}")

if __name__ == "__main__":
    main()
