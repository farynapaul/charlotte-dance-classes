import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { initializeAppCheck, ReCaptchaV3Provider } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-check.js";
import { getFirestore, collection, query, where, getDocs } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { firebaseConfig, recaptchaSiteKey } from "./firebase-config.js";

const app = initializeApp(firebaseConfig);
initializeAppCheck(app, {
  provider: new ReCaptchaV3Provider(recaptchaSiteKey),
  isTokenAutoRefreshEnabled: true,
});
const db = getFirestore(app);

const STUDIO_STYLES = ["hiphop", "ballet", "tap", "jazz", "musicaltheater", "more"];

const SITE_URL = "https://charlottedanceclasses.com/";
const DAY_INDEX = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };

function injectOrganizationJsonLd(){
  if(document.getElementById("ld-organization")) return;
  const data = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": "Charlotte Dance Classes",
    "url": SITE_URL,
    "description": "A live calendar of salsa, bachata, zouk, kizomba, tango, swing, hip hop, ballet, tap, jazz and musical theater classes and socials across Charlotte, NC."
  };
  const script = document.createElement("script");
  script.type = "application/ld+json";
  script.id = "ld-organization";
  script.textContent = JSON.stringify(data);
  document.head.appendChild(script);
}

function easternNowParts(){
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
    weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false
  });
  const parts = {};
  fmt.formatToParts(new Date()).forEach(p => { if(p.type !== "literal") parts[p.type] = p.value; });
  return parts;
}

function easternUtcOffsetHours(){
  const fmt = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", timeZoneName: "shortOffset" });
  const part = fmt.formatToParts(new Date()).find(p => p.type === "timeZoneName").value; // e.g. "GMT-4"
  const match = part.match(/GMT([+-]\d+)/);
  return match ? parseInt(match[1], 10) : -5;
}

// Pulls the first "H:MM AM/PM" out of a free-text time field like
// "7:00 PM class, practica to 11 PM" -- a best-effort lead time, not the full session window.
function parseLeadTime(timeStr){
  const m = (timeStr || "").match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
  if(!m) return null;
  let hour = parseInt(m[1], 10) % 12;
  if(/PM/i.test(m[3])) hour += 12;
  return { hour, minute: parseInt(m[2], 10) };
}

// Events here only carry a day-of-week + free-text time, never an absolute calendar
// date, so "startDate" is always the nearest upcoming occurrence in America/New_York --
// not a literal one-time date, even for type:"oneoff" entries.
function nextOccurrenceISO(day, timeStr){
  const time = parseLeadTime(timeStr);
  if(!time || !(day in DAY_INDEX)) return null;

  const now = easternNowParts();
  const todayIdx = DAY_INDEX[now.weekday];
  const targetIdx = DAY_INDEX[day];
  let daysAhead = (targetIdx - todayIdx + 7) % 7;
  const nowMinutes = parseInt(now.hour, 10) * 60 + parseInt(now.minute, 10);
  const targetMinutes = time.hour * 60 + time.minute;
  if(daysAhead === 0 && targetMinutes <= nowMinutes) daysAhead = 7;

  const baseUTC = Date.UTC(parseInt(now.year, 10), parseInt(now.month, 10) - 1, parseInt(now.day, 10));
  const target = new Date(baseUTC + daysAhead * 86400000);
  const y = target.getUTCFullYear();
  const mo = String(target.getUTCMonth() + 1).padStart(2, "0");
  const d = String(target.getUTCDate()).padStart(2, "0");
  const hh = String(time.hour).padStart(2, "0");
  const mm = String(time.minute).padStart(2, "0");
  const offset = easternUtcOffsetHours();
  const offsetStr = (offset <= 0 ? "-" : "+") + String(Math.abs(offset)).padStart(2, "0") + ":00";
  return `${y}-${mo}-${d}T${hh}:${mm}:00${offsetStr}`;
}

// Google's Event rich result doesn't support schema.org's eventSchedule/Schedule for
// recurring events -- it wants a discrete Event per occurrence. We don't have future
// occurrence dates, so we emit one Event per class using its nearest upcoming date.
function eventToJsonLd(ev){
  const startDate = nextOccurrenceISO(ev.day, ev.time);
  if(!startDate) return null; // no parseable time -- skip rather than fabricate one

  const venue = (ev.venue || "").trim();
  const location = { "@type": "Place", "name": venue || "Charlotte, NC" };
  if(venue.includes(",")) location.address = venue;

  const entry = {
    "@context": "https://schema.org",
    "@type": "Event",
    "name": ev.name || "",
    "startDate": startDate,
    "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
    "eventStatus": "https://schema.org/EventScheduled",
    "location": location,
    "description": `${(ev.styles || []).join(", ")} ${ev.type === "recurring" ? "class" : "event"} in Charlotte, NC.`.trim()
  };
  if(ev.link) entry.url = ev.link;
  return entry;
}

// Rebuilds the events JSON-LD block from exactly what render() just put on the page,
// so filtered-out events never linger in stale schema.
function injectEventJsonLd(events){
  const existing = document.getElementById("ld-events");
  if(existing) existing.remove();

  const items = events.map(eventToJsonLd).filter(Boolean);
  if(items.length === 0) return;

  const script = document.createElement("script");
  script.type = "application/ld+json";
  script.id = "ld-events";
  script.textContent = JSON.stringify(items.length === 1 ? items[0] : items);
  document.head.appendChild(script);
}

// Pages set <body data-default-style="tango"> etc. to land pre-filtered; index.html omits it (defaults to "all").
const defaultStyle = document.body.dataset.defaultStyle || "all";

let activeType = STUDIO_STYLES.includes(defaultStyle) ? "studio" : "social";
let activeStyle = defaultStyle;
let activeDay = "all";
let activeAudience = "adult";
let allEvents = [];

// Style pages are separate page loads (not a SPA), so every chip click is a full
// navigation. Caching the fetched events in sessionStorage means hopping between
// salsa.html -> bachata.html -> tango.html only hits Firestore once per session
// (or every CACHE_TTL_MS, whichever comes first), instead of refetching on every click.
const CACHE_KEY = "cdc_events_cache_v1";
const CACHE_TTL_MS = 15 * 60 * 1000; // 15 minutes

function readEventsCache(){
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if(!raw) return null;
    const { savedAt, events } = JSON.parse(raw);
    if(!Array.isArray(events) || Date.now() - savedAt > CACHE_TTL_MS) return null;
    return events;
  } catch(e){
    return null;
  }
}
function writeEventsCache(events){
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), events }));
  } catch(e){
    // sessionStorage unavailable (private browsing, quota) -- fine, just skip caching
  }
}

async function loadEvents(){
  const cached = readEventsCache();
  if(cached){
    allEvents = cached;
    render();
    return;
  }

  const q = query(collection(db, "events"), where("status", "==", "approved"));
  const snap = await getDocs(q);
  allEvents = [];
  snap.forEach(doc => allEvents.push({ id: doc.id, ...doc.data() }));
  // sensible default order: day of week, then time
  const dayOrder = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
  allEvents.sort((a,b)=>{
    const da = dayOrder.indexOf(a.day), db_ = dayOrder.indexOf(b.day);
    if(da !== db_) return da - db_;
    return (a.time || "").localeCompare(b.time || "");
  });
  writeEventsCache(allEvents);
  render();
}

function render(){
  const list = document.getElementById("event-list");
  const filtered = allEvents.filter(ev => {
    const isStudio = (ev.styles || []).some(s => STUDIO_STYLES.includes(s));
    const typeMatch = activeType === "studio" ? isStudio : !isStudio;
    const styleMatch = activeStyle === "all" || (ev.styles || []).includes(activeStyle);
    const dayMatch = activeDay === "all" || ev.day === activeDay;
    const audienceMatch = activeAudience === "kids" ? ev.audience === "kids" : ev.audience !== "kids";
    return typeMatch && styleMatch && dayMatch && audienceMatch;
  });

  injectEventJsonLd(filtered);

  if(filtered.length === 0){
    list.innerHTML = `<div class="empty">Nothing matches yet — try a different filter, or <a href="submit.html">add an event</a> if you know of one.</div>`;
    return;
  }

  list.innerHTML = filtered.map(ev => `
    <div class="event">
      <div class="event-time">${ev.day || ""}<br>${ev.time || ""}</div>
      <div>
        <p class="event-name">${escapeHtml(ev.name || "")}</p>
        <p class="event-meta">${escapeHtml(ev.venue || "")}${ev.type === "recurring" ? " · Recurring" : " · One-time"}</p>
        <div class="event-tags">
          ${(ev.styles||[]).map(s => `<span class="tag style-${s}">${s}</span>`).join("")}
        </div>
      </div>
      ${ev.link ? `<a class="event-link" href="${escapeAttr(ev.link)}" target="_blank" rel="noopener">Details</a>` : "<span></span>"}
    </div>
  `).join("");
}

function escapeHtml(str){
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}
function escapeAttr(str){
  return String(str).replace(/"/g,"&quot;");
}

// Reflects activeType/activeStyle onto the chip UI. Called on init and after any
// filter change, so dedicated pages (data-default-style) and click handlers share
// one source of truth instead of duplicating "which chip is active" logic.
function syncTypeUI(){
  document.querySelectorAll("#type-filters .chip").forEach(b => b.classList.toggle("active", b.dataset.type === activeType));
  const socialGroup = document.getElementById("social-style-filters");
  const studioGroup = document.getElementById("studio-style-filters");
  if(socialGroup) socialGroup.style.display = activeType === "social" ? "" : "none";
  if(studioGroup) studioGroup.style.display = activeType === "studio" ? "" : "none";
}
function syncStyleUI(){
  document.querySelectorAll("#social-style-filters .chip, #studio-style-filters .chip").forEach(b => {
    b.classList.toggle("active", b.dataset.style === activeStyle);
  });
}

syncTypeUI();
syncStyleUI();
injectOrganizationJsonLd();

// Every style chip is a real <a href="..."> to that style's dedicated page (or
// index.html for "All styles"), so the browser navigates natively -- no JS needed.
// The lone exception is "More Dances" (a <button>, no dedicated page for the
// catch-all), which still filters in place like the day/audience/type controls.
function onStyleFilterClick(e){
  const btn = e.target.closest(".chip");
  if(!btn || btn.tagName !== "BUTTON") return;
  activeStyle = btn.dataset.style;
  syncStyleUI();
  render();
}
document.getElementById("social-style-filters").addEventListener("click", onStyleFilterClick);
document.getElementById("studio-style-filters").addEventListener("click", onStyleFilterClick);

document.getElementById("type-filters").addEventListener("click", e => {
  const btn = e.target.closest(".chip");
  if(!btn) return;
  activeType = btn.dataset.type;
  activeStyle = "all";
  syncTypeUI();
  syncStyleUI();
  render();
});

document.getElementById("audience-filters").addEventListener("click", e => {
  const btn = e.target.closest(".chip");
  if(!btn) return;
  document.querySelectorAll("#audience-filters .chip").forEach(b=>b.classList.remove("active"));
  btn.classList.add("active");
  activeAudience = btn.dataset.audience;
  render();
});

document.getElementById("day-nav").addEventListener("click", e => {
  const btn = e.target.closest("button");
  if(!btn) return;
  document.querySelectorAll("#day-nav button").forEach(b=>b.classList.remove("active"));
  btn.classList.add("active");
  activeDay = btn.dataset.day;
  render();
});

loadEvents().catch(err => {
  document.getElementById("event-list").innerHTML =
    `<div class="empty">Couldn't load events. Check the Firebase config in firebase-config.js.<br><small>${err.message}</small></div>`;
  console.error(err);
});
