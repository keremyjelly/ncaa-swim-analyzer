import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
} from "recharts";
import { fetchSwimmers, fetchSwimmerTrend, formatTime, shortEvent } from "./api";

// Swimmer trends: pick a swimmer, then one event at a time. Click any swim
// (chart or table row) to see its splits and race detail.
export default function SwimmerTrends() {
  const [swimmers, setSwimmers] = useState([]);
  const [query, setQuery] = useState("Lasco, Destin");
  const [name, setName] = useState("Lasco, Destin");
  const [trend, setTrend] = useState(null);
  const [error, setError] = useState(null);

  const [eventName, setEventName] = useState(null);
  const [swim, setSwim] = useState(null); // selected point for the detail panel

  useEffect(() => {
    fetchSwimmers()
      .then(setSwimmers)
      .catch((e) => setError(`Couldn't reach the API (${e.message}). Is the backend running on :8000?`));
  }, []);

  useEffect(() => {
    if (!name) return;
    setTrend(null);
    setEventName(null);
    setSwim(null);
    fetchSwimmerTrend(name).then(setTrend).catch((e) => setError(e.message));
  }, [name]);

  const known = useMemo(() => new Set(swimmers.map((s) => s.name)), [swimmers]);
  function onQueryChange(v) {
    setQuery(v);
    if (known.has(v)) setName(v);
  }

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

  // When the event changes, preselect its most recent swim.
  useEffect(() => {
    setSwim(current?.points?.length ? current.points[current.points.length - 1] : null);
  }, [current]);

  // Percent change in time from the swimmer's first to most recent year in this
  // event. Negative = faster = improvement.
  const pctChange = useMemo(() => {
    const pts = current?.points ?? [];
    if (pts.length < 2) return null;
    const first = pts[0], last = pts[pts.length - 1];
    return {
      first, last,
      pct: ((last.time_sec - first.time_sec) / first.time_sec) * 100,
    };
  }, [current]);

  const baseSec = current?.points?.[0]?.time_sec ?? null;

  return (
    <div>
      {error && <div className="error">{error}</div>}

      <div className="controls">
        <div className="field">
          <label htmlFor="swimmer">Swimmer</label>
          <input id="swimmer" list="swimmer-list" value={query}
            placeholder="Type a name…" onChange={(e) => onQueryChange(e.target.value)} />
          <datalist id="swimmer-list">
            {swimmers.map((s) => (
              <option key={s.name} value={s.name}>
                {`${s.first_year}–${s.last_year} · ${s.schools.join("/")}`}
              </option>
            ))}
          </datalist>
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
            {pctChange.pct <= 0 ? "faster" : "slower"} ({pctChange.first.year}&nbsp;→&nbsp;{pctChange.last.year}):
            {" "}{formatTime(pctChange.first.time_sec)} → {formatTime(pctChange.last.time_sec)}
          </span>
        </div>
      )}

      <div className="card">
        {!current ? (
          <div className="loading">{trend ? "No timed individual results." : "Loading…"}</div>
        ) : (
          <ResponsiveContainer width="100%" height={380}>
            <LineChart data={current.points} margin={{ top: 16, right: 24, bottom: 8, left: 8 }}
              onClick={(state) => {
                const p = state?.activePayload?.[0]?.payload;
                if (p) setSwim(p);
              }}
              style={{ cursor: "pointer" }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="year" allowDuplicatedCategory={false} />
              <YAxis domain={["auto", "auto"]} reversed tickFormatter={formatTime} width={70}
                label={{ value: "Time (faster ↑)", angle: -90, position: "insideLeft", style: { fill: "#888" } }} />
              <Tooltip formatter={(v) => [formatTime(v), shortEvent(current.event)]}
                labelFormatter={(y) => `${y} Championships`} />
              <Line type="monotone" dataKey="time_sec" name={shortEvent(current.event)}
                stroke="#DC143C" strokeWidth={2.5}
                dot={{ r: 4 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {current && (
        <div className="split-view">
          <table className="results">
            <thead>
              <tr><th>Year</th><th>Time</th><th>Place</th><th>Δ%</th></tr>
            </thead>
            <tbody>
              {current.points.map((p, i) => {
                const pct = baseSec ? ((p.time_sec - baseSec) / baseSec) * 100 : null;
                return (
                  <tr key={p.year}
                      className={swim && swim.year === p.year ? "row-selected" : "row-click"}
                      onClick={() => setSwim(p)}>
                    <td>{p.year}</td>
                    <td className="mono">{formatTime(p.time_sec)}</td>
                    <td>{p.place ?? "—"}</td>
                    <td className={"mono " + (i === 0 ? "" : pct <= 0 ? "good" : "bad")}>
                      {i === 0 ? "—" : `${pct <= 0 ? "" : "+"}${pct.toFixed(2)}%`}
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
        One event at a time so each line's slope is meaningful. Δ% is vs the first year shown. Click a point or row for splits.
      </p>
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
