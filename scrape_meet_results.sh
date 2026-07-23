#!/bin/bash
#
# Download NCAA D-I prelim (P) session result pages, HTML-tag-stripped, into data/.
#
# Run this NATIVELY on your Mac. The sandbox cannot reach swimmeetresults.tech,
# and web fetchers reformat the HTML (destroying HY-TEK's fixed-width columns
# that create_csv.py relies on). Plain `curl | sed` is required.
#
# Idempotent: files that already exist and are non-empty are skipped, so it is
# safe to re-run. Currently this fills in the missing prelims (men 2021-2026,
# women 2026); women 2021-2025 prelims already present will be skipped.
#
# After running: `python create_csv.py <YY>` per year, then `python build_db.py`.
# NOTE: finals (F) pages already include prelim non-qualifiers, so create_csv.py
# must dedupe once these P pages are added.

set -uo pipefail

cd ~/dev/ncaa-swim-analyzer/data || exit 1

# slug | YY (prefix create_csv wants) | gender tag
MEETS=(
  "NCAA-Division-I-Men-2021|21|m"
  "NCAA-Division-I-Men-2022|22|m"
  "NCAA-Division-I-Men-2023|23|m"
  "NCAA-Division-I-Men-2024|24|m"
  "NCAA-Division-I-Men-2025|25|m"
  "NCAA-Division-I-Men-2026|26|m"
  "NCAA-Division-I-Women-2021|21|w"
  "NCAA-Division-I-Women-2022|22|w"
  "NCAA-Division-I-Women-2023|23|w"
  "NCAA-Division-I-Women-2024|24|w"
  "NCAA-Division-I-Women-2025|25|w"
  "NCAA-Division-I-Women-2026|26|w"
)

for entry in "${MEETS[@]}"; do
  IFS='|' read -r SLUG YY G <<< "$entry"
  base="https://swimmeetresults.tech/$SLUG"
  echo "== $SLUG =="

  # Discover the exact P (prelim) event-file names from the meet index.
  files=$(curl -s "$base/evtindex.htm" | grep -oE '[0-9]{6}P[0-9]{3}\.htm' | sort -u)
  if [ -z "$files" ]; then
    echo "  no prelim pages found (or index unreachable)"
    continue
  fi

  while read -r f; do
    out="ncaa${YY}_${G}_${f%.htm}.txt"
    if [ -s "$out" ]; then
      echo "  skip $out (exists)"
      continue
    fi
    if curl -sf "$base/$f" | sed 's/<[^>]*>//g' > "$out" && [ -s "$out" ]; then
      # Drop diving prelims (1 mtr / 3 mtr / platform) automatically:
      # these are scored by points, not time, and are excluded from the DB.
      if grep -qE '^ Event .*Diving' "$out"; then
        rm -f "$out"
        echo "  skip $out (diving)"
      else
        echo "  saved $out"
      fi
    else
      rm -f "$out"
      echo "  FAILED $f"
    fi
  done <<< "$files"
done
