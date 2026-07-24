import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { fetchTrend, formatTime } from "./api";

// Winner + top-16 average final time by year for one event.
//
// The event picker lives in the Race Analysis umbrella (this is one of its
// sub-views), so `event` arrives as a prop and this component only owns the
// trend fetch for whatever event it's handed.
export default function RaceTrends({ event }) {
  const [trend, setTrend] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!event) return;
    setTrend(null);
    setError(null);
    fetchTrend(event)
      .then(setTrend)
      .catch((e) =>
        setError(`Couldn't reach the API (${e.message}). Is the backend running on :8000?`)
      );
  }, [event]);

  const points = trend?.points ?? [];

  const delta = useMemo(() => {
    if (points.length < 2) return null;
    const first = points[0];
    const last = points[points.length - 1];
    return { first, last, drop: first.winner_sec - last.winner_sec };
  }, [points]);

  if (error) return <div className="error">{error}</div>;

  return (
    <div>
      {delta && (
        <div className="stat">
          <span className="stat-num">{delta.drop >= 0 ? "−" : "+"}{Math.abs(delta.drop).toFixed(2)}s</span>
          <span className="stat-label">
            winning time {delta.drop >= 0 ? "faster" : "slower"} ({delta.first.year}&nbsp;→&nbsp;{delta.last.year}):
            {" "}{formatTime(delta.first.winner_sec)} → {formatTime(delta.last.winner_sec)}
          </span>
        </div>
      )}

      <div className="card">
        {points.length === 0 ? (
          <div className="loading">Loading…</div>
        ) : (
          <ResponsiveContainer width="100%" height={420}>
            <LineChart data={points} margin={{ top: 16, right: 24, bottom: 8, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="year" />
              <YAxis domain={["auto", "auto"]} reversed tickFormatter={formatTime} width={70}
                label={{ value: "Time (faster ↑)", angle: -90, position: "insideLeft", style: { fill: "#888" } }} />
              <Tooltip formatter={(v, n) => [formatTime(v), n]} labelFormatter={(y) => `${y} Championships`} />
              <Legend />
              <Line type="monotone" dataKey="winner_sec" name="Winner" stroke="#DC143C" strokeWidth={2.5} dot={{ r: 4 }} />
              <Line type="monotone" dataKey="top16_avg_sec" name="Top-16 average" stroke="#4169E1" strokeWidth={2.5} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <p className="note">Y-axis reversed so faster (lower) times sit higher.</p>
    </div>
  );
}
