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
def swimmers():
    """All individual swimmers (name-keyed) for the picker."""
    return {"swimmers": db.get_swimmers()}


@app.get("/api/swimmers/trend")
def swimmer_trend(name: str = Query(..., description="Exact swimmer NAME, e.g. 'Lasco, Destin'")):
    """One swimmer's fastest time per event per year, across meets."""
    valid = {s["name"] for s in db.get_swimmers()}
    if name not in valid:
        raise HTTPException(status_code=404, detail=f"Unknown swimmer: {name!r}")
    return db.get_swimmer_trend(name)
