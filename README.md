# NCAA Swim Analyzer

## Overview

This project turns six years of Men's NCAA Swimming & Diving Championship results (2021–2026) into a queryable dataset and an interactive dashboard for exploring how the sport is changing. Raw meet files — the messy, multi-line text you get when you export a results heat sheet — get parsed into clean per-year CSVs, loaded into a SQLite database, and surfaced two ways: through a web dashboard for visual trend analysis, and through exploratory SQL for digging into specific questions.

The original version of this was a one-meet, five-question class project. It's grown into something I actually want to use: a platform for looking at **race trends** (how events evolve year over year) and **individual trends** (how a given swimmer's times move across seasons).

Right now the dataset covers 2,682 results across 18 events and roughly 600 individual swimmers.

## Data Pipeline

The data flows through three stages:

```
data/ncaa<YY>_e<NN>_<event>_m.txt   ← raw meet files, one per event
        │  create_csv.py <YY>
        ▼
raw/ncaa<YY>.csv                    ← one cleaned CSV per year
        │  build_db.py
        ▼
swim.db  (results table)            ← what the dashboard + queries read
```

To add or refresh a year, drop the meet files into `data/` using the `ncaa<YY>_...` naming convention so they get picked up, then run:

```bash
python3 create_csv.py 21     # rebuild raw/ncaa21.csv from data/
python3 build_db.py          # rebuild swim.db from all raw/*.csv
```

**create_csv.py** reads the meet files in `data/` and extracts events, places, points, times, splits, and reaction times using regex and general parsing logic. Given a 2-digit year (e.g. `21`) it processes just that year's files and writes `raw/ncaa<YY>.csv`.

**build_db.py** concatenates every `raw/ncaa*.csv`, adds the parsed-seconds columns (`FINAL_TIME_SEC`, `PRELIM_TIME_SEC`), and rebuilds the `results` table from scratch. `raw/*.csv` is the single source of truth, so no stale rows ever linger.

## Web Dashboard

`web/` holds an interactive browser dashboard built on `swim.db`: a **FastAPI** backend serving trend data and a **React (Vite)** frontend charting winning and top-16 average times by year, with an event selector. The y-axis is reversed so faster times sit higher, and a headline stat shows how much the winning time moved across the dataset. See `web/README.md` for how to run the two servers locally.

## Exploratory Analysis

A few things jump out once the six years sit in one table.

**The sport is getting faster, almost across the board.** Comparing the 2021 winner to the 2026 winner in each event:

| Event | 2021 winner | 2026 winner | Change |
| --- | --- | --- | --- |
| 100 Free | 40.89 | 39.91 | −0.98s |
| 1650 Free | 14:12.52 | 14:10.03 | −2.49s |
| 100 Butterfly | 44.25 | 42.49 | −1.76s |
| 200 Backstroke | 1:35.75 | 1:34.13 | −1.62s |
| 500 Free | 4:07.97 | 4:06.56 | −1.41s |
| 200 IM | 1:39.53 | 1:38.48 | −1.05s |
| 50 Free | 18.33 | 18.06 | −0.27s |

**Depth is improving faster than the win.** In the 100 Free the winning time dropped ~1.0s from 2021 to 2026, but the top-16 average tightened even more — 42.08 → 40.63 — meaning the whole field is compressing, not just the top of it. (The 2026 average is computed over the 8 finalists captured for that year, so treat the last point as indicative rather than exact — filling in full 2026 heats is on the roadmap.)

**Individual trajectories are the most interesting thread — and the least finished.** A self-join on swimmer + event across consecutive years surfaces the biggest year-over-year drops:

```sql
SELECT a.NAME, a.EVENT_NAME, a.MEET_YEAR,
       a.FINAL_TIME_SEC AS before, b.FINAL_TIME_SEC AS after
FROM results a
JOIN results b
  ON a.NAME = b.NAME AND a.EVENT_NAME = b.EVENT_NAME
 AND b.MEET_YEAR = a.MEET_YEAR + 1
WHERE a.SECTION = 'finals' AND b.SECTION = 'finals' AND a.IS_RELAY = 0
ORDER BY (a.FINAL_TIME_SEC - b.FINAL_TIME_SEC) DESC;
```

The leaderboard it returns is dominated by distance swimmers (Levi Sandidge, −20.0s in the 1650 from 2024→2025; Liam Custer, −19.9s), which makes sense — a 15-minute race has far more room to swing than a 40-second one. Two caveats make this a starting point rather than a finished feature: it matches on *exact* name strings (no identity resolution yet, so a name typo or format change breaks the link), and raw seconds favor long events. Normalizing swimmer identity and switching to percentage improvement is the next real step.

## Data Source & Parsing

The results I wanted lived on a dynamically rendered JavaScript site, so pulling them with plain HTTP requests just returned empty tags. I ended up downloading each event under a standardized naming convention and parsing from there. The parsing itself was the hard part: results span multiple lines per swimmer, and the 50-yard splits in particular are finicky — I loop to find where the split block ends, then pull lingering fields like reaction times out of that subset with regex.

## Roadmap

- **Individual swimmer identity** — the highest-value next feature. Resolve name variants to a single athlete so individual trends work reliably, then add a swimmer page to the dashboard.
- **Women's results** — the parser already handles gender via the `EVENT_GENDER` column; this is mostly a matter of sourcing the data, after which every view works for both.
- **Port trend views into the dashboard** — pacing, split correlations, and reaction-time analysis as interactive charts instead of one-off scripts.
- **Backfill and deploy** — fill in missing heats (e.g. full 2026 fields), extend earlier than 2021 (the format goes back to ~2012), and host the dashboard.

## Use of AI Tools

I used AI as a sounding board and a safety net — talking through how to approach questions statistically, debugging the uglier regular expressions, and standing up the FastAPI/React scaffolding for the dashboard.
