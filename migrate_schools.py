#!/usr/bin/env python3
"""
Apply schools.py name normalization to an existing swim.db, in place.

create_csv.py now canonicalizes school names at ingest, so a full re-parse
(create_csv.py per year + build_db.py) would also fix this. This script is the
shortcut: it rewrites only the SCHOOL column, so you don't have to re-run the
whole pipeline just to merge ten name variants.

Usage:
    python3 migrate_schools.py            # show what would change, touch nothing
    python3 migrate_schools.py --apply    # actually write

Safe to run more than once: canonical names map to themselves, so a second run
is a no-op.
"""

import argparse
import os
import shutil
import sqlite3
import sys

from schools import SCHOOL_ALIASES

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "swim.db")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default is a dry run)")
    ap.add_argument("--db", default=DB, help="path to swim.db")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"swim.db not found at {args.db}")

    conn = sqlite3.connect(args.db)
    try:
        before = conn.execute("SELECT COUNT(DISTINCT SCHOOL) FROM results").fetchone()[0]

        planned = []
        for alias, canon in sorted(SCHOOL_ALIASES.items()):
            n = conn.execute("SELECT COUNT(*) FROM results WHERE SCHOOL = ?", (alias,)).fetchone()[0]
            if n:
                planned.append((alias, canon, n))

        if not planned:
            print("Nothing to do — no alias spellings present.")
            return

        print(f"{'alias':<18}{'->':^4}{'canonical':<18}{'rows':>6}")
        for alias, canon, n in planned:
            print(f"{alias:<18}{'->':^4}{canon:<18}{n:>6}")
        total = sum(n for _, _, n in planned)
        print(f"\n{total} rows across {len(planned)} aliases; "
              f"distinct schools {before} -> {before - len(planned)}")

        if not args.apply:
            print("\nDry run. Re-run with --apply to write.")
            return

        # Relay rows carry the school in NAME as well (the team *is* the
        # competitor), so both columns need rewriting to stay consistent.
        backup = args.db + ".bak"
        shutil.copy2(args.db, backup)
        print(f"\nbacked up to {backup}")

        for alias, canon, _ in planned:
            conn.execute("UPDATE results SET SCHOOL = ? WHERE SCHOOL = ?", (canon, alias))
            conn.execute(
                "UPDATE results SET NAME = ? WHERE NAME = ? AND IS_RELAY = 1", (canon, alias)
            )
        conn.commit()

        after = conn.execute("SELECT COUNT(DISTINCT SCHOOL) FROM results").fetchone()[0]
        left = [a for a in SCHOOL_ALIASES
                if conn.execute("SELECT 1 FROM results WHERE SCHOOL = ? LIMIT 1", (a,)).fetchone()]
        print(f"done. distinct schools now {after}"
              + (f"; STILL PRESENT: {left}" if left else "; no alias spellings remain"))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
