import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getFirestore, collection, query, where, getDocs } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { firebaseConfig } from "./firebase-config.js";

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

const STUDIO_STYLES = ["hiphop", "ballet", "tap", "jazz", "musicaltheater", "more"];

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
