# Charlotte Dance Classes

A public calendar (`index.html`), a submission form (`submit.html`), and a moderation queue (`admin.html`). No build step — plain HTML/JS, deploys as-is.

## 1. Create a Firebase project (free)

1. Go to https://console.firebase.google.com → **Add project** → name it (e.g. "charlotte-dance-classes") → skip Google Analytics if you don't want it.
2. In the left sidebar: **Build → Firestore Database → Create database** → start in **production mode** → pick a region close to you (e.g. `us-east1`).
3. In the left sidebar: **Build → Authentication → Get started → Sign-in method → Email/Password → Enable**.
4. Still in Authentication, go to the **Users** tab → **Add user** → create yourself as the one admin login (this is what you'll use to sign into `admin.html`).
5. Go to **Project settings** (gear icon) → **General** → scroll to **Your apps** → click the `</>` (web) icon → register the app (nickname doesn't matter, skip hosting) → copy the `firebaseConfig` object it gives you.
6. Paste those values into `firebase-config.js` in this folder, replacing the placeholders.

## 2. Set Firestore security rules

In Firebase Console → **Firestore Database → Rules**, replace the default rules with:

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /events/{eventId} {
      // anyone can read approved events
      allow read: if resource.data.status == "approved";
      // anyone can submit a new event, but it must start as "pending"
      allow create: if request.resource.data.status == "pending";
      // only a signed-in admin can approve/reject/edit
      allow update, delete: if request.auth != null;
    }
  }
}
```

This is what makes the whole thing safe to leave open: the public can submit, but nothing shows on the calendar until you approve it from `admin.html`, and only a signed-in user (you) can approve or delete.

## 3. Seed some starting events

Easiest way: open `admin.html` isn't needed for this — just add documents directly.

In Firebase Console → **Firestore Database → Start collection** → name it `events`. Add a few documents by hand using the fields in `seed-events.json` as a reference, or ask Claude Code to write a one-off script that reads `seed-events.json` and pushes it into Firestore using the Firebase Admin SDK.

## 4. Run it locally

Any static server works, e.g.:

```
npx serve .
```

Then open the printed localhost URL.

## 5. Deploy

Push this folder to a GitHub repo, then connect it in **Vercel** or **Netlify** (both free tiers, both auto-deploy on every push):

- Vercel: https://vercel.com/new → import the repo → framework preset "Other" → deploy.
- Netlify: https://app.netlify.com → "Add new site" → import the repo → no build command needed → deploy.

## 6. Connect CharlotteDanceClasses.com

In Vercel/Netlify project settings → **Domains** → add `charlottedanceclasses.com` → it'll give you DNS records (usually an A record and/or CNAME) → add those in Namecheap under **Domain List → Manage → Advanced DNS**. SSL is issued automatically, no action needed.

## Files

- `index.html` — public calendar, filterable by style and day
- `submit.html` — public event submission form (writes to Firestore as `status: "pending"`)
- `admin.html` — sign in with the admin account you created in step 1.4 to approve or reject pending submissions
- `firebase-config.js` — your Firebase project keys go here
- `seed-events.json` — starting events from Rumbao, RW Latin Dance, and CLTDance to get the calendar populated
