import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Legend,
} from "recharts";
import { fetchEvents, fetchRoster, fetchMatchup, shortEvent, formatTime } from "./api";

const A_COLOR = "#DC143C";
const B_COLOR = "#4169E1";

const TIP = {
  background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
  boxShadow: "0 4px 14px rgba(16,24,40,.12)", padding: "8px 10px",
  fontSize: 12, minWidth: 160, fontVariantNumeric: "tabular-nums",
};

const firstName = (n) => (n ? n.split(",")[0] : "");
const fastest = (sw) => (sw ? [...sw.swims].sort((a, b) => a.time_sec - b.time_sec)[0] : null);
const asPick = (s) => (s ? { year: s.year, section: s.section } : null);

export default function MatchUp({ gender }) {
  const [allEvents, setAllEvents] = useState([]);
  const [event, setEvent] = useState(null);
  const [roster, setRoster] = useState([]);
  const [aName, setAName] = useState(null);
  const [aSwim, setASwim] = useState(null); // { year, section }
  const [bName, setBName] = useState(null);
  const [bSwim, setBSwim] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchEvents()
      .then((evs) => setAllEvents(evs.filter((e) => !e.is_relay && e.distance)))
      .catch((e) => setError(`Couldn't reach the API (${e.message}). Is the backend running on :8000?`));
  }, []);

  const events = useMemo(() => allEvents.filter((e) => e.gender === gender), [allEvents, gender]);

  useEffect(() => {
    if (!events.length) return;
    if (!events.some((e) => e.name === event)) {
      const pref = events.find((e) => e.name === `${gender} 100 Yard Freestyle`);
      setEvent((pref ?? events[0]).name);
    }
  }, [events, gender, event]);

  // Load the roster whenever the event changes.
  useEffect(() => {
    if (!event) return;
    setRoster([]); setData(null);
    fetchRoster(event).then(setRoster).catch((e) => setError(e.message));
  }, [event]);

  // Default the two sides to the event's two fastest swimmers (their fastest swim).
  useEffect(() => {
    if (!roster.length) return;
    const ranked = roster
      .map((s) => ({ s, best: Math.min(...s.swims.map((x) => x.time_sec)) }))
      .sort((x, y) => x.best - y.best);
    const A = ranked[0]?.s, B = ranked[1]?.s ?? ranked[0]?.s;
    setAName(A?.name ?? null); setASwim(asPick(fastest(A)));
    setBName(B?.name ?? null); setBSwim(asPick(fastest(B)));
  }, [roster]);

  const validNames = useMemo(() => new Set(roster.map((s) => s.name)), [roster]);

  useEffect(() => {
    if (event && validNames.has(aName) && validNames.has(bName) && aSwim && bSwim) {
      fetchMatchup(event, { name: aName, ...aSwim }, { name: bName, ...bSwim })
        .then(setData).catch((e) => setError(e.message));
    }
  }, [event, aName, aSwim, bName, bSwim, validNames]);

  const pickName = (side) => (name) => {
    const sw = roster.find((s) => s.name === name);
    if (side === "a") { setAName(name); setASwim(asPick(fastest(sw))); }
    else { setBName(name); setBSwim(asPick(fastest(sw))); }
  };

  const ready = data && data.a && data.b;

  return (
    <div>
      {error && <div className="error">{error}</div>}

      <div className="controls">
        <div className="field">
          <label htmlFor="mu-event">Event</label>
          <select id="mu-event" value={event ?? ""} onChange={(e) => setEvent(e.target.value)}>
            {events.map((e) => <option key={e.name} value={e.name}>{shortEvent(e.name)}</option>)}
          </select>
        </div>
        <span className="meta">Compare any two swims — different swimmers, or the same swimmer across years.</span>
      </div>

      <div className="matchup-sides">
        <SwimmerPicker label="Swimmer A" color={A_COLOR} roster={roster}
          name={aName} swim={aSwim} onName={pickName("a")} onSwim={setASwim} />
        <SwimmerPicker label="Swimmer B" color={B_COLOR} roster={roster}
          name={bName} swim={bSwim} onName={pickName("b")} onSwim={setBSwim} />
      </div>

      <div className="card">
        {!ready ? <div className="loading">Loading…</div> : (
          <>
            <MarginChart data={data} />
            <PaceChart data={data} />
          </>
        )}
      </div>

      {ready && <CompareTable data={data} />}
    </div>
  );
}

function SwimmerPicker({ label, color, roster, name, swim, onName, onSwim }) {
  const sw = roster.find((s) => s.name === name);
  const swims = sw?.swims ?? [];
  return (
    <div className="matchup-side" style={{ borderTopColor: color }}>
      <div className="matchup-side-h" style={{ color }}>{label}</div>
      <select value={name ?? ""} onChange={(e) => onName(e.target.value)}>
        {roster.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
      </select>
      <select value={swim ? `${swim.year}|${swim.section}` : ""}
        onChange={(e) => { const [y, sec] = e.target.value.split("|"); onSwim({ year: +y, section: sec }); }}>
        {swims.map((s) => (
          <option key={`${s.year}|${s.section}`} value={`${s.year}|${s.section}`}>
            {s.year} {s.section} · {formatTime(s.time_sec)}{s.place ? ` (P${s.place})` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}

// Hero: running margin (swim A's lead in seconds) at each wall.
function MarginChart({ data }) {
  const { race, a, b, final_margin, distance } = data;
  if (!race.length) {
    return <div className="loading">No split data recorded for one of these swims — see the table below.</div>;
  }
  const aN = firstName(a.name), bN = firstName(b.name);
  const rows = race.map((r) => ({ dist: r.dist, lead: r.lead }));
  const maxAbs = Math.max(0.1, ...rows.map((r) => Math.abs(r.lead)));
  const verdict = final_margin === 0 ? "dead heat"
    : final_margin < 0 ? `${aN} ${a.year} wins by ${Math.abs(final_margin).toFixed(2)}s`
    : `${bN} ${b.year} wins by ${Math.abs(final_margin).toFixed(2)}s`;

  return (
    <>
      <div className="matchup-title">
        <span style={{ color: A_COLOR }}>{aN} {a.year} {a.section}</span>
        {" vs "}
        <span style={{ color: B_COLOR }}>{bN} {b.year} {b.section}</span>
        {" — "}{verdict}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={rows} margin={{ top: 14, right: 30, bottom: 24, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="dist" type="number" domain={[0, distance]} ticks={rows.map((r) => r.dist)}
            tickFormatter={(v) => `${v}`}
            label={{ value: "cumulative distance (yd)", position: "insideBottom", offset: -2, fill: "#888", fontSize: 12 }} />
          <YAxis domain={[-maxAbs * 1.15, maxAbs * 1.15]} width={70}
            tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}`}
            label={{ value: `${aN}'s lead (s)`, angle: -90, position: "insideLeft", fill: "#888", fontSize: 12 }} />
          <ReferenceLine y={0} stroke="#111" label={{ value: "even", fill: "#888", fontSize: 11, position: "right" }} />
          <Tooltip content={<MarginTip a={a} b={b} race={race} />} />
          <Line type="monotone" dataKey="lead" stroke={A_COLOR} strokeWidth={2.5} dot={{ r: 4 }} activeDot={{ r: 6 }} />
        </LineChart>
      </ResponsiveContainer>
      <p className="note">
        Above the line = <span style={{ color: A_COLOR }}>{aN} ({a.year})</span> ahead; below ={" "}
        <span style={{ color: B_COLOR }}>{bN} ({b.year})</span> ahead. The line is the running margin at each wall.
      </p>
    </>
  );
}

function MarginTip({ active, label, a, b, race }) {
  if (!active || label == null) return null;
  const r = race.find((x) => x.dist === label);
  if (!r) return null;
  return (
    <div style={TIP}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{label} yd</div>
      <div style={{ color: A_COLOR }}>{firstName(a.name)} <b>{formatTime(r.a_cum)}</b></div>
      <div style={{ color: B_COLOR }}>{firstName(b.name)} <b>{formatTime(r.b_cum)}</b></div>
      <div style={{ marginTop: 2 }}>
        {r.lead === 0 ? "even" : `${firstName(r.lead > 0 ? a.name : b.name)} +${Math.abs(r.lead).toFixed(2)}s`}
      </div>
    </div>
  );
}

// Per-segment split pace: side-by-side bars at each mark.
function PaceChart({ data }) {
  const { race, a, b } = data;
  if (!race.length) return null;
  const aN = firstName(a.name), bN = firstName(b.name);
  const rows = race.map((r) => ({ dist: r.dist, a: r.a_seg, b: r.b_seg }));
  return (
    <div style={{ marginTop: 18 }}>
      <div className="splits-label" style={{ marginLeft: 8 }}>Split pace (seconds per segment)</div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={rows} margin={{ top: 8, right: 30, bottom: 24, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
          <XAxis dataKey="dist" tickFormatter={(v) => `${v}`}
            label={{ value: "cumulative distance (yd)", position: "insideBottom", offset: -2, fill: "#888", fontSize: 12 }} />
          <YAxis width={54} tickFormatter={(v) => v.toFixed(1)} />
          <Tooltip formatter={(v, n) => [`${v.toFixed(2)}s`, n]} labelFormatter={(l) => `${l} yd segment`} />
          <Legend wrapperStyle={{ paddingTop: 8 }} />
          <Bar dataKey="a" name={`${aN} ${a.year}`} fill={A_COLOR} />
          <Bar dataKey="b" name={`${bN} ${b.year}`} fill={B_COLOR} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function CompareTable({ data }) {
  const { a, b, race } = data;
  const aHead = `${firstName(a.name)} ${a.year}`;
  const bHead = `${firstName(b.name)} ${b.year}`;
  // winner: 1 = A better, 2 = B better, 0 = tie/na. `lower` for times/places/reaction.
  const lower = (x, y) => (x == null || y == null ? 0 : x < y ? 1 : y < x ? 2 : 0);
  const higher = (x, y) => (x == null || y == null ? 0 : x > y ? 1 : y > x ? 2 : 0);
  const rt = (v) => (v != null ? `${v.toFixed(2)}s` : "—");

  return (
    <table className="compare">
      <thead>
        <tr>
          <th></th>
          <th style={{ color: A_COLOR }}>{aHead}</th>
          <th style={{ color: B_COLOR }}>{bHead}</th>
        </tr>
      </thead>
      <tbody>
        <Row label="Session" a={a.section} b={b.section} />
        <Row label="School" a={a.school ?? "—"} b={b.school ?? "—"} />
        <Row label="Time" a={formatTime(a.time_sec)} b={formatTime(b.time_sec)} win={lower(a.time_sec, b.time_sec)} />
        <Row label="Place" a={a.place ?? "—"} b={b.place ?? "—"} win={lower(a.place, b.place)} />
        <Row label="Points" a={a.points ?? "—"} b={b.points ?? "—"} win={higher(a.points, b.points)} />
        <Row label="Reaction" a={rt(a.reaction)} b={rt(b.reaction)} win={lower(a.reaction, b.reaction)} />
        {race.map((r) => (
          <Row key={r.dist} label={`${r.dist} yd split`}
            a={r.a_seg.toFixed(2)} b={r.b_seg.toFixed(2)} win={lower(r.a_seg, r.b_seg)} />
        ))}
      </tbody>
    </table>
  );
}

function Row({ label, a, b, win = 0 }) {
  return (
    <tr>
      <th>{label}</th>
      <td className={"mono" + (win === 1 ? " cmp-win" : "")}>{a}</td>
      <td className={"mono" + (win === 2 ? " cmp-win" : "")}>{b}</td>
    </tr>
  );
}
