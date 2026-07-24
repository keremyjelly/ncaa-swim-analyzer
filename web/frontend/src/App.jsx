import { useState } from "react";
import SwimmerTrends from "./SwimmerTrends";
import RaceAnalysis from "./RaceAnalysis";
import PrelimFinals from "./PrelimFinals";
import MatchUp from "./MatchUp";
import Eligibility from "./Eligibility";

const TABS = [
  // Umbrella: season trend for one event plus the split/reaction analyses.
  { id: "analysis", label: "Race Analysis" },
  { id: "swimmer", label: "Swimmer Trends" },
  // Umbrella: per-event drill-downs plus the meet-wide seed-adjusted step-up views.
  { id: "compare", label: "Prelims → Finals" },
  { id: "matchup", label: "Head-to-Head" },
  { id: "eligibility", label: "5th-Year Bubble" },
];

const GENDERS = ["Men", "Women"];

export default function App() {
  const [tab, setTab] = useState(TABS[0].id);
  const [gender, setGender] = useState("Men");

  return (
    <div className="page">
      <header className="app-header">
        <div>
          <h1>NCAA Swim Analyzer</h1>
          <p className="sub">{gender}'s Championships, 2021&ndash;2026</p>
        </div>
        <div className="gender-switch">
          {GENDERS.map((g) => (
            <button key={g} className={gender === g ? "gbtn active" : "gbtn"} onClick={() => setGender(g)}>
              {g}
            </button>
          ))}
        </div>
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

      {tab === "analysis" && <RaceAnalysis gender={gender} />}
      {tab === "swimmer" && <SwimmerTrends gender={gender} />}
      {tab === "compare" && <PrelimFinals gender={gender} />}
      {tab === "matchup" && <MatchUp gender={gender} />}
      {tab === "eligibility" && <Eligibility gender={gender} />}

      <footer>Data: swim.db via FastAPI.</footer>
    </div>
  );
}
