"""
Prelims -> Finals comparisons computed from swim.db.

Every finalist swam twice at the meet: once in prelims, once in the final. This
module pairs those two swims for each swimmer (matched on year + name + school
within one event) and derives how the final differed from the morning swim:

  - time_drop:     prelim time vs final time — how much faster the final was,
                   and how many swimmers actually improved, per year.
  - rank_movement: prelim (seed) place vs final place — who moved up, who faded.
  - pacing:        per-split average delta (prelim split - final split, seconds),
                   indexed by cumulative distance — *where* in the race the drop
                   comes from (front half vs back half).

Why this needs the prelims pages: a finalist's prelim time appears on the finals
page only as a bare column number, with no splits. Their prelim *splits* and
reaction live solely on the prelims (P) page, so pacing comparison is impossible
without them.

Note on the swum time: for both a prelims row and a finals row, the time actually
swum in that session is FINAL_TIME_SEC (the last time column HY-TEK prints). On a
prelims row FINAL_TIME_SEC is therefore the prelim swim; on a finals row it is the
final swim. Splits are per-segment (incremental) times that sum to that swum time.

Analyses reuse the split helpers and cumulative-distance indexing from analysis.py
so the 100s' 2024 switch from 50- to 25-yard splits lines up across years.
"""

from collections import Counter

from db import _connect
from analysis import _splits, _marks, _event_distance, _mean


def _paired(conn, event):
    """Return one dict per finalist who also has a prelim swim, with both swims.

    Keyed match is (MEET_YEAR, NAME, SCHOOL): within a single meet a swimmer has
    at most one prelim and one final row per event, so this pairs them uniquely.
    School is stable within a meet, so including it avoids ever crossing two
    same-named swimmers.
    """
    finals = conn.execute(
        "SELECT MEET_YEAR y, NAME, SCHOOL, PLACE, FINAL_TIME_SEC, SPLITS_50 "
        "FROM results "
        "WHERE EVENT_NAME = ? AND SECTION = 'finals' AND IS_RELAY = 0 "
        "AND FINAL_TIME_SEC IS NOT NULL AND PLACE IS NOT NULL",
        (event,),
    ).fetchall()
    prelims = conn.execute(
        "SELECT MEET_YEAR y, NAME, SCHOOL, PLACE, FINAL_TIME_SEC, SPLITS_50 "
        "FROM results "
        "WHERE EVENT_NAME = ? AND SECTION = 'prelims' AND IS_RELAY = 0",
        (event,),
    ).fetchall()

    pmap = {(r["y"], r["NAME"], r["SCHOOL"]): r for r in prelims}
    out = []
    for f in finals:
        p = pmap.get((f["y"], f["NAME"], f["SCHOOL"]))
        if p is None:
            continue
        out.append({
            "year": int(f["y"]),
            "name": f["NAME"],
            "school": f["SCHOOL"],
            "final_place": int(f["PLACE"]),
            "prelim_place": int(p["PLACE"]) if p["PLACE"] is not None else None,
            "final_sec": f["FINAL_TIME_SEC"],
            "prelim_sec": p["FINAL_TIME_SEC"],  # the swum prelim time
            "final_splits": _splits(f["SPLITS_50"]),
            "prelim_splits": _splits(p["SPLITS_50"]),
        })
    return out


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return None
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def time_drop(event):
    """Prelim vs final swum time for each finalist, aggregated per year.

    drop = prelim_sec - final_sec, so positive = the final was faster (the norm).
    """
    with _connect() as conn:
        distance = _event_distance(conn, event)
        pairs = [p for p in _paired(conn, event) if p["prelim_sec"] is not None]

    by_year = {}
    for p in pairs:
        by_year.setdefault(p["year"], []).append(p)

    years = []
    for y in sorted(by_year):
        ps = by_year[y]
        drops = [p["prelim_sec"] - p["final_sec"] for p in ps]
        improved = sum(1 for d in drops if d > 0)
        swimmers = [
            {
                "name": p["name"],
                "school": p["school"],
                "prelim_place": p["prelim_place"],
                "final_place": p["final_place"],
                "prelim_sec": round(p["prelim_sec"], 2),
                "final_sec": round(p["final_sec"], 2),
                "drop": round(p["prelim_sec"] - p["final_sec"], 2),
            }
            for p in sorted(ps, key=lambda x: x["final_place"])
        ]
        years.append({
            "year": y,
            "n": len(ps),
            "mean_drop": round(_mean(drops), 2),
            "median_drop": round(_median(drops), 2),
            "pct_improved": round(100 * improved / len(drops), 1),
            "swimmers": swimmers,
        })

    return {"event": event, "distance": distance, "years": years}


def meet_drop(gender):
    """Every finalist's prelim vs final swim across all individual events, per year.

    This powers the "whole meet" scatter: one point per finalist per event. Times
    span the 50 to the 500, so the frontend plots them on log-log axes where every
    event lines up along the y=x diagonal. pct = how much faster the final was, as
    a share of the prelim time, which is scale-free and comparable across events.
    """
    with _connect() as conn:
        events = [
            r["EVENT_NAME"]
            for r in conn.execute(
                "SELECT DISTINCT EVENT_NAME FROM results "
                "WHERE IS_RELAY = 0 AND EVENT_GENDER = ? "
                "AND EVENT_DISTANCE IS NOT NULL AND EVENT_DISTANCE != 1650",
                (gender,),
            ).fetchall()
        ]
        by_year = {}
        for ev in events:
            for p in _paired(conn, ev):
                if p["prelim_sec"] is None or p["prelim_sec"] <= 0:
                    continue
                by_year.setdefault(p["year"], []).append({
                    "event": ev,
                    "name": p["name"],
                    "school": p["school"],
                    "final_place": p["final_place"],
                    "prelim_sec": round(p["prelim_sec"], 2),
                    "final_sec": round(p["final_sec"], 2),
                    "pct": round(100 * (p["prelim_sec"] - p["final_sec"]) / p["prelim_sec"], 2),
                })

    years = []
    for y in sorted(by_year):
        swims = by_year[y]
        improved = sum(1 for s in swims if s["pct"] > 0)
        years.append({
            "year": y,
            "n": len(swims),
            "pct_improved": round(100 * improved / len(swims), 1),
            "swims": swims,
        })
    return {"gender": gender, "years": years}


def rank_movement(event):
    """Prelim (seed) place vs final place for each finalist, per year."""
    with _connect() as conn:
        pairs = [p for p in _paired(conn, event) if p["prelim_place"] is not None]

    by_year = {}
    for p in pairs:
        by_year.setdefault(p["year"], []).append({
            "name": p["name"],
            "school": p["school"],
            "prelim_place": p["prelim_place"],
            "final_place": p["final_place"],
            "prelim_sec": round(p["prelim_sec"], 2) if p["prelim_sec"] is not None else None,
            "final_sec": round(p["final_sec"], 2),
            "move": p["prelim_place"] - p["final_place"],  # + = moved up
        })

    years = [
        {"year": y, "swimmers": sorted(by_year[y], key=lambda x: x["final_place"])}
        for y in sorted(by_year)
    ]
    return {"event": event, "years": years}


def pacing(event):
    """Average per-split delta (prelim - final, seconds) indexed by distance.

    Positive at a mark = finalists, on average, swam that segment faster in the
    final than in prelims. Only swimmers whose prelim and final swims have the
    same number of splits that year are used (they always should within a year).
    """
    with _connect() as conn:
        distance = _event_distance(conn, event)
        pairs = _paired(conn, event)

    by_year = {}
    for p in pairs:
        by_year.setdefault(p["year"], []).append(p)

    per_year, all_marks = [], set()
    for y in sorted(by_year):
        valid = [
            p for p in by_year[y]
            if len(p["prelim_splits"]) >= 2
            and len(p["prelim_splits"]) == len(p["final_splits"])
        ]
        if not valid:
            continue
        length = Counter(len(p["final_splits"]) for p in valid).most_common(1)[0][0]
        valid = [p for p in valid if len(p["final_splits"]) == length]
        if not valid:
            continue

        delta = [
            round(_mean([p["prelim_splits"][i] - p["final_splits"][i] for p in valid]), 3)
            for i in range(length)
        ]
        total_drop = round(sum(delta), 2)
        half = length // 2
        marks = _marks(distance, length)
        all_marks |= set(marks)
        per_year.append({
            "year": y,
            "n": len(valid),
            "length": length,
            "total_drop": total_drop,
            "front_drop": round(sum(delta[:half]), 2),
            "back_drop": round(sum(delta[half:]), 2),
            "_m2d": dict(zip(marks, delta)),
        })

    marks = sorted(all_marks)
    years = [
        {
            "year": p["year"], "n": p["n"], "total_drop": p["total_drop"],
            "front_drop": p["front_drop"], "back_drop": p["back_drop"],
            "delta": [p["_m2d"].get(m) for m in marks],
        }
        for p in per_year
    ]
    return {"event": event, "distance": distance, "marks": marks, "years": years}
