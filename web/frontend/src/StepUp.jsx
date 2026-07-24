import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, ComposedChart, BarChart, Bar, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, Legend, Cell,
} from "recharts";
import { fetchStepUp } from "./api";

const GOOD = "#11A046";
const BAD = "#DC143C";
const ACCENT = "#4E79A7";
const MUTED = "#9ca3af";

const TIP = {
  background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8,
  boxShadow: "0 4px 14px rgba(16,24,40,.12)", padding: "8px 10px",
  fontSize: 12, minWidth: 150, fontVariantNumeric: "tabular-nums",
};

// Meet-wide views. Exported so the Prelims -> Finals umbrella can drive the
// shared sub-nav; this component renders whichever one is selected.
export const STEPUP_VIEWS = [
  { kind: "seed", label: "The Seed Effect",
    blurb: "Prelim seed almost entirely determines who steps up at night. Top seeds go faster in the final far more often than swimmers who scraped into the B final — the opposite of regression to the mean. The other meet-wide views adjust this curve away." },
  { kind: "program", label: "Programs",
    blurb: "Each program's median swim scored against what its swimmers' seeds predict. Above zero = the program beats its seeding; the raw column shows how much of a program's apparent step-up is really just sending top seeds." },
  { kind: "class", label: "By Class Year",
    blurb: "Seed-adjusted step-up by class year. Raw numbers flatter upperclassmen because they seed better — the adjusted column is the like-for-like comparison." },
];

// Signed percentage, e.g. +0.42% faster
const pct = (v, digits = 2) =>
  v == null ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`;

export default function StepUp({ gender, view = "seed" }) {
  const kind = view;
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    setError(null);
    fetchStepUp(gender)
      .then(setData)
      .catch((e) =>
        setError(`Couldn't reach the API (${e.message}). Is the backend running on :8000?`)
      );
  }, [gender]);

  const seedRows = useMemo(
    () =>
      (data?.seed_curve ?? []).map((r) => ({
        ...r,
        seedLabel: String(r.seed),
      })),
    [data]
  );

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div className="loading">Loading step-up data…</div>;
  if (!data.n) return <div className="error">No paired prelim/final swims for {gender}.</div>;

  const partial = data.partial_years ?? [];

  return (
    <>
      <div className="card" style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
        <div className="stat">
          <div className="stat-num" style={{ color: ACCENT }}>{data.n.toLocaleString()}</div>
          <div className="stat-label">paired prelim → final swims</div>
        </div>
        <div className="stat">
          <div className={data.overall.pct_faster >= 50 ? "stat-num good" : "stat-num bad"}>
            {data.overall.pct_faster}%
          </div>
          <div className="stat-label">went faster in the final</div>
        </div>
        <div className="stat">
          <div className="stat-num" style={{ color: ACCENT }}>{pct(data.overall.median)}</div>
          <div className="stat-label">median change (− = slower)</div>
        </div>
      </div>

      {kind === "seed" && <SeedView rows={seedRows} bands={data.bands} />}
      {kind === "program" && (
        <>
          <RankView rows={data.programs} labelKey="school" title="Program" minN={data.min_n} />
          <Reliability rel={data.reliability} />
        </>
      )}
      {kind === "class" && <RankView rows={data.classes} labelKey="cls" title="Class" sorted={false} />}

      <YearStrip years={data.years} partial={partial} />

      <p className="note">
        Individual events only; the 1650 is excluded because it&rsquo;s a timed final, so its
        &ldquo;prelim&rdquo; is a seed time rather than a same-meet swim. Changes are a percentage of the
        prelim time so a 50 and a 500 are comparable.
        {partial.length > 0 && (
          <>
            {" "}
            <strong>{partial.join(", ")}</strong> {partial.length === 1 ? "has" : "have"} no
            consolation (B) final in the source data — only seeds 1&ndash;8 exist{" "}
            {partial.length === 1 ? "that year" : "those years"}, so raw totals there are not
            comparable to other seasons. Seed adjustment removes most, but not all, of that bias.
          </>
        )}
      </p>
    </>
  );
}

function SeedView({ rows, bands }) {
  return (
    <>
      <div className="card">
        <h3 style={{ margin: "0 0 4px" }}>Share going faster in the final, by prelim seed</h3>
        <ResponsiveContainer width="100%" height={330}>
          <ComposedChart data={rows} margin={{ top: 10, right: 20, bottom: 28, left: 4 }}>
            <CartesianGrid stroke="#eef0f3" vertical={false} />
            <XAxis
              dataKey="seedLabel" tick={{ fontSize: 12 }}
              label={{ value: "prelim seed", position: "insideBottom", offset: -14, fontSize: 12 }}
            />
            <YAxis
              yAxisId="l" domain={[0, 100]} tick={{ fontSize: 12 }} width={46}
              tickFormatter={(v) => `${v}%`}
            />
            <YAxis
              yAxisId="r" orientation="right" tick={{ fontSize: 12 }} width={54}
              tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`}
            />
            <ReferenceLine yAxisId="l" y={50} stroke={MUTED} strokeDasharray="4 4" />
            <ReferenceLine yAxisId="r" y={0} stroke="#e5e7eb" />
            <Tooltip
              contentStyle={TIP}
              formatter={(v, n) =>
                n === "% faster" ? [`${v}%`, n] : [pct(v), n]
              }
              labelFormatter={(l) => `Seed ${l}`}
            />
            <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
            <Bar yAxisId="l" dataKey="pct_faster" name="% faster" radius={[3, 3, 0, 0]}>
              {rows.map((r) => (
                <Cell key={r.seed} fill={r.pct_faster >= 50 ? GOOD : BAD} fillOpacity={0.75} />
              ))}
            </Bar>
            <Line
              yAxisId="r" type="monotone" dataKey="median" name="median change"
              stroke={ACCENT} strokeWidth={2} dot={{ r: 3 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
        <p className="note" style={{ marginTop: 6 }}>
          Dashed line is a coin flip. Bars above it are seeds that reliably improve at night.
        </p>
      </div>

      <div className="card">
        <h3 style={{ margin: "0 0 10px" }}>By seed band</h3>
        <table className="su-table">
          <thead>
            <tr><th>Seed</th><th>n</th><th>% faster</th><th>Median change</th></tr>
          </thead>
          <tbody>
            {bands.map((b) => (
              <tr key={b.band}>
                <td>{b.band}</td>
                <td className="num">{b.n}</td>
                <td className="num" style={{ color: b.pct_faster >= 50 ? GOOD : BAD }}>
                  {b.pct_faster}%
                </td>
                <td className="num" style={{ color: b.median > 0 ? GOOD : b.median < 0 ? BAD : "inherit" }}>
                  {pct(b.median)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function RankView({ rows, labelKey, title, minN, sorted = true }) {
  if (!rows.length) {
    return (
      <div className="card">
        <p className="sub">No groups met the minimum sample size{minN ? ` (${minN} swims)` : ""}.</p>
      </div>
    );
  }
  const chart = (sorted ? rows : rows).map((r) => ({ ...r, label: r[labelKey] }));

  return (
    <>
      <div className="card">
        <h3 style={{ margin: "0 0 4px" }}>Seed-adjusted step-up{minN ? ` (min ${minN} swims)` : ""}</h3>
        <ResponsiveContainer width="100%" height={Math.max(220, chart.length * 30 + 60)}>
          <BarChart data={chart} layout="vertical" margin={{ top: 10, right: 24, bottom: 24, left: 8 }}>
            <CartesianGrid stroke="#eef0f3" horizontal={false} />
            <XAxis
              type="number" tick={{ fontSize: 12 }}
              tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`}
              label={{ value: "median change vs. seed expectation", position: "insideBottom", offset: -12, fontSize: 12 }}
            />
            <YAxis type="category" dataKey="label" tick={{ fontSize: 12 }} width={92} />
            <ReferenceLine x={0} stroke="#6b7280" />
            <Tooltip
              contentStyle={TIP}
              formatter={(v, n, p) => [
                `${pct(v)}  (raw ${pct(p.payload.median)}, n=${p.payload.n})`,
                "vs. seed expectation",
              ]}
            />
            <Bar dataKey="median_adj" radius={[0, 3, 3, 0]}>
              {chart.map((r) => (
                <Cell key={r.label} fill={r.median_adj >= 0 ? GOOD : BAD} fillOpacity={0.8} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <table className="su-table">
          <thead>
            <tr>
              <th>{title}</th><th>n</th><th>% faster</th>
              <th>Raw median</th><th>vs. seed</th><th>% beating seed</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r[labelKey]}>
                <td>{r[labelKey]}</td>
                <td className="num">{r.n}</td>
                <td className="num">{r.pct_faster}%</td>
                <td className="num" style={{ color: MUTED }}>{pct(r.median)}</td>
                <td
                  className="num"
                  style={{ fontWeight: 600, color: r.median_adj > 0 ? GOOD : r.median_adj < 0 ? BAD : "inherit" }}
                >
                  {pct(r.median_adj)}
                </td>
                <td className="num">{r.pct_beat_seed}%</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note" style={{ marginTop: 8 }}>
          Compare the grey raw column with the bold adjusted one: where they diverge, the program&rsquo;s
          reputation for stepping up is mostly a reflection of how well it seeds.
        </p>
      </div>
    </>
  );
}

// The leaderboard is descriptive, not predictive — say so rather than let the
// ranking imply a durable program trait.
function Reliability({ rel }) {
  if (!rel || rel.r == null) return null;
  const strong = rel.r >= 0.3;
  return (
    <div className="card">
      <h3 style={{ margin: "0 0 6px" }}>Does this repeat?</h3>
      <div className="stat">
        <div className="stat-num" style={{ color: strong ? GOOD : BAD }}>
          r = {rel.r > 0 ? "+" : ""}{rel.r.toFixed(2)}
        </div>
        <div className="stat-label">
          split-half correlation across eras ({rel.split}), {rel.n_groups} programs
        </div>
      </div>
      <p className="note" style={{ marginTop: 0 }}>
        {strong ? (
          <>
            A program&rsquo;s early-era figure meaningfully predicts its later one, so this is
            behaving like a real, durable trait rather than year-to-year noise.
          </>
        ) : (
          <>
            <strong>Treat this leaderboard as descriptive, not predictive.</strong> Once seed is
            adjusted away, a program&rsquo;s early-era step-up barely predicts its later-era
            step-up. On the <em>raw</em> metric the same test looks much stronger (r &asymp; +0.35)
            — but that mostly reflects programs reliably recruiting swimmers who seed well, not
            athletes reliably beating their seeds. The ranking says what happened; it isn&rsquo;t
            evidence that a program will do it again.
          </>
        )}
      </p>
    </div>
  );
}

function YearStrip({ years, partial }) {
  return (
    <div className="card">
      <h3 style={{ margin: "0 0 10px" }}>Season by season</h3>
      <table className="su-table">
        <thead>
          <tr><th>Meet</th><th>n</th><th>% faster</th><th>Raw median</th><th>vs. seed</th></tr>
        </thead>
        <tbody>
          {years.map((y) => {
            const flag = partial.includes(y.year);
            return (
              <tr key={y.year}>
                <td>
                  {y.year}
                  {flag && <span className="badge" style={{ marginLeft: 8 }}>A final only</span>}
                </td>
                <td className="num">{y.n}</td>
                <td className="num">{y.pct_faster}%</td>
                <td className="num" style={{ color: MUTED }}>{pct(y.median)}</td>
                <td
                  className="num"
                  style={{ fontWeight: 600, color: y.median_adj > 0 ? GOOD : y.median_adj < 0 ? BAD : "inherit" }}
                >
                  {pct(y.median_adj)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
