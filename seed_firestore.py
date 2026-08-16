"""
One-off script: load seed-events.json into the Firestore `events` collection.

Usage:
    python seed_firestore.py <path-to-service-account-key.json>

Uses the Firebase Admin credentials to bypass security rules (the seed data
is marked status: "approved", which the public client SDK isn't allowed to write).
"""
import json
import sys
from pathlib import Path

from google.cloud import firestore
from google.oauth2 import service_account

def main():
    if len(sys.argv) != 2:
        print("Usage: python seed_firestore.py <path-to-service-account-key.json>")
        sys.exit(1)

    key_path = Path(sys.argv[1])
    events_path = Path(__file__).parent / "seed-events.json"

    credentials = service_account.Credentials.from_service_account_file(str(key_path))
    db = firestore.Client(credentials=credentials, project=credentials.project_id)

    events = json.loads(events_path.read_text(encoding="utf-8"))

    collection = db.collection("events")
    for event in events:
        doc_ref = collection.document()
        doc_ref.set(event)
        print(f"Added: {event['name']} ({doc_ref.id})")

    print(f"\nDone. Seeded {len(events)} events into '{credentials.project_id}'.")

if __name__ == "__main__":
    main()
