// All calls to the FastAPI backend live here so components stay UI-only.
const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function get(path, params) {
  const url = new URL(BASE + path);
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const fetchEvents = () => get("/api/events").then((d) => d.events);
export const fetchTrend = (event) => get("/api/events/trend", { event });
export const fetchSwimmers = (gender) => get("/api/swimmers", gender ? { gender } : undefined).then((d) => d.swimmers);
export const fetchSwimmerTrend = (name, gender) => get("/api/swimmers/trend", gender ? { name, gender } : { name });
export const fetchMeta = () => get("/api/meta");
export const fetchAnalysisEvent = (kind, event) => get(`/api/analysis/${kind}`, { event });
export const fetchReaction = (gender) => get("/api/analysis/reaction", gender ? { gender } : undefined);
// Prelims -> finals comparisons: kind in {time-drop, rank-movement, pacing}.
export const fetchCompare = (kind, event) => get(`/api/compare/${kind}`, { event });
// Whole-meet prelim->final scatter (all events, one gender).
export const fetchMeetDrop = (gender) => get("/api/compare/meet-drop", gender ? { gender } : undefined);
// Head-to-head matchup: roster for the pickers, then two chosen swims.
export const fetchRoster = (event) => get("/api/events/roster", { event }).then((d) => d.swimmers);
export const fetchMatchup = (event, a, b) =>
  get("/api/matchup", {
    event,
    aName: a.name, aYear: a.year, aSection: a.section,
    bName: b.name, bYear: b.year, bSection: b.section,
  });

// Seed-adjusted prelim->final step-up: seed curve, programs, classes, years.
export const fetchStepUp = (gender, minN) =>
  get("/api/stepup", { ...(gender ? { gender } : {}), ...(minN ? { min_n: minN } : {}) });
export const fetchStepUpSwims = (gender, school) =>
  get("/api/stepup/swims", { ...(gender ? { gender } : {}), ...(school ? { school } : {}) });
// Scoring share by class year per season (the COVID 5th-year bubble).
export const fetchClassShare = (gender) =>
  get("/api/cohort/class-share", gender ? { gender } : undefined);

// Condense chart labels
export const shortEvent = (name) =>
  name.replace(/^(Men|Women)\s+/, "").replace(/\s+Yard\s+/, " ");

// Seconds -> "m:ss.xx" (or "ss.xx" for sub-minute swims), for axis + tooltips
export function formatTime(sec) {
  if (sec == null) return "";
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return m > 0 ? `${m}:${s.toFixed(2).padStart(5, "0")}` : s.toFixed(2);
}
