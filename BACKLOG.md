# Research backlog

Studios/leads investigated but not yet added, kept here so they survive between sessions.

## Open leads

- **Steps N Motion Dance Studio** — real studio (The Fountains @ 8183 Ardrey Kell Rd, plus Wesley Chapel and Indian Land locations). Teaches Ballet, Hip Hop, Jazz, Tap, Contemporary. Schedule sits behind a Jackrabbit parent-portal login on stepsnmotion.com — couldn't extract via fetch or public pages. Would need either a login, a call to the studio, or another public schedule source. Re-checked 2026-09-22, still no public schedule. Phone: Fountains 704-845-1180, Wesley Chapel 704-684-0005, Indian Land 803-228-0679.

- **Charlotte Dance Alliance** (dancingcda.com, formerly "Fancy Feet Dance Studio" under Paula Mann — same studio, not two separate leads) — real, established studio (32+ years), Ballet/Tap/Jazz/Hip Hop/Lyrical/Contemporary/Acro, ages 18mo-adult. Site has "Class Schedule" links per category (Recreational, Hip Hop, Floor Gymnastics, Specialty, Competition) but they don't resolve to any visible day/time content -- likely broken or JS-gated. No public schedule found. Phone: (704) 847-7138.

- **BB Dance Productions** (3721 Atmore Street, Charlotte, NC 28205) — real studio since 1991, Ballet/Tap/Jazz/Gym/Lyrical/Hip Hop, ages 2-high school. No public schedule on bbdance.com or via the ActivityHero third-party listing (which advertised "2026 Schedules" but didn't actually expose one, at least not without JS/login). Phone: (704) 563-8693.

- **Noche De Sabor** (Rumbao's dance-lesson-and-social night, Midtown Ballroom, Fri ~8PM) — shows up roughly monthly in Rumbao's ICS feed, not weekly, so it doesn't fit the site's current weekly-recurring display model. User wants to revisit "how to show monthly events" as a separate design question before adding this (or anything like it).

## Explicitly out of scope (per user direction, 2026-08-16)

Ballroom dance styles/studios — "attracts a very different demographic." Confirmed and excluded:
- Arthur Murray Charlotte (8700 Pineville-Matthews Rd) — lead-gen site, no public schedule anyway
- Arthur Murray Cornelius
- Dance Center USA — actually based in Fort Mill, SC; stale web presence (calendar last updated 2023)
- Midtown Ballroom (7631 Sharon Lakes Rd)
- Fred Astaire Charlotte (2 locations) + Fred Astaire Lake Norman
- Creative Dancesport
- Metropolitan Ballroom
- T.C. Dance Club International

## Resolved (skip, don't re-investigate)

- **Yoyo's Salon & Events** — appears to be a stale/old RW Latin Dance address, different from the venue their live ICS feed reports (The Dance Loft). Adding it risked duplicating/conflicting with the already-accurate synced data.
- **Dancers Unite Fine Arts Academy** (Dilworth) — confirmed CLOSED, Yelp listing updated January 2026 explicitly marks it "CLOSED." Don't re-check again barring some new signal it reopened.
- **Queen City Zouk** — defunct, folded into Crown Zouk (see above).
- **GottaSwing Charlotte** — resolved, added (see git log). The trick was using gottaswingcharlotte.com directly, not the national gottaswing.com franchise site.
- **Crown Zouk / "Momentum"** — resolved, added (see git log). Real name is "Momentum Dance Project" (@momentumdanceproject on Instagram), Tue nights at Vista Events, 5028 South Blvd b, Charlotte — Bachata Beginner 7-8PM, Bachata Intermediate 8-9PM, Zouk (class + practice) 9-10:30PM. User supplied a flyer screenshot with the schedule.
