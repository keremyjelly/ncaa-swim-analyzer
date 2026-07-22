"""
Thin data-access layer over swim.db.

We use the stdlib sqlite3 driver directly (no ORM) so the queries stay
readable and you can see exactly what SQL runs. Every function opens a
short-lived read-only connection and returns plain dicts/lists that
FastAPI serializes to JSON for free.
"""

import os
import sqlite3
from functools import lru_cache

# swim.db lives at the repo root, two directories above this file.
# Override with the SWIM_DB_PATH env var if you move it.
_DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "swim.db",
)
DB_PATH = os.environ.get("SWIM_DB_PATH", _DEFAULT_DB)


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
# Identity is keyed on NAME. The name strings in this dataset are clean and
# consistent across years (no case/spacing variants), so an exact NAME match
# reliably links a swimmer's results across meets. Deliberately NOT keying on
# name+school, because genuine transfers (e.g. Notre Dame -> SMU) would then
# split one athlete into two. A swimmer's school(s) are surfaced separately so
# transfers are visible rather than fragmenting.
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
        }
        for r in rows
    ]


def get_swimmer_trend(name: str, gender: str | None = None) -> dict:
    """
    A swimmer's championship trajectory, grouped by event.

    For each (event, year) we keep the swimmer's *fastest* timed swim that year
    (min final time across prelims/finals), so the series reflects their best
    performance per season. Returns:
      {"name": ..., "schools": [...],
       "events": [ {"event": ..., "points": [ {year, time_sec, place, section}, ... ]}, ... ]}
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

    # event -> year -> best row (lowest FINAL_TIME_SEC)
    events: dict[str, dict[int, dict]] = {}
    for r in rows:
        best = events.setdefault(r["EVENT_NAME"], {})
        cur = best.get(r["MEET_YEAR"])
        if cur is None or r["FINAL_TIME_SEC"] < cur["time_sec"]:
            best[r["MEET_YEAR"]] = {
                "year": int(r["MEET_YEAR"]),
                "time_sec": round(r["FINAL_TIME_SEC"], 2),
                "place": int(r["PLACE"]) if r["PLACE"] is not None else None,
                "section": r["SECTION"],
                "points": r["POINTS"],
                "reaction": r["REACTION"],
                "school": r["SCHOOL"],
                "splits": parse_splits(r["SPLITS_50"]),
            }

    event_list = [
        {"event": event, "points": [by_year[y] for y in sorted(by_year)]}
        for event, by_year in sorted(events.items())
    ]

    return {"name": name, "schools": schools, "events": event_list}
