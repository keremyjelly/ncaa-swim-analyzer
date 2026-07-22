#!/usr/local/bin/python3
"""
Build swim.db from the per-year CSVs in raw/.

This replaces the old notebook step: it concatenates every raw/ncaa*.csv,
adds the parsed-seconds columns the dashboard/queries rely on, and (re)writes
the `results` table in swim.db from scratch. raw/*.csv is the source of truth,
so the table is fully rebuilt each run — no stale rows linger.

Typical flow after finding new meet data:
    python3 create_csv.py 21     # rebuild raw/ncaa21.csv from data/
    python3 build_db.py          # rebuild swim.db from all raw/*.csv

Usage:
    python3 build_db.py                 # raw/ -> swim.db (defaults)
    python3 build_db.py --raw raw --db swim.db
"""

import argparse
import glob
import os
import sqlite3
import sys

import pandas as pd

# Reuse the project's own time parser so seconds are computed identically
# everywhere (create_csv/analyze/build_db all agree).
from analyze import parse_time

HERE = os.path.dirname(os.path.abspath(__file__))


def build(raw_dir: str, db_path: str, table: str = "results") -> int:
    paths = sorted(glob.glob(os.path.join(raw_dir, "ncaa*.csv")))
    if not paths:
        print(f"Error: no CSVs matching {os.path.join(raw_dir, 'ncaa*.csv')}.")
        print("Run create_csv.py first to generate raw/ncaa<YY>.csv.")
        sys.exit(1)

    print(f"Reading {len(paths)} file(s):")
    for p in paths:
        print(f"  - {os.path.relpath(p, HERE)}")

    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)

    # Derived seconds columns (not present in the raw CSVs).
    df["FINAL_TIME_SEC"] = df["FINAL_TIME"].apply(
        lambda x: parse_time(x) if pd.notna(x) and x != "" else None
    )
    df["PRELIM_TIME_SEC"] = df["PRELIM_TIME"].apply(
        lambda x: parse_time(x) if pd.notna(x) and x != "" else None
    )

    conn = sqlite3.connect(db_path)
    try:
        df.to_sql(table, conn, if_exists="replace", index=False)
    finally:
        conn.close()

    years = sorted(int(y) for y in df["MEET_YEAR"].dropna().unique())
    print(
        f"\nRebuilt '{table}' in {os.path.relpath(db_path, HERE)}: "
        f"{len(df)} rows, years {years}."
    )
    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild swim.db from raw/*.csv")
    parser.add_argument("--raw", default=os.path.join(HERE, "raw"),
                        help="directory of per-year CSVs (default: raw/)")
    parser.add_argument("--db", default=os.path.join(HERE, "swim.db"),
                        help="output SQLite file (default: swim.db)")
    args = parser.parse_args()
    build(args.raw, args.db)


if __name__ == "__main__":
    main()
