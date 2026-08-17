"""
One-time backfill: sets a `priority` field on every event doc in Firestore.

Default priority is 50. Events organized by "Momentum" -- identified by a
name that starts with "Momentum:", the existing convention for their listings
(see BACKLOG.md) -- get priority 20, so they sort after everything else
without being filtered out or hidden. Higher numbers sort first; a future
"featured" tier could use 80 or 100 without any other code changing, since
calendar.js's sort just reads this field directly.

Usage:
    python backfill_priority.py <path-to-service-account-key.json>
"""
import sys
from pathlib import Path

from google.cloud import firestore
from google.oauth2 import service_account

DEFAULT_PRIORITY = 50
MOMENTUM_PRIORITY = 20

def main():
    if len(sys.argv) != 2:
        print("Usage: python backfill_priority.py <path-to-service-account-key.json>")
        sys.exit(1)

    key_path = Path(sys.argv[1])
    credentials = service_account.Credentials.from_service_account_file(str(key_path))
    db = firestore.Client(credentials=credentials, project=credentials.project_id)

    collection = db.collection("events")
    docs = list(collection.stream())

    for doc in docs:
        data = doc.to_dict()
        name = (data.get("name") or "").strip()
        priority = MOMENTUM_PRIORITY if name.startswith("Momentum:") else DEFAULT_PRIORITY
        doc.reference.update({"priority": priority})
        print(f"{priority:>3}  {name}")

    print(f"\nDone. Set priority on {len(docs)} events in '{credentials.project_id}'.")

if __name__ == "__main__":
    main()
