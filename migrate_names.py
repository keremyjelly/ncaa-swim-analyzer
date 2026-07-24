#!/usr/bin/env python3
"""
Apply names.py swimmer-name normalization to an existing swim.db, in place.

Companion to migrate_schools.py. create_csv.py now canonicalizes names at
ingest, so a full re-parse would also fix this; this rewrites just the NAME
column so you don't have to re-run the pipeline.

Usage:
    python3 migrate_names.py            # show what would change, touch nothing
    python3 migrate_names.py --apply    # actually write

Safe to run repeatedly: canonical names map to themselves.

Before writing, this re-checks the safety property that justified each merge —
that the two spellings never appear in the same meet year. If a future data
pull breaks that assumption, the merge is refused rather than silently fusing
two different people.
"""

import argparse
import os
import shutil
import sqlite3
import sys

from names import NAME_ALIASES

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "swim.db")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default is a dry run)")
    ap.add_argument("--db", default=DB, help="path to swim.db")
    ap.add_argument("--force", action="store_true",
                    help="merge even if a year-overlap conflict is detected")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"swim.db not found at {args.db}")

    conn = sqlite3.connect(args.db)
    try:
        before = conn.execute(
            "SELECT COUNT(DISTINCT NAME) FROM results WHERE IS_RELAY = 0"
        ).fetchone()[0]

        planned, conflicts = [], []
        for alias, canon in sorted(NAME_ALIASES.items()):
            n = conn.execute(
                "SELECT COUNT(*) FROM results WHERE NAME = ? AND IS_RELAY = 0", (alias,)
            ).fetchone()[0]
            if not n:
                continue
            ya = {r[0] for r in conn.execute(
                "SELECT DISTINCT MEET_YEAR FROM results WHERE NAME = ? AND IS_RELAY = 0", (alias,))}
            yc = {r[0] for r in conn.execute(
                "SELECT DISTINCT MEET_YEAR FROM results WHERE NAME = ? AND IS_RELAY = 0", (canon,))}
            overlap = sorted(ya & yc)
            if overlap:
                conflicts.append((alias, canon, n, overlap))
            else:
                planned.append((alias, canon, n))

        if conflicts:
            print("!! YEAR-OVERLAP CONFLICTS — both spellings appear in the same meet.")
            print("   That's evidence of two different people, not one renamed swimmer.\n")
            for alias, canon, n, ov in conflicts:
                print(f"   {alias!r} vs {canon!r}: both present in {ov}")
            print()
            if not args.force:
                print("   Refusing to merge these. Re-run with --force to override,")
                print("   or remove them from NAME_ALIASES in names.py.\n")
            else:
                planned.extend((a, c, n) for a, c, n, _ in conflicts)
                print("   --force given: merging anyway.\n")

        if not planned:
            print("Nothing to do — no superseded spellings present.")
            return

        print(f"{'superseded':<26}{'->':^4}{'canonical':<26}{'rows':>5}")
        for alias, canon, n in planned:
            print(f"{alias:<26}{'->':^4}{canon:<26}{n:>5}")
        total = sum(n for _, _, n in planned)
        print(f"\n{total} rows across {len(planned)} merges; "
              f"distinct swimmers {before} -> {before - len(planned)}")

        if not args.apply:
            print("\nDry run. Re-run with --apply to write.")
            return

        backup = args.db + ".bak"
        shutil.copy2(args.db, backup)
        print(f"\nbacked up to {backup}")

        for alias, canon, _ in planned:
            conn.execute("UPDATE results SET NAME = ? WHERE NAME = ? AND IS_RELAY = 0",
                         (canon, alias))
        conn.commit()

        after = conn.execute(
            "SELECT COUNT(DISTINCT NAME) FROM results WHERE IS_RELAY = 0"
        ).fetchone()[0]
        left = [a for a in NAME_ALIASES
                if conn.execute("SELECT 1 FROM results WHERE NAME = ? AND IS_RELAY = 0 LIMIT 1",
                                (a,)).fetchone()]
        print(f"done. distinct swimmers now {after}"
              + (f"; STILL PRESENT: {left}" if left else "; no superseded spellings remain"))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
