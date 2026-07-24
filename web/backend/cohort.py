"""
Class-year composition of the scoring field — the COVID 5th-year bubble.

The NCAA's blanket extra-eligibility grant for the 2020-21 season created a
cohort that shows up in the data as `5Y` and then washes out. Scoring share by
class year per season traces that wave in one chart.

Share, not raw points: the number of points on offer differs by year (and 2026
is missing its consolation finals entirely), so absolute totals aren't
comparable across seasons but shares mostly are.

Individual events only — relay rows have no single class year attached.

Note: this dataset contains only the `5Y` code, with no separate `GR`, so no
merging of graduate/5th-year codes is needed.
"""

from collections import defaultdict

from db import _connect

CLASS_ORDER = ["FR", "SO", "JR", "SR", "5Y"]


def class_share(gender: str):
    """Points share and swimmer count by class year, per meet year."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT MEET_YEAR y, YEAR cls, POINTS, NAME "
            "FROM results "
            "WHERE IS_RELAY = 0 AND EVENT_GENDER = ? "
            "  AND POINTS IS NOT NULL AND POINTS > 0 AND YEAR IS NOT NULL",
            (gender,),
        ).fetchall()

    pts = defaultdict(float)
    swimmers = defaultdict(set)
    for r in rows:
        pts[(int(r["y"]), r["cls"])] += float(r["POINTS"])
        swimmers[(int(r["y"]), r["cls"])].add(r["NAME"])

    all_years = sorted({y for y, _ in pts})
    classes = [c for c in CLASS_ORDER if any((y, c) in pts for y in all_years)]

    years = []
    for y in all_years:
        total = sum(pts[(y, c)] for c in classes)
        entry = {"year": y, "total_points": round(total, 1)}
        for c in classes:
            p = pts.get((y, c), 0.0)
            entry[c] = round(100.0 * p / total, 2) if total else 0.0
            entry[f"{c}_points"] = round(p, 1)
            entry[f"{c}_swimmers"] = len(swimmers.get((y, c), ()))
        years.append(entry)

    return {"gender": gender, "classes": classes, "years": years}
