"""
Race analyses computed from swim.db.

Splits are indexed by their cumulative distance (in yards), not by raw position.
This matters because the 100s changed granularity over the years — 2021-2023
recorded two 50-yard splits, 2024-2026 four 25-yard splits — so a distance index
puts the 50-split years' marks at 50 and 100 (not 25 and 50) and lines them up
correctly with the 25-split years.

  - split_distribution: pacing shape of one event, year over year (% vs the
    year's own average split), indexed by distance
  - split_place:        correlation of each split with final place, per year
  - reaction:           correlation of reaction time with place, year x event

Stats are pure-python (no numpy). Analyses use finals swims only.
"""

from collections import Counter

from db import _connect

STROKE_ORDER = {"Freestyle": 0, "Backstroke": 1, "Breaststroke": 2, "Butterfly": 3, "IM": 4}
STROKE_ABBR = {"Freestyle": "Free", "Backstroke": "Back", "Breaststroke": "Breast", "Butterfly": "Fly", "IM": "IM"}


def _reaction_events(conn):
    """All individual events (no relays), ordered by stroke then distance, with short labels."""
    rows = conn.execute(
        "SELECT DISTINCT EVENT_NAME, EVENT_DISTANCE, EVENT_STROKE FROM results "
        "WHERE IS_RELAY = 0 AND EVENT_NAME IS NOT NULL"
    ).fetchall()
    evs = []
    for r in rows:
        stroke, dist = r["EVENT_STROKE"], r["EVENT_DISTANCE"]
        label = f"{dist} {STROKE_ABBR.get(stroke, stroke)}"
        evs.append((STROKE_ORDER.get(stroke, 9), dist, label, r["EVENT_NAME"]))
    evs.sort()
    return [(label, name) for _, _, label, name in evs]


# --- helpers -----------------------------------------------------------------

def _mean(xs):
    return sum(xs) / len(xs)


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _splits(raw):
    out = []
    for piece in (raw or "").split("|"):
        piece = piece.strip()
        try:
            out.append(float(piece))
        except ValueError:
            pass
    return out


def _event_distance(conn, event):
    r = conn.execute(
        "SELECT EVENT_DISTANCE FROM results WHERE EVENT_NAME = ? AND EVENT_DISTANCE IS NOT NULL LIMIT 1",
        (event,),
    ).fetchone()
    return r["EVENT_DISTANCE"] if r else None


def _marks(distance, length):
    """Cumulative-distance endpoint of each split (yards)."""
    seg = distance / length if distance else 1
    return [round((i + 1) * seg) for i in range(length)]


def _years_with_splits(conn, event):
    return [
        int(r["MEET_YEAR"])
        for r in conn.execute(
            "SELECT DISTINCT MEET_YEAR FROM results "
            "WHERE EVENT_NAME = ? AND SECTION = 'finals' AND SPLITS_50 IS NOT NULL "
            "ORDER BY MEET_YEAR",
            (event,),
        ).fetchall()
    ]


# --- analyses ----------------------------------------------------------------

def split_distribution(event):
    with _connect() as conn:
        distance = _event_distance(conn, event)
        per_year, all_marks = [], set()

        for year in _years_with_splits(conn, event):
            rows = conn.execute(
                "SELECT SPLITS_50 FROM results "
                "WHERE EVENT_NAME = ? AND MEET_YEAR = ? AND SECTION = 'finals' AND PLACE <= 16",
                (event, year),
            ).fetchall()
            sets = [s for s in (_splits(r["SPLITS_50"]) for r in rows) if len(s) >= 2]
            if not sets:
                continue
            length = Counter(len(s) for s in sets).most_common(1)[0][0]
            sets = [s for s in sets if len(s) == length]
            if length < 2 or not sets:
                continue

            avg = [_mean([s[i] for s in sets]) for i in range(length)]
            total = sum(avg)
            avg_split = total / length
            rel = [round(100 * (a / avg_split - 1), 2) for a in avg]
            marks = _marks(distance, length)
            all_marks |= set(marks)
            half = length // 2
            per_year.append({
                "year": year, "n": len(sets), "length": length,
                "front_pct": round(100 * sum(avg[:half]) / total, 2),
                "back_pct": round(100 * sum(avg[half:]) / total, 2),
                "_m2r": dict(zip(marks, rel)),
            })

        marks = sorted(all_marks)
        years = [{
            "year": p["year"], "n": p["n"], "length": p["length"],
            "front_pct": p["front_pct"], "back_pct": p["back_pct"],
            "rel": [p["_m2r"].get(m) for m in marks],
        } for p in per_year]

    return {"event": event, "distance": distance, "marks": marks, "years": years}


def split_place(event):
    """Correlation of each split with final place, computed per year."""
    with _connect() as conn:
        distance = _event_distance(conn, event)
        per_year, all_marks = [], set()

        for year in _years_with_splits(conn, event):
            rows = conn.execute(
                "SELECT PLACE, SPLITS_50 FROM results "
                "WHERE EVENT_NAME = ? AND MEET_YEAR = ? AND SECTION = 'finals' AND PLACE IS NOT NULL",
                (event, year),
            ).fetchall()
            parsed = [(r["PLACE"], _splits(r["SPLITS_50"])) for r in rows]
            parsed = [(p, s) for p, s in parsed if len(s) >= 2]
            if len(parsed) < 3:
                continue
            length = Counter(len(s) for _, s in parsed).most_common(1)[0][0]
            parsed = [(p, s) for p, s in parsed if len(s) == length]
            if len(parsed) < 3:
                continue

            places = [p for p, _ in parsed]
            corr = []
            for i in range(length):
                r = _pearson(places, [s[i] for _, s in parsed])
                corr.append(round(r, 3) if r is not None else None)
            marks = _marks(distance, length)
            all_marks |= set(marks)
            per_year.append({"year": year, "n": len(parsed), "_m2c": dict(zip(marks, corr))})

        marks = sorted(all_marks)
        years = [{
            "year": p["year"], "n": p["n"],
            "corr": [p["_m2c"].get(m) for m in marks],
        } for p in per_year]

    return {"event": event, "distance": distance, "marks": marks, "years": years}


def reaction():
    """Reaction-time vs place correlation for every year x individual event."""
    with _connect() as conn:
        events = _reaction_events(conn)
        labels = [lbl for lbl, _ in events]
        years = [
            int(r["MEET_YEAR"])
            for r in conn.execute(
                "SELECT DISTINCT MEET_YEAR FROM results WHERE MEET_YEAR IS NOT NULL ORDER BY MEET_YEAR"
            ).fetchall()
        ]
        rows = []
        for year in years:
            corr = []
            for _, event in events:
                r = conn.execute(
                    "SELECT PLACE, REACTION FROM results "
                    "WHERE EVENT_NAME = ? AND MEET_YEAR = ? AND SECTION = 'finals' "
                    "AND PLACE <= 16 AND REACTION IS NOT NULL AND PLACE IS NOT NULL",
                    (event, year),
                ).fetchall()
                places = [x["PLACE"] for x in r]
                reacts = [x["REACTION"] for x in r]
                c = _pearson(places, reacts) if len(places) >= 3 else None
                corr.append({"value": round(c, 3) if c is not None else None, "n": len(places)})
            rows.append({"year": year, "cells": corr})

    return {"events": labels, "rows": rows}
