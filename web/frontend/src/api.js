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
export const fetchSwimmers = () => get("/api/swimmers").then((d) => d.swimmers);
export const fetchSwimmerTrend = (name) => get("/api/swimmers/trend", { name });

// "Men 200 Yard Backstroke" -> "200 Backstroke" for compact chart labels.
export const shortEvent = (name) =>
  name.replace(/^(Men|Women)\s+/, "").replace(/\s+Yard\s+/, " ");

// Seconds -> "m:ss.xx" (or "ss.xx" for sub-minute swims), for axis + tooltips.
export function formatTime(sec) {
  if (sec == null) return "";
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return m > 0 ? `${m}:${s.toFixed(2).padStart(5, "0")}` : s.toFixed(2);
}
