"""
FastAPI app serving NCAA swim data out of swim.db.

Run locally:
    cd web/backend
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Interactive API docs are auto-generated at http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import db
import analysis
import compare
import matchup as matchup_mod

app = FastAPI(
    title="NCAA Swim Analyzer API",
    version="0.1.0",
    description="Race and individual trend data from the NCAA Championships.",
)

# Allow the Vite dev server (localhost:5173) to call the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "db": db.DB_PATH}


@app.get("/api/meta")
def meta():
    """Years available in the dataset."""
    return {"years": db.get_years()}


@app.get("/api/events")
def events():
    """All events with light metadata (individual events first)."""
    return {"events": db.get_events()}


@app.get("/api/events/trend")
def event_trend(event: str = Query(..., description="Exact EVENT_NAME, e.g. 'Men 100 Yard Freestyle'")):
    """Winner + top-16 average final time per year for a single event."""
    valid = {e["name"] for e in db.get_events()}
    if event not in valid:
        raise HTTPException(status_code=404, detail=f"Unknown event: {event!r}")
    return db.get_event_trend(event)


@app.get("/api/swimmers")
def swimmers(gender: str | None = None):
    """Individual swimmers (name-keyed) for the picker, optionally by gender."""
    return {"swimmers": db.get_swimmers(gender)}


@app.get("/api/swimmers/trend")
def swimmer_trend(
    name: str = Query(..., description="Exact swimmer NAME, e.g. 'Lasco, Destin'"),
    gender: str | None = None,
):
    """One swimmer's fastest time per event per year, across meets."""
    valid = {s["name"] for s in db.get_swimmers(gender)}
    if name not in valid:
        raise HTTPException(status_code=404, detail=f"Unknown swimmer: {name!r}")
    return db.get_swimmer_trend(name, gender)


# --- race analyses -----------------------------------------------------------

def _check_event(event: str) -> None:
    if event not in {e["name"] for e in db.get_events()}:
        raise HTTPException(status_code=404, detail=f"Unknown event: {event!r}")


@app.get("/api/analysis/split-distribution")
def analysis_split_distribution(event: str = Query(..., description="Exact EVENT_NAME")):
    """Pacing shape of one event, year over year (% vs the year's avg split)."""
    _check_event(event)
    return analysis.split_distribution(event)


@app.get("/api/analysis/split-place")
def analysis_split_place(event: str = Query(..., description="Exact EVENT_NAME")):
    """Correlation of each split with final place, per year, for one event."""
    _check_event(event)
    return analysis.split_place(event)


@app.get("/api/analysis/reaction")
def analysis_reaction(gender: str = "Men"):
    """Reaction-time vs place correlation for every year x event, one gender."""
    return analysis.reaction(gender)


# --- prelims -> finals comparisons -------------------------------------------

@app.get("/api/compare/time-drop")
def compare_time_drop(event: str = Query(..., description="Exact EVENT_NAME")):
    """Prelim vs final swum time for each finalist, aggregated per year."""
    _check_event(event)
    return compare.time_drop(event)


@app.get("/api/compare/rank-movement")
def compare_rank_movement(event: str = Query(..., description="Exact EVENT_NAME")):
    """Prelim (seed) place vs final place for each finalist, per year."""
    _check_event(event)
    return compare.rank_movement(event)


@app.get("/api/compare/pacing")
def compare_pacing(event: str = Query(..., description="Exact EVENT_NAME")):
    """Per-split average delta (prelim - final) indexed by distance, per year."""
    _check_event(event)
    return compare.pacing(event)


@app.get("/api/compare/meet-drop")
def compare_meet_drop(gender: str = "Men"):
    """Every finalist's prelim vs final swim across all events, per year (one gender)."""
    return compare.meet_drop(gender)


# --- head-to-head matchup ----------------------------------------------------

@app.get("/api/events/roster")
def events_roster(event: str = Query(..., description="Exact EVENT_NAME")):
    """Swimmers in one event with their individual swims, for the matchup pickers."""
    _check_event(event)
    return matchup_mod.roster(event)


@app.get("/api/matchup")
def matchup_endpoint(
    event: str = Query(..., description="Exact EVENT_NAME"),
    aName: str = Query(...), aYear: int = Query(...), aSection: str = Query(...),
    bName: str = Query(...), bYear: int = Query(...), bSection: str = Query(...),
):
    """Race data for two chosen swims (swimmer + year + prelim/final each)."""
    _check_event(event)
    return matchup_mod.matchup(event, aName, aYear, aSection, bName, bYear, bSection)
