import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { fetchSwimmers, fetchSwimmerTrend, formatTime, shortEvent } from "./api";
import SwimmerSearch from "./SwimmerSearch";

const FINAL_COLOR = "#DC143C";
const PRELIM_COLOR = "#4169E1";
const GOOD = "#11A046";
const BAD = "#DC143C";

const TIP = {
  background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
  boxShadow: "0 4px 14px rgba(16,24,40,.12)", padding: "8px 10px",
  fontSize: 12, minWidth: 150, fontVariantNumeric: "tabular-nums",
};

// A signed in-meet drop (prelim - final) in seconds: +0.90s faster in the final.
const fmtDrop = (v) =>
  v == null ? "—" : `${v > 0 ? "−" : v < 0 ? "+" : ""}${Math.abs(v).toFixed(2)}s`;

// Swimmer trends: pick a swimmer, then one event at a time. Prelim and final are
// drawn as two lines; click any swim (a table cell or chart point) for its splits.
export default function SwimmerTrends({ gender }) {
  // The loaded list is stored WITH the gender it belongs to. Both effects below
  // re-run when gender flips, and the trend effect would otherwise fire first
  // with the previous gender's swimmer still in state — asking the API for a
  // men's swimmer under Women, which 404s. Pairing the list with its gender
  // gives the trend effect a way to tell "not loaded yet" from "ready".
  const [list, setList] = useState({ gender: null, swimmers: [] });
  const [name, setName] = useState(null);
  const [trend, setTrend] = useState(null);
  const [error, setError] = useState(null);

  const [eventName, setEventName] = useState(null);
  const [swim, setSwim] = useState(null); // selected swim object for the detail panel

  const swimmers = list.gender === gender ? list.swimmers : [];

  // Reload the swimmer list when gender changes, and pick a busy default swimmer.
  useEffect(() => {
    let cancelled = false;
    setName(null); setTrend(null);
    setList({ gender: null, swimmers: [] });
    fetchSwimmers(gender)
      .then((sw) => {
        if (cancelled) return; // a faster gender flip already superseded this
        setList({ gender, swimmers: sw });
        const featured = [...sw].sort((a, b) => b.years - a.years || b.swims - a.swims)[0];
        if (featured) setName(featured.name);
      })
      .catch((e) => {
        if (!cancelled) setError(`Couldn't reach the API (${e.message}). Is the backend running on :8000?`);
      });
    return () => { cancelled = true; };
  }, [gender]);

  useEffect(() => {
    // Only ask for a trend once the list for THIS gender has arrived and the
    // selected swimmer is actually in it.
    if (!name || list.gender !== gender) return;
    if (!list.swimmers.some((s) => s.name === name)) return;
    let cancelled = false;
    setTrend(null);
    setEventName(null);
    setSwim(null);
    fetchSwimmerTrend(name, gender)
      .then((t) => { if (!cancelled) setTrend(t); })
      .catch((e) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [name, gender, list]);

  const events = trend?.events ?? [];

  // Default to the swimmer's most-swum event whenever the trend loads.
  useEffect(() => {
    if (events.length === 0) return;
    const mostSwum = [...events].sort((a, b) => b.points.length - a.points.length)[0];
    setEventName(mostSwum.event);
  }, [trend]); // eslint-disable-line react-hooks/exhaustive-deps

  const current = useMemo(
    () => events.find((e) => e.event === eventName) ?? null,
    [events, eventName]
  );

  // Chart rows: one per year, with prelim and final swum times side by side.
  const chartRows = useMemo(
    () => (current?.points ?? []).map((p) => ({
      year: p.year,
      prelim_sec: p.prelim?.time_sec ?? null,
      final_sec: p.final?.time_sec ?? null,
    })),
    [current]
  );

  // The swimmer's best swim each year (final if present, else prelim) — for the headline.
  const bestPerYear = useMemo(
    () => (current?.points ?? [])
      .map((p) => {
        const t = [p.final?.time_sec, p.prelim?.time_sec].filter((v) => v != null);
        return t.length ? { year: p.year, time_sec: Math.min(...t) } : null;
      })
      .filter(Boolean),
    [current]
  );

  // When the event changes, preselect its most recent swim (final if there is one).
  useEffect(() => {
    const pts = current?.points ?? [];
    const last = pts[pts.length - 1];
    setSwim(last ? (last.final ?? last.prelim) : null);
  }, [current]);

  const pctChange = useMemo(() => {
    if (bestPerYear.length < 2) return null;
    const first = bestPerYear[0], last = bestPerYear[bestPerYear.length - 1];
    return { first, last, pct: ((last.time_sec - first.time_sec) / first.time_sec) * 100 };
  }, [bestPerYear]);

  const isSel = (s) => s && swim && s.year === swim.year && s.section === swim.section;

  return (
    <div>
      {error && <div className="error">{error}</div>}

      <div className="controls">
        <div className="field">
          <SwimmerSearch
            id="swimmer"
            label="Swimmer"
            items={swimmers}
            value={name}
            onChange={setName}
            placeholder="Type a name or team…"
            renderMeta={(s) => `${s.first_year}–${s.last_year} · ${s.schools.join(" / ")}`}
          />
        </div>

        {events.length > 0 && (
          <div className="field">
            <label htmlFor="swimmer-event">Event</label>
            <select id="swimmer-event" value={eventName ?? ""}
              onChange={(e) => setEventName(e.target.value)}>
              {events.map((e) => (
                <option key={e.event} value={e.event}>
                  {shortEvent(e.event)} ({e.points.length} yr{e.points.length === 1 ? "" : "s"})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {pctChange && (
        <div className="stat">
          <span className={pctChange.pct <= 0 ? "stat-num good" : "stat-num bad"}>
            {pctChange.pct <= 0 ? "▼" : "▲"} {Math.abs(pctChange.pct).toFixed(2)}%
          </span>
          <span className="stat-label">
            best-time {pctChange.pct <= 0 ? "improvement" : "regression"} ({pctChange.first.year}&nbsp;→&nbsp;{pctChange.last.year}):
            {" "}{formatTime(pctChange.first.time_sec)} → {formatTime(pctChange.last.time_sec)}
          </span>
        </div>
      )}

      <div className="card">
        {!current ? (
          <div className="loading">{trend ? "No timed individual results." : "Loading…"}</div>
        ) : (
          <ResponsiveContainer width="100%" height={380}>
            <LineChart data={chartRows} margin={{ top: 16, right: 24, bottom: 8, left: 8 }}
              onClick={(state) => {
                const yr = state?.activePayload?.[0]?.payload?.year;
                const p = current.points.find((x) => x.year === yr);
                if (p) setSwim(p.final ?? p.prelim);
              }}
              style={{ cursor: "pointer" }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="year" allowDuplicatedCategory={false} />
              <YAxis domain={["auto", "auto"]} reversed tickFormatter={formatTime} width={70}
                label={{ value: "Time (faster ↑)", angle: -90, position: "insideLeft", style: { fill: "#888" } }} />
              <Tooltip content={<TrendTip event={current.event} />} />
              <Legend wrapperStyle={{ paddingTop: 8 }} />
              <Line type="monotone" dataKey="final_sec" name="Final" stroke={FINAL_COLOR} strokeWidth={2.5}
                connectNulls dot={{ r: 4 }} activeDot={{ r: 6 }} />
              <Line type="monotone" dataKey="prelim_sec" name="Prelim" stroke={PRELIM_COLOR} strokeWidth={2.5}
                strokeDasharray="5 4" connectNulls dot={{ r: 4 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {current && (
        <div className="split-view">
          <table className="results">
            <thead>
              <tr><th>Year</th><th>Prelim</th><th>Final</th><th>Drop</th></tr>
            </thead>
            <tbody>
              {current.points.map((p) => {
                const drop = p.prelim && p.final ? p.prelim.time_sec - p.final.time_sec : null;
                return (
                  <tr key={p.year}>
                    <td>{p.year}</td>
                    <td className={"mono" + (isSel(p.prelim) ? " row-selected" : "")}
                      style={p.prelim ? { cursor: "pointer", color: PRELIM_COLOR } : undefined}
                      onClick={() => p.prelim && setSwim(p.prelim)}>
                      {p.prelim ? `${formatTime(p.prelim.time_sec)} (P${p.prelim.place ?? "–"})` : "—"}
                    </td>
                    <td className={"mono" + (isSel(p.final) ? " row-selected" : "")}
                      style={p.final ? { cursor: "pointer", fontWeight: 600 } : undefined}
                      onClick={() => p.final && setSwim(p.final)}>
                      {p.final ? `${formatTime(p.final.time_sec)} (P${p.final.place ?? "–"})` : "—"}
                    </td>
                    <td className={"mono " + (drop == null ? "" : drop > 0 ? "good" : "bad")}>
                      {fmtDrop(drop)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {swim && <SwimDetail event={current.event} swim={swim} />}
        </div>
      )}

      <p className="note">
        One event at a time. <span style={{ color: FINAL_COLOR }}>Final</span> vs{" "}
        <span style={{ color: PRELIM_COLOR }}>prelim</span> swum time each year; Drop = how much faster the final
        was. Click any time (or a chart point) for its splits.
      </p>
    </div>
  );
}

function TrendTip({ active, payload, label, event }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const drop = row.prelim_sec != null && row.final_sec != null ? row.prelim_sec - row.final_sec : null;
  return (
    <div style={TIP}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{label} · {shortEvent(event)}</div>
      <div style={{ display: "flex", gap: 8 }}>
        <span style={{ width: 9, height: 9, borderRadius: 2, background: PRELIM_COLOR, display: "inline-block", alignSelf: "center" }} />
        prelim <b style={{ marginLeft: "auto" }}>{row.prelim_sec != null ? formatTime(row.prelim_sec) : "—"}</b>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <span style={{ width: 9, height: 9, borderRadius: 2, background: FINAL_COLOR, display: "inline-block", alignSelf: "center" }} />
        final <b style={{ marginLeft: "auto" }}>{row.final_sec != null ? formatTime(row.final_sec) : "—"}</b>
      </div>
      {drop != null && (
        <div style={{ color: drop > 0 ? GOOD : BAD, marginTop: 2 }}>
          {fmtDrop(drop)} {drop > 0 ? "faster in final" : "slower in final"}
        </div>
      )}
    </div>
  );
}

// Quick overview of a single swim: place, time, section, points, reaction, splits.
function SwimDetail({ event, swim }) {
  const total = swim.splits.reduce((a, b) => a + b, 0);
  return (
    <div className="detail">
      <div className="detail-head">
        <strong>{shortEvent(event)}</strong> · {swim.year}
        <span className={`badge ${swim.section}`}>{swim.section}</span>
      </div>

      <div className="kv-row">
        <div className="kv"><span>Place</span><b>{swim.place ?? "—"}</b></div>
        <div className="kv"><span>Time</span><b className="mono">{formatTime(swim.time_sec)}</b></div>
        <div className="kv"><span>Points</span><b>{swim.points ?? "—"}</b></div>
        <div className="kv"><span>Reaction</span><b>{swim.reaction != null ? `${swim.reaction.toFixed(2)}s` : "—"}</b></div>
        <div className="kv"><span>School</span><b>{swim.school ?? "—"}</b></div>
      </div>

      {swim.splits.length > 0 && (
        <div className="splits">
          <div className="splits-label">Splits</div>
          <div className="chips">
            {swim.splits.map((s, i) => (
              <span key={i} className="chip"><em>{i + 1}</em>{s.toFixed(2)}</span>
            ))}
          </div>
          {Math.abs(total - swim.time_sec) < 1 && (
            <div className="splits-sum">sum {formatTime(total)}</div>
          )}
        </div>
      )}
    </div>
  );
}
