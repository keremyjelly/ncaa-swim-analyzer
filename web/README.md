# NCAA Swim Analyzer — Web Dashboard

A FastAPI backend + React (Vite) frontend that turns `swim.db` into an
interactive, browser-based dashboard. This is the first vertical slice:
**race trends over the years** (winner + top-16 average time per event,
2021–2026). The architecture is built to grow into individual-swimmer
trends, pacing views, and more.

```
web/
  backend/     FastAPI app reading swim.db (read-only)
    main.py        routes
    db.py          SQL queries -> plain dicts
    requirements.txt
  frontend/    Vite + React + Recharts
    src/
      App.jsx      the dashboard UI
      api.js       backend calls + time formatting
      index.css    styling
```

## Run it (two terminals)

**1. Backend** — from the repo root:

```bash
cd web/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Check it's alive: <http://localhost:8000/api/health> — and the auto-generated
API docs at <http://localhost:8000/docs>.

**2. Frontend** — in a second terminal:

```bash
cd web/frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Pick an event from the dropdown and the chart
updates. The y-axis is reversed so faster (lower) times sit higher.

## How the pieces talk

`App.jsx` calls `api.js`, which fetches JSON from FastAPI (`:8000`). The
backend's CORS config only allows the Vite dev origin (`:5173`). `db.py`
opens `swim.db` **read-only** — the API can never mutate your data.

The database path defaults to `swim.db` at the repo root; override with the
`SWIM_DB_PATH` environment variable. The frontend's API base defaults to
`http://localhost:8000`; override with `VITE_API_BASE`.

## API (v0.1)

| Endpoint | Returns |
| --- | --- |
| `GET /api/health` | status + resolved db path |
| `GET /api/meta` | `{ years: [...] }` |
| `GET /api/events` | all events with metadata (individual events first) |
| `GET /api/events/trend?event=<EVENT_NAME>` | winner + top-16 avg final time per year |

## Next steps (natural extensions)

- **Individual trends** — the hard-but-high-value one. Needs a swimmer-identity
  layer so `Foster, Carson` resolves to one athlete across years; then an
  `/api/swimmers/{id}/trend` endpoint + a swimmer page.
- **Port the 5 existing analyses** (200 pacing, 100 split correlation, reaction
  time, 400 IM legs) from `analyze.py` into API endpoints + interactive charts.
- **Women's results** — extend the data pipeline, then everything above works
  for both genders via the existing `EVENT_GENDER` column.
- **Deploy** — build the frontend (`npm run build`) and serve it; host the API.
```
