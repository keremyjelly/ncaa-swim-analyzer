import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ReferenceArea,
} from "recharts";
import { fetchEvents, fetchAnalysisEvent, fetchReaction, shortEvent } from "./api";

// Ordered palette for the year lines.
const YEAR_COLORS = ["#4E79A7", "#F28E2B", "#59A14F", "#E15759", "#B07AA1", "#1F2937"];

// Shared diverging color for correlation-style heatmaps (red = positive, blue = inverse).
const divergeColor = (v, maxAbs = 1) => {
  if (v == null) return "transparent";
  const t = Math.max(-1, Math.min(1, v / maxAbs));
  const a = (0.12 + 0.72 * Math.abs(t)).toFixed(3);
  return t < 0 ? `rgba(65,105,225,${a})` : `rgba(220,20,60,${a})`;
};

const ANALYSES = [
  { kind: "split-distribution", label: "Split Distribution", control: "event",
    blurb: "One event's average pacing shape across 2021-2026. Each split is shown as % above/below that year's own average split. Thus 0 indicates average pace, negative indicates faster than pace (like the dive), and positive indicates slower than pace. Split marks are cumulative yards." },
  { kind: "split-place", label: "Split → Place", control: "event",
    blurb: "How strongly each split correlates with final place, year by year. Higher bar suggests that the split separated the field more that year." },
  { kind: "reaction", label: "Reaction Time", control: "none",
    blurb: "Reaction-time vs final-place correlation for every year and freestyle event (−1…1). Red = a slow start correlated to a worse place (reaction mattered); blue = the inverse; pale = little to no correlation." },
];

const fmtPct = (v) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`);

export default function RaceAnalysis({ gender }) {
  const [allEvents, setAllEvents] = useState([]);
  const [event, setEvent] = useState(null);
  const [kind, setKind] = useState("split-distribution");
  const [data, setData] = useState(null); // { forKind, payload }
  const [error, setError] = useState(null);

  const meta = ANALYSES.find((a) => a.kind === kind);

  useEffect(() => {
    fetchEvents()
      .then((evs) => setAllEvents(evs.filter((e) => !e.is_relay && e.distance >= 100)))
      .catch((e) => setError(`Couldn't reach the API (${e.message}). Is the backend running on :8000?`));
  }, []);

  const events = useMemo(() => allEvents.filter((e) => e.gender === gender), [allEvents, gender]);

  // Keep the selected event valid for the current gender.
  useEffect(() => {
    if (!events.length) return;
    if (!events.some((e) => e.name === event)) {
      const pref = events.find((e) => e.name === `${gender} 200 Yard Freestyle`);
      setEvent((pref ?? events[0]).name);
    }
  }, [events, gender, event]);

  useEffect(() => {
    setData(null);
    const forKind = kind;
    const req = meta.control === "event"
      ? (event && event.startsWith(gender) ? fetchAnalysisEvent(kind, event) : null)
      : fetchReaction(gender);
    if (req) req.then((r) => setData({ forKind, payload: r })).catch((e) => setError(e.message));
  }, [kind, event, gender]); // eslint-disable-line react-hooks/exhaustive-deps

  const ready = data && data.forKind === kind;

  return (
    <div>
      {error && <div className="error">{error}</div>}

      <nav className="subtabs">
        {ANALYSES.map((a) => (
          <button key={a.kind} className={a.kind === kind ? "subtab active" : "subtab"}
            onClick={() => setKind(a.kind)}>{a.label}</button>
        ))}
      </nav>

      <div className="controls">
        {meta.control === "event" && (
          <div className="field">
            <label htmlFor="an-event">Event</label>
            <select id="an-event" value={event ?? ""} onChange={(e) => setEvent(e.target.value)}>
              {events.map((e) => <option key={e.name} value={e.name}>{shortEvent(e.name)}</option>)}
            </select>
          </div>
        )}
        <span className="meta">{meta.blurb}</span>
      </div>

      <div className="card">
        {!ready ? <div className="loading">Loading…</div> : <Chart kind={kind} data={data.payload} />}
      </div>

      {ready && kind === "split-distribution" && data.payload.years?.length > 0 && (
        <FrontBackTable years={data.payload.years} />
      )}
    </div>
  );
}

function Chart({ kind, data }) {
  if (kind === "split-distribution") return <SplitDistribution data={data} />;
  if (kind === "split-place") return <SplitPlaceHeatmap data={data} />;
  if (kind === "reaction") return <ReactionHeatmap data={data} />;
  return null;
}

// --- split distribution ------------------------------------------------------

function SplitDistribution({ data }) {
  const { marks, years } = data;
  const [mode, setMode] = useState("line");

  const model = useMemo(() => {
    const rows = marks.map((m, i) => {
      const row = { dist: m };
      years.forEach((y) => (row[y.year] = y.rel[i]));
      return row;
    });
    const maxAbs = Math.max(0.5, ...years.flatMap((y) => y.rel.map((v) => Math.abs(v ?? 0))));
    return { rows, maxAbs };
  }, [marks, years]);

  if (!years.length) return <Empty />;

  return (
    <>
      <div className="toggle">
        <button className={mode === "line" ? "active" : ""} onClick={() => setMode("line")}>Line</button>
        <button className={mode === "heatmap" ? "active" : ""} onClick={() => setMode("heatmap")}>Heatmap</button>
      </div>

      {mode === "line"
        ? <RelLine rows={model.rows} years={years} marks={marks} />
        : <RelHeatmap years={years} marks={marks} maxAbs={model.maxAbs} />}

      <p className="note">
        Each split as % above/below that year's own average split, placed by cumulative distance.
        Negative = faster than the year's average pace (e.g. the dive); positive = slower.
      </p>
    </>
  );
}

function RelLine({ rows, years, marks }) {
  const xMin = marks[0];
  const xMax = marks[marks.length - 1];

  const [domain, setDomain] = useState([xMin, xMax]);
  const [ref, setRef] = useState(null);
  const [tip, setTip] = useState(null);
  const [hidden, setHidden] = useState(() => new Set());

  useEffect(() => { setDomain([xMin, xMax]); setRef(null); setTip(null); }, [rows, xMin, xMax]);

  const visYears = years.filter((y) => !hidden.has(String(y.year)));
  const zoomed = domain[0] > xMin || domain[1] < xMax;

  const yDomain = useMemo(() => {
    let mn = Infinity, mx = -Infinity;
    rows.forEach((r) => {
      if (r.dist < domain[0] || r.dist > domain[1]) return;
      visYears.forEach((y) => { const v = r[y.year]; if (v != null) { mn = Math.min(mn, v); mx = Math.max(mx, v); } });
    });
    if (mn === Infinity) return ["auto", "auto"];
    const pad = (mx - mn) * 0.18 || 0.5;
    return [+(mn - pad).toFixed(2), +(mx + pad).toFixed(2)];
  }, [rows, visYears, domain]);

  const ticks = useMemo(() => marks.filter((m) => m >= domain[0] && m <= domain[1])
    .filter((_, i, a) => a.length <= 14 || i % Math.ceil(a.length / 14) === 0), [marks, domain]);

  const down = (e) => { if (e?.activeLabel != null) { setRef({ a: e.activeLabel, b: e.activeLabel }); setTip(null); } };
  const move = (e) => { if (ref && e?.activeLabel != null) setRef((r) => ({ ...r, b: e.activeLabel })); };
  const up = () => { if (ref) { const { a, b } = ref; if (a !== b) setDomain([Math.min(a, b), Math.max(a, b)]); setRef(null); } };
  const toggle = (o) => {
    const k = String(o.dataKey);
    setHidden((s) => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n; });
  };

  return (
    <div style={{ position: "relative", userSelect: "none" }}>
      <div className="chart-toolbar">
        <span className="hint">Drag across the plot to zoom · click a year in the key to toggle it</span>
        {zoomed && <button className="linkbtn" onClick={() => setDomain([xMin, xMax])}>Reset zoom</button>}
      </div>

      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={rows} margin={{ top: 16, right: 28, bottom: 28, left: 8 }}
          onMouseDown={down} onMouseMove={move} onMouseUp={up}
          onMouseLeave={() => { setRef(null); setTip(null); }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="dist" type="number" domain={domain} ticks={ticks} allowDataOverflow
            tickFormatter={(v) => `${v}`}
            label={{ value: "cumulative distance (yd)", position: "insideBottom", offset: -2, fill: "#888", fontSize: 12 }} />
          <YAxis width={54} domain={yDomain} allowDataOverflow tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`} />
          <Tooltip content={() => null} cursor={ref ? false : { stroke: "#d1d5db", strokeDasharray: "3 3" }} />
          <ReferenceLine y={0} stroke="#111" label={{ value: "even", fill: "#888", fontSize: 11, position: "right" }} />
          <Legend onClick={toggle} wrapperStyle={{ paddingTop: 18, cursor: "pointer" }} />
          {years.map((y, i) => (
            <Line key={y.year} type="monotone" dataKey={y.year} name={`${y.year}`}
              stroke={YEAR_COLORS[i % YEAR_COLORS.length]} strokeWidth={2.5} connectNulls
              hide={hidden.has(String(y.year))} dot={{ r: 3 }}
              activeDot={{
                r: 6,
                onMouseEnter: (p) => {
                  if (ref || p?.cx == null) return;
                  setTip({ i: rows.findIndex((r) => r.dist === p.payload.dist), x: p.cx, y: p.cy });
                },
                onMouseLeave: () => setTip(null),
              }} />
          ))}
          {ref && ref.a !== ref.b && (
            <ReferenceArea x1={Math.min(ref.a, ref.b)} x2={Math.max(ref.a, ref.b)}
              fill="#4169E1" fillOpacity={0.08} stroke="#4169E1" strokeOpacity={0.3} />
          )}
        </LineChart>
      </ResponsiveContainer>

      {tip && !ref && rows[tip.i] && (
        <div className="pt-tip" style={{ left: tip.x, top: tip.y }}>
          <div className="pt-tip-h">{rows[tip.i].dist} yd mark</div>
          {visYears.map((y) => {
            const i = years.indexOf(y);
            return (
              <div key={y.year} className="pt-row">
                <span className="pt-dot" style={{ background: YEAR_COLORS[i % YEAR_COLORS.length] }} />
                {y.year}<b>{fmtPct(rows[tip.i][y.year])}</b>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function RelHeatmap({ years, marks, maxAbs }) {
  return (
    <div className="heatmap-wrap">
      <table className="heatmap">
        <thead>
          <tr><th>Year</th>{marks.map((m) => <th key={m}>{m}</th>)}</tr>
        </thead>
        <tbody>
          {years.map((y) => (
            <tr key={y.year}>
              <th>{y.year}</th>
              {y.rel.map((v, i) => (
                <td key={i} style={{ background: divergeColor(v, maxAbs) }} title={v != null ? `${marks[i]} yd: ${fmtPct(v)}` : ""}>
                  {fmtPct(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="heat-legend">
        <span className="sw blue" /> faster than year avg
        <span className="sw red" /> slower
        <span className="muted">columns are cumulative-distance marks (yd)</span>
      </div>
    </div>
  );
}

function FrontBackTable({ years }) {
  return (
    <table className="results" style={{ maxWidth: 460 }}>
      <thead>
        <tr><th>Year</th><th>Front half</th><th>Back half</th><th>n</th></tr>
      </thead>
      <tbody>
        {years.map((y) => (
          <tr key={y.year}>
            <td>{y.year}</td>
            <td className="mono">{y.front_pct}%</td>
            <td className="mono">{y.back_pct}%</td>
            <td>{y.n}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// --- split -> place (year x split heatmap) ----------------------------------

function SplitPlaceHeatmap({ data }) {
  const { marks, years } = data;
  if (!years.length) return <Empty />;
  return (
    <>
      <div className="heatmap-wrap">
        <table className="heatmap">
          <thead>
            <tr><th>Year</th>{marks.map((m) => <th key={m}>{m}</th>)}</tr>
          </thead>
          <tbody>
            {years.map((y) => (
              <tr key={y.year}>
                <th>{y.year}</th>
                {y.corr.map((v, i) => (
                  <td key={i} style={{ background: divergeColor(v) }}
                    title={v != null ? `${marks[i]} yd: r=${v}` : "no data"}>
                    {v != null ? v.toFixed(2) : "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="heat-legend">
          <span className="sw red" /> split predicts place
          <span className="sw blue" /> inverse
          <span className="muted">Pearson r · columns are cumulative-distance marks (yd)</span>
        </div>
      </div>
      <p className="note">
        Correlation of each split time with final place, per year. Blank cells = that split wasn't
        recorded that year (the 100s went from 50s to 25s in 2024).
      </p>
    </>
  );
}

// --- reaction: year x event heatmap -----------------------------------------

function ReactionHeatmap({ data }) {
  const { events, rows } = data;
  const color = (v) => divergeColor(v);
  return (
    <div className="heatmap-wrap">
      <table className="heatmap">
        <thead>
          <tr><th>Year</th>{events.map((e) => <th key={e}>{e}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.year}>
              <th>{r.year}</th>
              {r.cells.map((c, i) => (
                <td key={i} style={{ background: color(c.value) }}
                  title={c.value != null ? `${events[i]}: r=${c.value} (n=${c.n})` : "no data"}>
                  {c.value != null ? c.value.toFixed(2) : "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="heat-legend">
        <span className="sw red" /> slow start → worse place
        <span className="sw blue" /> slow start → better place
        <span className="muted">Pearson r, −1…1</span>
      </div>
    </div>
  );
}

function Empty() {
  return <div className="loading">No data for this event.</div>;
}
