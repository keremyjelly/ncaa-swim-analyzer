"""
Head-to-head matchups between any two swims of one event.

Pick an event, then two swims — each an independent (swimmer, year, prelim/final)
choice. The two sides can be different swimmers or the *same* swimmer in different
years (a personal-progress comparison), and the two years need not match: we align
the swims on their shared cumulative-distance marks so a 2021 swim (50-yd splits)
still lines up against a 2026 swim (25-yd splits) at the 50s they have in common.

roster(event) feeds the pickers; matchup(...) returns the race data:
  - each swim's per-segment splits and running cumulative time,
  - a `race` array over the shared marks with both cumulative times, both segment
    splits, and the running margin (how far swim A leads B at each wall),
  - the final margin.

The swum time and splits come from FINAL_TIME_SEC / SPLITS_50 (see db/compare for
the note on why the swum time lives in FINAL_TIME_SEC for both sessions).
"""

from db import _connect  # also puts the repo root on sys.path for `names`
from names import aka_names
from analysis import _splits, _marks, _event_distance


def roster(event):
    """Every swimmer in the event with their individual swims, for the pickers.

    `schools` and `best` are included so the picker can filter by team and show
    a swimmer's fastest swim without a second request. A swimmer who transferred
    has more than one school here — identity stays keyed on name, so their swims
    across programs stay together.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT NAME, SCHOOL, MEET_YEAR, SECTION, PLACE, FINAL_TIME_SEC "
            "FROM results "
            "WHERE EVENT_NAME = ? AND IS_RELAY = 0 AND FINAL_TIME_SEC IS NOT NULL "
            "ORDER BY NAME COLLATE NOCASE, MEET_YEAR, SECTION",
            (event,),
        ).fetchall()

    swimmers = {}
    for r in rows:
        s = swimmers.setdefault(r["NAME"], {"name": r["NAME"], "swims": [], "_schools": set()})
        if r["SCHOOL"]:
            s["_schools"].add(r["SCHOOL"])
        s["swims"].append({
            "year": int(r["MEET_YEAR"]),
            "section": "prelim" if r["SECTION"] == "prelims" else "final",
            "time_sec": round(r["FINAL_TIME_SEC"], 2),
            "place": int(r["PLACE"]) if r["PLACE"] is not None else None,
        })

    out = []
    for s in swimmers.values():
        s["schools"] = sorted(s.pop("_schools"))
        s["best"] = min(x["time_sec"] for x in s["swims"])
        s["also_known_as"] = aka_names(s["name"])
        out.append(s)
    return {"event": event, "swimmers": out}


def _load_swim(conn, event, name, year, section, distance):
    sec = "prelims" if section == "prelim" else "finals"
    r = conn.execute(
        "SELECT NAME, SCHOOL, MEET_YEAR, SECTION, PLACE, FINAL_TIME_SEC, "
        "POINTS, REACTION, SPLITS_50 "
        "FROM results "
        "WHERE EVENT_NAME = ? AND NAME = ? AND MEET_YEAR = ? AND SECTION = ? "
        "AND IS_RELAY = 0 "
        "ORDER BY FINAL_TIME_SEC LIMIT 1",
        (event, name, int(year), sec),
    ).fetchone()
    if r is None:
        return None

    splits = _splits(r["SPLITS_50"])
    marks = _marks(distance, len(splits)) if splits else []
    cum, running = [], 0.0
    for s in splits:
        running = round(running + s, 2)
        cum.append(running)

    return {
        "name": r["NAME"],
        "school": r["SCHOOL"],
        "year": int(r["MEET_YEAR"]),
        "section": section,
        "place": int(r["PLACE"]) if r["PLACE"] is not None else None,
        "time_sec": round(r["FINAL_TIME_SEC"], 2),
        "points": r["POINTS"],
        "reaction": r["REACTION"],
        "marks": marks,
        "cum": cum,
        "splits": [round(s, 2) for s in splits],
    }


def matchup(event, a_name, a_year, a_section, b_name, b_year, b_section):
    """Race data for two chosen swims, aligned on their shared distance marks."""
    with _connect() as conn:
        distance = _event_distance(conn, event)
        a = _load_swim(conn, event, a_name, a_year, a_section, distance)
        b = _load_swim(conn, event, b_name, b_year, b_section, distance)

    if a is None or b is None:
        return {"event": event, "distance": distance, "a": a, "b": b,
                "marks": [], "race": [], "final_margin": None}

    b_marks = set(b["marks"])
    common = [m for m in a["marks"] if m in b_marks]

    def cum_at(sw, mark):
        return sw["cum"][sw["marks"].index(mark)]

    race, pa, pb = [], 0.0, 0.0
    for m in common:
        ca, cb = cum_at(a, m), cum_at(b, m)
        race.append({
            "dist": m,
            "a_cum": round(ca, 2),
            "b_cum": round(cb, 2),
            "a_seg": round(ca - pa, 2),
            "b_seg": round(cb - pb, 2),
            "lead": round(cb - ca, 2),  # positive = swim A is ahead at this wall
        })
        pa, pb = ca, cb

    return {
        "event": event,
        "distance": distance,
        "marks": common,
        "a": a,
        "b": b,
        "race": race,
        "final_margin": round(a["time_sec"] - b["time_sec"], 2),  # + = A slower
    }
