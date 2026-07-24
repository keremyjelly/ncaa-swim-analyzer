import { useState } from "react";
import RaceTrends from "./RaceTrends";
import SwimmerTrends from "./SwimmerTrends";
import RaceAnalysis from "./RaceAnalysis";
import PrelimFinals from "./PrelimFinals";
import MatchUp from "./MatchUp";

const TABS = [
  { id: "race", label: "Race Trends" },
  { id: "swimmer", label: "Swimmer Trends" },
  { id: "analysis", label: "Race Analysis" },
  { id: "compare", label: "Prelims → Finals" },
  { id: "matchup", label: "Head-to-Head" },
];

const GENDERS = ["Men", "Women"];

export default function App() {
  const [tab, setTab] = useState("race");
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

      {tab === "race" && <RaceTrends gender={gender} />}
      {tab === "swimmer" && <SwimmerTrends gender={gender} />}
      {tab === "analysis" && <RaceAnalysis gender={gender} />}
      {tab === "compare" && <PrelimFinals gender={gender} />}
      {tab === "matchup" && <MatchUp gender={gender} />}

      <footer>Data: swim.db via FastAPI.</footer>
    </div>
  );
}
