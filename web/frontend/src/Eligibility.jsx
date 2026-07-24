import { useEffect, useState } from "react";
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { fetchClassShare } from "./api";

// Freshman -> 5th year, cool to warm, so the 5Y band reads as the anomaly it is.
const CLASS_COLORS = {
  FR: "#A0CBE8", SO: "#4E79A7", JR: "#59A14F", SR: "#F28E2B", "5Y": "#E15759",
};

const TIP = {
  background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
  boxShadow: "0 4px 14px rgba(16,24,40,.12)", padding: "8px 10px",
  fontSize: 12, minWidth: 150, fontVariantNumeric: "tabular-nums",
};

export default function Eligibility({ gender }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    setError(null);
    fetchClassShare(gender)
      .then(setData)
      .catch((e) =>
        setError(`Couldn't reach the API (${e.message}). Is the backend running on :8000?`)
      );
  }, [gender]);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div className="loading">Loading class data…</div>;
  if (!data.years.length) return <div className="error">No scoring data for {gender}.</div>;

  const fifth = data.years.map((y) => ({ year: y.year, share: y["5Y"] ?? 0 }));
  const peak = fifth.reduce((a, b) => (b.share > a.share ? b : a), fifth[0]);
  const last = fifth[fifth.length - 1];

  return (
    <>
      <p className="sub">
        The NCAA&rsquo;s blanket extra-eligibility grant for the 2020&ndash;21 season created a cohort
        that lingered on podiums for years. Scoring share by class year traces the wave arriving and
        washing out.
      </p>

      <div className="card" style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
        <div className="stat">
          <div className="stat-num" style={{ color: CLASS_COLORS["5Y"] }}>{peak.share.toFixed(1)}%</div>
          <div className="stat-label">peak 5th-year scoring share ({peak.year})</div>
        </div>
        <div className="stat">
          <div className="stat-num" style={{ color: "#4E79A7" }}>{last.share.toFixed(1)}%</div>
          <div className="stat-label">by {last.year}</div>
        </div>
      </div>

      <div className="card">
        <h3 style={{ margin: "0 0 4px" }}>Scoring share by class year</h3>
        <ResponsiveContainer width="100%" height={340}>
          <AreaChart data={data.years} margin={{ top: 10, right: 20, bottom: 24, left: 4 }}>
            <CartesianGrid stroke="#eef0f3" vertical={false} />
            <XAxis dataKey="year" tick={{ fontSize: 12 }} />
            <YAxis
              domain={[0, 100]} width={46} tick={{ fontSize: 12 }}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              contentStyle={TIP}
              formatter={(v, n) => [`${v.toFixed(1)}%`, n]}
              labelFormatter={(l) => `${l} Championships`}
            />
            <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
            {data.classes.map((c) => (
              <Area
                key={c} type="monotone" dataKey={c} stackId="1" name={c}
                stroke={CLASS_COLORS[c]} fill={CLASS_COLORS[c]} fillOpacity={0.85}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3 style={{ margin: "0 0 4px" }}>The 5th-year band alone</h3>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={fifth} margin={{ top: 10, right: 20, bottom: 24, left: 4 }}>
            <CartesianGrid stroke="#eef0f3" vertical={false} />
            <XAxis dataKey="year" tick={{ fontSize: 12 }} />
            <YAxis width={46} tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
            <Tooltip
              contentStyle={TIP}
              formatter={(v) => [`${v.toFixed(1)}%`, "5th-year share"]}
              labelFormatter={(l) => `${l} Championships`}
            />
            <Line
              type="monotone" dataKey="share" stroke={CLASS_COLORS["5Y"]}
              strokeWidth={2.5} dot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <table className="su-table">
          <thead>
            <tr>
              <th>Meet</th>
              {data.classes.map((c) => <th key={c}>{c}</th>)}
              <th>Total pts</th>
            </tr>
          </thead>
          <tbody>
            {data.years.map((y) => (
              <tr key={y.year}>
                <td>{y.year}</td>
                {data.classes.map((c) => (
                  <td key={c} className="num" title={`${y[`${c}_points`]} pts, ${y[`${c}_swimmers`]} swimmers`}>
                    {(y[c] ?? 0).toFixed(1)}%
                  </td>
                ))}
                <td className="num" style={{ color: "#9ca3af" }}>{y.total_points}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note" style={{ marginTop: 8 }}>
          Individual events only — relay rows have no single class year. Shares rather than raw
          points, since the number of points on offer differs by season (2026 has no consolation
          final in the source data, so its total is roughly half). This dataset uses a single
          <code> 5Y </code> code with no separate <code>GR</code>, so nothing needed merging.
        </p>
      </div>
    </>
  );
}
