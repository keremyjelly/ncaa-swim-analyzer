"""
"Who steps up in finals" — seed-adjusted prelim -> final performance.

The naive version of this question ("what share of finalists go faster at
night?") gives ~57%, which sounds like a coin flip and hides the real
structure. Step-up is overwhelmingly a function of *prelim seed*:

    seed  1     81% go faster    median -0.72%
    seeds 2-4   72%                     -0.49%
    seeds 5-8   57%                     -0.14%
    seeds 9-12  47%                     +0.02%
    seeds 13-16 48%                     +0.01%

So a program that sends lots of top seeds will look like it "steps up" even
if every one of its swimmers performs exactly as their seed predicts. To
separate real over-performance from seed composition, every swim here is
scored against the pooled median for its seed:

    adj = pct_faster - baseline[seed]

adj > 0 means the swimmer beat what a swimmer off that seed typically does.
Program and class-year rankings use adj; the seed curve itself is exposed so
the frontend can show the effect being adjusted away.

Scope decisions:
  - individual events only; the 1650 is EXCLUDED because it is a timed final,
    so its "prelim" is a seed time from another meet rather than a same-meet
    swim (in 2022 that column is also mis-parsed).
  - deltas are a PERCENTAGE of the prelim time, not raw seconds, so a 500 and
    a 50 are comparable.
  - 2026 has no consolation (B) final in the source data — only seeds 1-8
    exist that year. Cross-year views are flagged via `partial_years` so the
    frontend can mark it; seed adjustment already removes most of the
    resulting bias, since the missing swimmers are the ones with ~0 baseline.
"""

from collections import defaultdict

from db import _connect

# Seeds 1-16 make a final; anything beyond is a data oddity (swim-off, tie).
MAX_SEED = 16

SEED_BANDS = [
    ("1", 1, 1),
    ("2-4", 2, 4),
    ("5-8", 5, 8),
    ("9-12", 9, 12),
    ("13-16", 13, 16),
]

CLASS_ORDER = ["FR", "SO", "JR", "SR", "5Y"]


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return None
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _band(seed):
    for label, lo, hi in SEED_BANDS:
        if lo <= seed <= hi:
            return label
    return None


def _swims(conn, gender):
    """Every usable finals swim for one gender, with seed and pct improvement.

    Pairs the finals row with the swimmer's prelims row on (meet, name, school)
    — the same key compare._paired uses. The prelims row is preferred over the
    finals row's PRELIM_TIME column because it also carries the true prelim
    PLACE, which is the seed.
    """
    finals = conn.execute(
        "SELECT MEET_YEAR y, NAME, SCHOOL, YEAR class, EVENT_NAME, "
        "       FINAL_TIME_SEC, PLACE "
        "FROM results "
        "WHERE SECTION = 'finals' AND IS_RELAY = 0 AND EVENT_GENDER = ? "
        "  AND EVENT_DISTANCE IS NOT NULL AND EVENT_DISTANCE != 1650 "
        "  AND FINAL_TIME_SEC IS NOT NULL",
        (gender,),
    ).fetchall()
    prelims = conn.execute(
        "SELECT MEET_YEAR y, NAME, SCHOOL, EVENT_NAME, FINAL_TIME_SEC, PLACE "
        "FROM results "
        "WHERE SECTION = 'prelims' AND IS_RELAY = 0 AND EVENT_GENDER = ? "
        "  AND EVENT_DISTANCE IS NOT NULL AND EVENT_DISTANCE != 1650",
        (gender,),
    ).fetchall()

    pmap = {(r["y"], r["NAME"], r["SCHOOL"], r["EVENT_NAME"]): r for r in prelims}

    out = []
    for f in finals:
        p = pmap.get((f["y"], f["NAME"], f["SCHOOL"], f["EVENT_NAME"]))
        if p is None or p["FINAL_TIME_SEC"] is None or p["FINAL_TIME_SEC"] <= 0:
            continue
        if p["PLACE"] is None:
            continue
        seed = int(p["PLACE"])
        if not 1 <= seed <= MAX_SEED:
            continue
        prelim_sec = p["FINAL_TIME_SEC"]   # time actually swum in prelims
        final_sec = f["FINAL_TIME_SEC"]    # time actually swum in the final
        out.append({
            "year": int(f["y"]),
            "name": f["NAME"],
            "school": f["SCHOOL"],
            "cls": f["class"],
            "event": f["EVENT_NAME"],
            "seed": seed,
            "final_place": int(f["PLACE"]) if f["PLACE"] is not None else None,
            "prelim_sec": round(prelim_sec, 2),
            "final_sec": round(final_sec, 2),
            # + = faster in the final
            "pct": 100.0 * (prelim_sec - final_sec) / prelim_sec,
        })
    return out


def _baseline(swims):
    """Pooled median pct improvement per seed — the curve we adjust away.

    Falls back to the seed's band median where a single seed is thin, so a
    sparse seed can't produce a wild baseline.
    """
    by_seed = defaultdict(list)
    by_band = defaultdict(list)
    for s in swims:
        by_seed[s["seed"]].append(s["pct"])
        by_band[_band(s["seed"])].append(s["pct"])

    base = {}
    for seed in range(1, MAX_SEED + 1):
        vals = by_seed.get(seed, [])
        if len(vals) >= 30:
            base[seed] = _median(vals)
        else:
            band_vals = by_band.get(_band(seed), [])
            base[seed] = _median(band_vals) if band_vals else 0.0
    return base


def _summary(items):
    """n / %faster / median raw / median seed-adjusted for a group of swims."""
    if not items:
        return None
    pcts = [i["pct"] for i in items]
    adjs = [i["adj"] for i in items]
    return {
        "n": len(items),
        "pct_faster": round(100.0 * sum(1 for p in pcts if p > 0) / len(pcts), 1),
        "median": round(_median(pcts), 3),
        "median_adj": round(_median(adjs), 3),
        "pct_beat_seed": round(100.0 * sum(1 for a in adjs if a > 0) / len(adjs), 1),
    }


def _reliability(swims, key="school", split_year=2023, min_half=15):
    """Split-half correlation of a group's mean adjusted step-up: early vs late era.

    This is the honesty check on the program leaderboard. If "stepping up" were a
    durable program trait, a program's 2021-23 figure would predict its 2024-26
    figure. Measured on the RAW metric it looks like signal (r ~ +0.35), but that
    is mostly programs reliably sending good seeds. On the seed-adjusted metric
    it drops to weak, so the leaderboard describes what happened rather than
    predicting what a program will do next.
    """
    early, late = defaultdict(list), defaultdict(list)
    for s in swims:
        (early if s["year"] <= split_year else late)[s[key]].append(s["adj"])
    common = [
        k for k in early
        if k in late and len(early[k]) >= min_half and len(late[k]) >= min_half
    ]
    if len(common) < 4:
        return {"n_groups": len(common), "r": None, "verdict": "insufficient data"}

    a = [sum(early[k]) / len(early[k]) for k in common]
    b = [sum(late[k]) / len(late[k]) for k in common]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    if not den:
        return {"n_groups": len(common), "r": None, "verdict": "insufficient data"}
    r = num / den
    return {
        "n_groups": len(common),
        "r": round(r, 3),
        "split": f"≤{split_year} vs >{split_year}",
        "verdict": "repeatable" if r >= 0.5 else "partly repeatable" if r >= 0.3 else "not repeatable",
    }


def step_up(gender: str, min_n: int = 40):
    """Seed curve plus seed-adjusted step-up by program, class year, and year.

    `min_n` gates the program leaderboard: per-swimmer samples are far too
    small to be a "trait" (a handful of finals each), and even programs need
    a few dozen swims before the median stabilises.
    """
    with _connect() as conn:
        swims = _swims(conn, gender)

    if not swims:
        return {
            "gender": gender, "n": 0, "min_n": min_n, "overall": None,
            "seed_curve": [], "bands": [], "programs": [],
            "classes": [], "years": [], "partial_years": [], "reliability": None,
        }

    base = _baseline(swims)
    for s in swims:
        s["adj"] = s["pct"] - base[s["seed"]]

    # --- seed curve (the finding itself) ---
    by_seed = defaultdict(list)
    for s in swims:
        by_seed[s["seed"]].append(s)
    seed_curve = [
        dict(seed=seed, baseline=round(base[seed], 3), **_summary(by_seed[seed]))
        for seed in sorted(by_seed)
    ]

    by_band = defaultdict(list)
    for s in swims:
        by_band[_band(s["seed"])].append(s)
    bands = [
        dict(band=label, **_summary(by_band[label]))
        for label, _, _ in SEED_BANDS if by_band.get(label)
    ]

    # --- programs, ranked on seed-adjusted median ---
    by_school = defaultdict(list)
    for s in swims:
        by_school[s["school"]].append(s)
    programs = [
        dict(school=school, **_summary(items))
        for school, items in by_school.items() if len(items) >= min_n
    ]
    programs.sort(key=lambda r: r["median_adj"], reverse=True)

    # --- class years ---
    by_class = defaultdict(list)
    for s in swims:
        if s["cls"]:
            by_class[s["cls"]].append(s)
    classes = [
        dict(cls=c, **_summary(by_class[c]))
        for c in CLASS_ORDER if by_class.get(c)
    ]

    # --- per meet year, plus which years are missing the B final ---
    by_year = defaultdict(list)
    for s in swims:
        by_year[s["year"]].append(s)
    years = [dict(year=y, **_summary(by_year[y])) for y in sorted(by_year)]

    partial = [
        y for y in sorted(by_year)
        if max(s["seed"] for s in by_year[y]) < MAX_SEED
    ]

    return {
        "gender": gender,
        "n": len(swims),
        "min_n": min_n,
        "overall": _summary(swims),
        "seed_curve": seed_curve,
        "bands": bands,
        "programs": programs,
        "classes": classes,
        "years": years,
        "partial_years": partial,
        "reliability": _reliability(swims),
    }


def step_up_swims(gender: str, school: str | None = None):
    """Individual swims behind the aggregates — for drill-down and spot checks."""
    with _connect() as conn:
        swims = _swims(conn, gender)
    base = _baseline(swims)
    for s in swims:
        s["adj"] = s["pct"] - base[s["seed"]]
    if school:
        swims = [s for s in swims if s["school"] == school]
    swims.sort(key=lambda s: s["adj"], reverse=True)
    for s in swims:
        s["pct"] = round(s["pct"], 3)
        s["adj"] = round(s["adj"], 3)
    return {"gender": gender, "school": school, "n": len(swims), "swims": swims}
