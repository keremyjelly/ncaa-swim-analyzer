import { useState } from "react";
import RaceTrends from "./RaceTrends";
import SwimmerTrends from "./SwimmerTrends";
import RaceAnalysis from "./RaceAnalysis";

const TABS = [
  { id: "race", label: "Race Trends" },
  { id: "swimmer", label: "Swimmer Trends" },
  { id: "analysis", label: "Race Analysis" },
];

export default function App() {
  const [tab, setTab] = useState("race");

  return (
    <div className="page">
      <header>
        <h1>NCAA Swim Analyzer</h1>
        <p className="sub">Men's Championships, 2021&ndash;2026</p>
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "tab active" : "tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "race" && <RaceTrends />}
      {tab === "swimmer" && <SwimmerTrends />}
      {tab === "analysis" && <RaceAnalysis />}

      <footer>Data: swim.db via FastAPI.</footer>
    </div>
  );
}
