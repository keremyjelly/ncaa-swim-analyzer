import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, ScatterChart, Scatter, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Legend,
} from "recharts";
import { fetchEvents, fetchCompare, fetchMeetDrop, shortEvent, formatTime } from "./api";
import StepUp, { STEPUP_VIEWS } from "./StepUp";

// Same ordered palette the Race Analysis tab uses for year lines.
const YEAR_COLORS = ["#4E79A7", "#F28E2B", "#59A14F", "#E15759", "#B07AA1", "#1F2937"];
const GOOD = "#11A046";
const BAD = "#DC143C";

const TIP = {
  background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
  boxShadow: "0 4px 14px rgba(16,24,40,.12)", padding: "8px 10px",
  fontSize: 12, minWidth: 130, fontVariantNumeric: "tabular-nums",
};

// Two families of question live under this tab. EVENT_VIEWS drill into one
// event and need the event picker; STEPUP_VIEWS pool the whole meet and don't.
const EVENT_VIEWS = [
  { kind: "time-drop", label: "Time Drop",
    blurb: "Each finalist's prelim time vs their final. Points below the diagonal swam faster in the final — green improved, red added time." },
  { kind: "rank-movement", label: "Rank Movement",
    blurb: "Prelim seed rank on the left, final place on the right. Green lines rose up the standings; red lines faded." },
  { kind: "pacing", label: "Where the Drop Happens",
    blurb: "Average per-segment change from prelims to finals, by cumulative distance. Above 0 = that stretch of the race was faster in the final." },
];

const VIEWS = [...EVENT_VIEWS, ...STEPUP_VIEWS];
const isEventView = (kind) => EVENT_VIEWS.some((v) => v.kind === kind);

// A signed drop in seconds: +0.29s faster, −0.10s slower.
const fmtSec = (v) =>
  v == null ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)}s`;

export default function PrelimFinals({ gender }) {
  const [allEvents, setAllEvents] = useState([]);
  const [event, setEvent] = useState(null);
  const [kind, setKind] = useState("time-drop");
  const [data, setData] = useState(null); // { forKind, payload }
  const [error, setError] = useState(null);

  const meta = VIEWS.find((v) => v.kind === kind);

  useEffect(() => {
    fetchEvents()
      // Individual events that have prelims: exclude relays and the 1650 (timed final, no prelim).
      .then((evs) => setAllEvents(evs.filter((e) => !e.is_relay && e.distance && e.distance !== 1650)))
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
    if (!isEventView(kind)) return; // meet-wide views fetch their own data
    setData(null);
    const forKind = kind;
    if (event && event.startsWith(gender)) {
      fetchCompare(kind, event)
        .then((r) => setData({ forKind, payload: r }))
        .catch((e) => setError(e.message));
    }
  }, [kind, event, gender]); // eslint-disable-line react-hooks/exhaustive-deps

  const eventScoped = isEventView(kind);
  const ready = data && data.forKind === kind;

  return (
    <div>
      {error && <div className="error">{error}</div>}

      <nav className="subtabs">
        <span className="subtab-group">One event</span>
        {EVENT_VIEWS.map((v) => (
          <button key={v.kind} className={v.kind === kind ? "subtab active" : "subtab"}
            onClick={() => setKind(v.kind)}>{v.label}</button>
        ))}
        <span className="subtab-div" aria-hidden="true" />
        <span className="subtab-group">Across the meet</span>
        {STEPUP_VIEWS.map((v) => (
          <button key={v.kind} className={v.kind === kind ? "subtab active" : "subtab"}
            onClick={() => setKind(v.kind)}>{v.label}</button>
        ))}
      </nav>

      {eventScoped ? (
        <div className="controls">
          <div className="field">
            <label htmlFor="pf-event">Event</label>
            <select id="pf-event" value={event ?? ""} onChange={(e) => setEvent(e.target.value)}>
              {events.map((e) => <option key={e.name} value={e.name}>{shortEvent(e.name)}</option>)}
            </select>
          </div>
          <span className="meta">{meta.blurb}</span>
        </div>
      ) : (
        <p className="sub">{meta.blurb}</p>
      )}

      {eventScoped ? (
        <div className="card">
          {!ready ? <div className="loading">Loading…</div> : <View kind={kind} data={data.payload} gender={gender} />}
        </div>
      ) : (
        <StepUp gender={gender} view={kind} />
      )}
    </div>
  );
}

function View({ kind, data, gender }) {
  if (kind === "time-drop") return <TimeDrop data={data} gender={gender} />;
  if (kind === "rank-movement") return <RankMovement data={data} />;
  if (kind === "pacing") return <Pacing data={data} />;
  return null;
}

function YearPicker({ years, year, setYear }) {
  return (
    <div className="toggle" style={{ marginBottom: 12 }}>
      {years.map((y) => (
        <button key={y} className={y === year ? "active" : ""} onClick={() => setYear(y)}>{y}</button>
      ))}
    </div>
  );
}

// --- Time Drop: prelim vs final scatter --------------------------------------

function TimeDrop({ data, gender }) {
  const years = data.years;
  const last = years.length ? years[years.length - 1].year : null;
  const [year, setYear] = useState(last);
  const [scope, setScope] = useState("event"); // "event" | "meet"
  const [meet, setMeet] = useState(null); // { gender, payload }
  useEffect(() => { setYear(last); }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  // Lazily load the whole-meet data the first time it's needed (and on gender change).
  useEffect(() => {
    if (scope === "meet" && (!meet || meet.gender !== gender)) {
      fetchMeetDrop(gender).then((r) => setMeet({ gender, payload: r })).catch(() => {});
    }
  }, [scope, gender, meet]);

  const yd = years.find((y) => y.year === year) ?? years[years.length - 1];

  const model = useMemo(() => {
    if (!yd) return null;
    const times = yd.swimmers.flatMap((s) => [s.prelim_sec, s.final_sec]);
    const lo = Math.min(...times), hi = Math.max(...times);
    const pad = (hi - lo) * 0.06 || 0.5;
    return {
      dom: [+(lo - pad).toFixed(2), +(hi + pad).toFixed(2)],
      improved: yd.swimmers.filter((s) => s.drop > 0),
      slower: yd.swimmers.filter((s) => s.drop <= 0),
    };
  }, [yd]);

  if (!years.length || !yd || !model) return <Empty />;

  return (
    <>
      <div className="toggle" style={{ marginBottom: 12 }}>
        <button className={scope === "event" ? "active" : ""} onClick={() => setScope("event")}>This event</button>
        <button className={scope === "meet" ? "active" : ""} onClick={() => setScope("meet")}>Whole meet</button>
      </div>

      <YearPicker years={years.map((y) => y.year)} year={yd.year} setYear={setYear} />

      {scope === "event" ? (
        <EventScatter yd={yd} model={model} />
      ) : (
        <MeetScatter meet={meet} gender={gender} year={yd.year} />
      )}

      <table className="results" style={{ maxWidth: 540 }}>
        <thead>
          <tr><th>Year</th><th>Finalists</th><th>Mean drop</th><th>Median</th><th>% faster</th></tr>
        </thead>
        <tbody>
          {years.map((y) => (
            <tr key={y.year} className="row-click"
              style={y.year === yd.year ? { background: "#fdeef0" } : undefined}
              onClick={() => setYear(y.year)}>
              <td>{y.year}</td>
              <td>{y.n}</td>
              <td className={"mono " + (y.mean_drop > 0 ? "good" : "bad")}>{fmtSec(y.mean_drop)}</td>
              <td className="mono">{fmtSec(y.median_drop)}</td>
              <td className="mono">{y.pct_improved}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function EventScatter({ yd, model }) {
  return (
    <>
      <div className="stat">
        <span className="stat-num good">{yd.pct_improved}%</span>
        <span className="stat-label">
          of {yd.n} finalists swam faster in the final &middot; mean {fmtSec(yd.mean_drop)}, median {fmtSec(yd.median_drop)}
        </span>
      </div>

      <ResponsiveContainer width="100%" height={380}>
        <ScatterChart margin={{ top: 10, right: 24, bottom: 26, left: 14 }}>
          <CartesianGrid stroke="#eee" />
          <XAxis type="number" dataKey="prelim_sec" domain={model.dom} tickFormatter={formatTime}
            allowDecimals name="Prelim"
            label={{ value: "prelim time", position: "insideBottom", offset: -2, fill: "#888", fontSize: 12 }} />
          <YAxis type="number" dataKey="final_sec" domain={model.dom} tickFormatter={formatTime} width={64}
            name="Final"
            label={{ value: "final time", angle: -90, position: "insideLeft", fill: "#888", fontSize: 12 }} />
          <ReferenceLine segment={[{ x: model.dom[0], y: model.dom[0] }, { x: model.dom[1], y: model.dom[1] }]}
            stroke="#9ca3af" strokeDasharray="5 5" ifOverflow="hidden" />
          <Tooltip content={<DropTip />} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={model.improved} fill={GOOD} />
          <Scatter data={model.slower} fill={BAD} />
        </ScatterChart>
      </ResponsiveContainer>
      <p className="note">
        Below the dashed line = faster in the final than in prelims ({yd.year}). Click a year in the table to switch.
      </p>
    </>
  );
}

// Whole-meet scatter: every finalist across all events, one year.
//
// This used to plot final time against prelim time on log-log axes. Both swims
// are nearly identical, so ~190 points collapsed onto the y=x diagonal and the
// only thing worth seeing — the gap between the two swims — was squeezed into a
// couple of pixels perpendicular to it.
//
// Plotting the DIFFERENCE against the prelim time instead frees the whole
// vertical axis for the signal (a Bland-Altman/MA-plot style transform). The
// diagonal becomes a flat zero line, and a 0.4% drop is now a visible distance
// rather than a hairline offset. As a share of prelim time the y-axis stays
// comparable across events, so the 50 and the 500 still sit together.
const LOG_TICKS = [15, 18, 20, 25, 30, 45, 60, 90, 120, 180, 240, 300, 480, 600];

function MeetScatter({ meet, gender, year }) {
  const [hoverEvent, setHoverEvent] = useState(null);

  if (!meet || meet.gender !== gender) return <div className="loading">Loading whole meet…</div>;
  const yd = meet.payload.years.find((y) => y.year === year);
  if (!yd || !yd.swims.length) return <Empty />;

  const times = yd.swims.map((s) => s.prelim_sec);
  const lo = Math.min(...times), hi = Math.max(...times);
  const dom = [+(lo * 0.9).toFixed(2), +(hi * 1.1).toFixed(2)];
  const ticks = LOG_TICKS.filter((t) => t >= dom[0] && t <= dom[1]);

  // Symmetric y-domain so the zero line sits centred and green/red read evenly.
  const maxAbs = Math.max(0.6, ...yd.swims.map((s) => Math.abs(s.pct))) * 1.08;

  const events = [...new Set(yd.swims.map((s) => s.event))].sort();
  const shown = hoverEvent ? yd.swims.filter((s) => s.event === hoverEvent) : yd.swims;
  const improved = shown.filter((s) => s.pct > 0);
  const slower = shown.filter((s) => s.pct <= 0);
  const median = [...yd.swims.map((s) => s.pct)].sort((a, b) => a - b)[Math.floor(yd.n / 2)];

  return (
    <>
      <div className="stat">
        <span className="stat-num good">{yd.pct_improved}%</span>
        <span className="stat-label">of {yd.n} finalist swims across the meet were faster in the final ({year})</span>
      </div>

      <div className="evt-filter">
        <button className={hoverEvent ? "chipbtn" : "chipbtn active"} onClick={() => setHoverEvent(null)}>
          All events
        </button>
        {events.map((e) => (
          <button key={e} className={hoverEvent === e ? "chipbtn active" : "chipbtn"}
            onClick={() => setHoverEvent(hoverEvent === e ? null : e)}>
            {shortEvent(e)}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 10, right: 24, bottom: 26, left: 14 }}>
          <CartesianGrid stroke="#eee" />
          <XAxis type="number" dataKey="prelim_sec" scale="log" domain={dom} ticks={ticks}
            tickFormatter={formatTime} allowDataOverflow name="Prelim"
            label={{ value: "prelim time (log)", position: "insideBottom", offset: -2, fill: "#888", fontSize: 12 }} />
          <YAxis type="number" dataKey="pct" domain={[-maxAbs, maxAbs]} width={64}
            tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`} name="Change"
            label={{ value: "faster in final (%)", angle: -90, position: "insideLeft", fill: "#888", fontSize: 12 }} />
          <ReferenceLine y={0} stroke="#6b7280"
            label={{ value: "same as prelims", fill: "#888", fontSize: 11, position: "insideBottomRight" }} />
          <ReferenceLine y={median} stroke="#4169E1" strokeDasharray="5 5"
            label={{ value: `median ${median > 0 ? "+" : ""}${median.toFixed(2)}%`, fill: "#4169E1", fontSize: 11, position: "insideTopRight" }} />
          <Tooltip content={<MeetTip />} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={improved} fill={GOOD} fillOpacity={0.65} />
          <Scatter data={slower} fill={BAD} fillOpacity={0.65} />
        </ScatterChart>
      </ResponsiveContainer>
      <p className="note">
        Every finalist in every individual event ({year}). Height is how much faster the final was than the
        morning swim, as a share of the prelim time — above the line improved, below it added time. Faster
        events sit left, distance events right. Click an event above to isolate it.
      </p>
    </>
  );
}

function DropTip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const s = payload[0].payload;
  const faster = s.drop > 0;
  return (
    <div style={TIP}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{s.name}</div>
      <div>seed P{s.prelim_place} &rarr; final P{s.final_place}</div>
      <div>prelim <b>{formatTime(s.prelim_sec)}</b></div>
      <div>final <b>{formatTime(s.final_sec)}</b></div>
      <div style={{ color: faster ? GOOD : BAD, marginTop: 2 }}>
        {fmtSec(s.drop)} {faster ? "faster" : "slower"}
      </div>
    </div>
  );
}

function MeetTip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const s = payload[0].payload;
  const faster = s.pct > 0;
  return (
    <div style={TIP}>
      <div style={{ fontWeight: 700, marginBottom: 2 }}>{s.name}</div>
      <div style={{ color: "#6b7280", marginBottom: 4 }}>{shortEvent(s.event)} &middot; final P{s.final_place}</div>
      <div>prelim <b>{formatTime(s.prelim_sec)}</b></div>
      <div>final <b>{formatTime(s.final_sec)}</b></div>
      <div style={{ color: faster ? GOOD : BAD, marginTop: 2 }}>
        {faster ? "−" : "+"}{Math.abs(s.pct).toFixed(2)}% {faster ? "faster" : "slower"}
      </div>
    </div>
  );
}

// --- Rank Movement: seed -> final slope chart --------------------------------

function RankMovement({ data }) {
  const years = data.years;
  const last = years.length ? years[years.length - 1].year : null;
  const [year, setYear] = useState(last);
  useEffect(() => { setYear(last); }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  const yd = years.find((y) => y.year === year) ?? years[years.length - 1];
  if (!years.length || !yd) return <Empty />;

  return (
    <>
      <YearPicker years={years.map((y) => y.year)} year={yd.year} setYear={setYear} />
      <SlopeChart swimmers={yd.swimmers} />
      <p className="note">
        Left = prelim seed rank, right = final place ({yd.year}). Green rose up the standings, red fell,
        gray held. The number is places gained.
      </p>
    </>
  );
}

function SlopeChart({ swimmers }) {
  if (!swimmers.length) return <Empty />;
  const maxP = Math.max(...swimmers.flatMap((s) => [s.prelim_place, s.final_place]));
  const rowH = 26, padTop = 28, padBot = 16;
  const H = padTop + padBot + (maxP - 1) * rowH;
  const leftX = 96, rightX = 432, W = 780;
  const y = (place) => padTop + (place - 1) * rowH;

  // Swimmers who tie on final place would otherwise print their names on top of
  // each other. Fan the tied labels out vertically and draw a leader line back
  // to the shared dot so each name still reads clearly.
  const labelDy = new Map();
  const byFinal = {};
  swimmers.forEach((s) => { (byFinal[s.final_place] ||= []).push(s); });
  Object.values(byFinal).forEach((grp) => {
    const m = grp.length;
    grp.forEach((s, k) => labelDy.set(s, (k - (m - 1) / 2) * 14));
  });

  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={W} height={H} style={{ fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
        <text x={leftX} y={12} textAnchor="middle" fill="#6b7280" fontWeight="600">Prelim seed</text>
        <text x={rightX} y={12} textAnchor="middle" fill="#6b7280" fontWeight="600">Final place</text>

        {Array.from({ length: maxP }, (_, i) => i + 1).map((p) => (
          <g key={p}>
            <text x={leftX - 30} y={y(p) + 4} textAnchor="end" fill="#c3c7cf">{p}</text>
            <text x={rightX + 22} y={y(p) + 4} textAnchor="start" fill="#c3c7cf">{p}</text>
          </g>
        ))}

        {swimmers.map((s) => {
          const col = s.move > 0 ? GOOD : s.move < 0 ? BAD : "#9ca3af";
          const dy = labelDy.get(s) || 0;
          const ly = y(s.final_place) + 4 + dy;
          return (
            <g key={s.name + s.final_place}>
              <line x1={leftX} y1={y(s.prelim_place)} x2={rightX} y2={y(s.final_place)}
                stroke={col} strokeWidth={s.move !== 0 ? 2.2 : 1.3} strokeOpacity={0.72} />
              <circle cx={leftX} cy={y(s.prelim_place)} r={3.5} fill={col} />
              <circle cx={rightX} cy={y(s.final_place)} r={3.5} fill={col} />
              {dy !== 0 && (
                <line x1={rightX + 6} y1={y(s.final_place)} x2={rightX + 34} y2={ly - 4}
                  stroke={col} strokeWidth={1} strokeOpacity={0.5} />
              )}
              <text x={rightX + 40} y={ly} fill="#374151">
                {s.name.split(",")[0]}
                {s.move !== 0 && (
                  <tspan fill={col} fontWeight="600"> {s.move > 0 ? "+" : ""}{s.move}</tspan>
                )}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// --- Where the Drop Happens: per-split delta line ----------------------------

function Pacing({ data }) {
  const { marks, years } = data;

  const rows = useMemo(() => marks.map((m, i) => {
    const row = { dist: m };
    years.forEach((yy) => (row[yy.year] = yy.delta[i]));
    return row;
  }), [marks, years]);

  if (!years.length) return <Empty />;

  return (
    <>
      <ResponsiveContainer width="100%" height={380}>
        <LineChart data={rows} margin={{ top: 14, right: 30, bottom: 28, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="dist" type="number" domain={[marks[0], marks[marks.length - 1]]} ticks={marks}
            tickFormatter={(v) => `${v}`}
            label={{ value: "cumulative distance (yd)", position: "insideBottom", offset: -2, fill: "#888", fontSize: 12 }} />
          <YAxis width={58} tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}`}
            label={{ value: "prelim − final (s)", angle: -90, position: "insideLeft", fill: "#888", fontSize: 12 }} />
          <ReferenceLine y={0} stroke="#111"
            label={{ value: "same as prelims", fill: "#888", fontSize: 11, position: "insideBottomRight" }} />
          <Tooltip content={<PaceTip />} />
          <Legend wrapperStyle={{ paddingTop: 14 }} />
          {years.map((yy, i) => (
            <Line key={yy.year} type="monotone" dataKey={yy.year} name={`${yy.year}`}
              stroke={YEAR_COLORS[i % YEAR_COLORS.length]} strokeWidth={2.5} connectNulls dot={{ r: 3 }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <p className="note">
        Average per-segment change (prelim &minus; final) for paired finalists. Above 0 = that stretch was faster in
        the final. Marks are cumulative yards; gaps in early years are the 50-yd-split era of the 100s.
      </p>

      <table className="results" style={{ maxWidth: 540 }}>
        <thead>
          <tr><th>Year</th><th>Front half</th><th>Back half</th><th>Total drop</th><th>n</th></tr>
        </thead>
        <tbody>
          {years.map((yy) => (
            <tr key={yy.year}>
              <td>{yy.year}</td>
              <td className={"mono " + (yy.front_drop > 0 ? "good" : "bad")}>{fmtSec(yy.front_drop)}</td>
              <td className={"mono " + (yy.back_drop > 0 ? "good" : "bad")}>{fmtSec(yy.back_drop)}</td>
              <td className={"mono " + (yy.total_drop > 0 ? "good" : "bad")}>{fmtSec(yy.total_drop)}</td>
              <td>{yy.n}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function PaceTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const shown = payload.filter((p) => p.value != null);
  if (!shown.length) return null;
  return (
    <div style={TIP}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{label} yd mark</div>
      {shown.map((p) => (
        <div key={p.dataKey} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ width: 9, height: 9, borderRadius: 2, background: p.color, display: "inline-block" }} />
          {p.name}
          <b style={{ marginLeft: "auto" }}>{p.value > 0 ? "+" : ""}{p.value.toFixed(3)}s</b>
        </div>
      ))}
    </div>
  );
}

function Empty() {
  return <div className="loading">No paired prelim/final data for this event.</div>;
}
