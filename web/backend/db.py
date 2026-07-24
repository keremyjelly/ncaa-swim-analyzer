"""
Thin data-access layer over swim.db.

We use the stdlib sqlite3 driver directly (no ORM) so the queries stay
readable and you can see exactly what SQL runs. Every function opens a
short-lived read-only connection and returns plain dicts/lists that
FastAPI serializes to JSON for free.
"""

import os
import sqlite3
import sys
from functools import lru_cache

# swim.db lives at the repo root, two directories above this file.
# Override with the SWIM_DB_PATH env var if you move it.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_DB = os.path.join(_REPO_ROOT, "swim.db")
DB_PATH = os.environ.get("SWIM_DB_PATH", _DEFAULT_DB)

# names.py lives at the repo root next to create_csv.py (it's shared by the
# ingest pipeline), so the backend needs the root on sys.path to import it.
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from names import aka_names  # noqa: E402  (import needs the sys.path line above)


def _connect() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"swim.db not found at {DB_PATH}. Set SWIM_DB_PATH to point at it."
        )
    # uri=True + mode=ro opens read-only: the API can never mutate your data.
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=1)
def get_years() -> list[int]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT MEET_YEAR FROM results "
            "WHERE MEET_YEAR IS NOT NULL ORDER BY MEET_YEAR"
        ).fetchall()
    return [int(r["MEET_YEAR"]) for r in rows]


@lru_cache(maxsize=1)
def get_events() -> list[dict]:
    """Distinct events with light metadata, individual events first."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT EVENT_NAME   AS name,
                   EVENT_GENDER AS gender,
                   EVENT_DISTANCE AS distance,
                   EVENT_STROKE AS stroke,
                   MAX(IS_RELAY) AS is_relay,
                   COUNT(DISTINCT MEET_YEAR) AS years_present
            FROM results
            WHERE EVENT_NAME IS NOT NULL
            GROUP BY EVENT_NAME
            ORDER BY is_relay, EVENT_DISTANCE, EVENT_STROKE
            """
        ).fetchall()
    return [
        {
            "name": r["name"],
            "gender": r["gender"],
            "distance": r["distance"],
            "stroke": r["stroke"],
            "is_relay": bool(r["is_relay"]),
            "years_present": r["years_present"],
        }
        for r in rows
    ]


def get_event_trend(event_name: str) -> dict:
    """
    Year-over-year summary for one event:
      - winner_sec:   fastest final time that year
      - top16_avg_sec: mean of the (up to) 16 fastest final times that year
      - field_size:   how many timed finalists we have

    Returns {"event": ..., "points": [ {year, winner_sec, top16_avg_sec, field_size}, ... ]}.
    """
    with _connect() as conn:
        years = [
            int(r["MEET_YEAR"])
            for r in conn.execute(
                "SELECT DISTINCT MEET_YEAR FROM results "
                "WHERE EVENT_NAME = ? AND FINAL_TIME_SEC IS NOT NULL "
                "ORDER BY MEET_YEAR",
                (event_name,),
            ).fetchall()
        ]

        points = []
        for year in years:
            times = [
                r["FINAL_TIME_SEC"]
                for r in conn.execute(
                    "SELECT FINAL_TIME_SEC FROM results "
                    "WHERE EVENT_NAME = ? AND MEET_YEAR = ? "
                    "AND FINAL_TIME_SEC IS NOT NULL "
                    "ORDER BY FINAL_TIME_SEC ASC",
                    (event_name, year),
                ).fetchall()
            ]
            if not times:
                continue
            top16 = times[:16]
            points.append(
                {
                    "year": year,
                    "winner_sec": round(times[0], 2),
                    "top16_avg_sec": round(sum(top16) / len(top16), 2),
                    "field_size": len(times),
                }
            )

    return {"event": event_name, "points": points}


# ---------------------------------------------------------------------------
# Individual swimmers
#
# Identity is keyed on NAME. Deliberately NOT on name+school, because genuine
# transfers (e.g. Notre Dame -> SMU) would then split one athlete into two. A
# swimmer's school(s) are surfaced separately so transfers are visible rather
# than fragmenting.
#
# The name strings are NOT inherently consistent across years — a school may
# enter the same athlete as "Fallon, Matt" one season and "Fallon, Matthew" the
# next, which would fragment a career just as badly. That's corrected at ingest
# by names.canonical_name(); the superseded spellings are surfaced here as
# `also_known_as` so search can still match what someone was previously listed
# under. See names.py for the evidence behind each merge.
# ---------------------------------------------------------------------------


def get_swimmers(gender: str | None = None) -> list[dict]:
    """One entry per swimmer (individual events only), for the picker.

    Scoped by gender so a men's and women's swimmer who share a name aren't
    merged into one identity.
    """
    where = "WHERE IS_RELAY = 0 AND NAME IS NOT NULL"
    params: list = []
    if gender:
        where += " AND EVENT_GENDER = ?"
        params.append(gender)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT NAME AS name,
                   COUNT(*)                 AS swims,
                   COUNT(DISTINCT MEET_YEAR) AS years,
                   MIN(MEET_YEAR)           AS first_year,
                   MAX(MEET_YEAR)           AS last_year,
                   GROUP_CONCAT(DISTINCT SCHOOL) AS schools
            FROM results
            {where}
            GROUP BY NAME
            ORDER BY NAME COLLATE NOCASE
            """,
            params,
        ).fetchall()
    return [
        {
            "name": r["name"],
            "swims": r["swims"],
            "years": r["years"],
            "first_year": r["first_year"],
            "last_year": r["last_year"],
            "schools": sorted((r["schools"] or "").split(",")),
            "also_known_as": aka_names(r["name"]),
        }
        for r in rows
    ]


def get_swimmer_trend(name: str, gender: str | None = None) -> dict:
    """
    A swimmer's championship trajectory, grouped by event.

    For each (event, year) we keep *both* swims the swimmer recorded: the prelim
    and the final, each as its own object (or null if they didn't swim that
    session — e.g. a non-qualifier has only a prelim; a timed-final event like the
    1650 has only a final). This lets the UI draw prelim and final as two lines and
    show how much a swimmer dropped from morning to night. Returns:
      {"name": ..., "schools": [...],
       "events": [ {"event": ...,
                    "points": [ {year, prelim: {...}|null, final: {...}|null}, ... ]}, ... ]}
    where each swim object is {year, time_sec, place, section, points, reaction, school, splits}.

    Note: the swum time for either session is FINAL_TIME_SEC (the last time column
    HY-TEK prints), so on a prelims row it is the prelim swim, on a finals row the
    final swim.
    """
    where = "WHERE NAME = ? AND IS_RELAY = 0 AND FINAL_TIME_SEC IS NOT NULL"
    params: list = [name]
    if gender:
        where += " AND EVENT_GENDER = ?"
        params.append(gender)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT MEET_YEAR, EVENT_NAME, SECTION, PLACE, SCHOOL,
                   FINAL_TIME_SEC, POINTS, REACTION, SPLITS_50
            FROM results
            {where}
            ORDER BY EVENT_NAME, MEET_YEAR
            """,
            params,
        ).fetchall()

    schools = sorted({r["SCHOOL"] for r in rows if r["SCHOOL"]})

    def parse_splits(raw):
        """'21.36|44.92|...' -> [21.36, 44.92, ...]; skip non-numeric bits."""
        out = []
        for piece in (raw or "").split("|"):
            piece = piece.strip()
            if not piece:
                continue
            try:
                out.append(round(float(piece), 2))
            except ValueError:
                pass
        return out

    def swim_obj(r):
        return {
            "year": int(r["MEET_YEAR"]),
            "time_sec": round(r["FINAL_TIME_SEC"], 2),
            "place": int(r["PLACE"]) if r["PLACE"] is not None else None,
            "section": r["SECTION"],
            "points": r["POINTS"],
            "reaction": r["REACTION"],
            "school": r["SCHOOL"],
            "splits": parse_splits(r["SPLITS_50"]),
        }

    # event -> year -> {"year", "prelim": obj|None, "final": obj|None}
    events: dict[str, dict[int, dict]] = {}
    for r in rows:
        by_year = events.setdefault(r["EVENT_NAME"], {})
        year = int(r["MEET_YEAR"])
        cell = by_year.setdefault(year, {"year": year, "prelim": None, "final": None})
        slot = "prelim" if r["SECTION"] == "prelims" else "final"
        obj = swim_obj(r)
        # If a session somehow has more than one row, keep the fastest.
        if cell[slot] is None or obj["time_sec"] < cell[slot]["time_sec"]:
            cell[slot] = obj

    event_list = [
        {"event": event, "points": [by_year[y] for y in sorted(by_year)]}
        for event, by_year in sorted(events.items())
    ]

    return {"name": name, "schools": schools, "events": event_list}
