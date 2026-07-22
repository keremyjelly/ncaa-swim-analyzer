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
