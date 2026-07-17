#!/usr/local/bin/python3

'''
Sanity-check the CSV produced by create_csv.py before it's fed into analyze.py.

This exists because create_csv.py's regex parsing can silently produce
incomplete or malformed rows (e.g. a place getting skipped, or a school name
tripping up a regex) without raising an error. analyze.py's filters
(PLACE == 1, PLACE == 16, len(splits) == 4, etc.) will then either crash or
- worse - silently return wrong data. Run this after every create_csv.py run.

Usage: python3 validate_csv.py [csv_file]   (defaults to ncaa_2026_results.csv)
'''

import sys
import pandas as pd
from analyze import parse_time

REQUIRED_COLUMNS = [
    'PLACE', 'NAME', 'SCHOOL', 'PRELIM_TIME', 'FINAL_TIME', 'POINTS',
    'SPLITS_50', 'SECTION', 'EVENT_NUM', 'EVENT_NAME', 'EVENT_GENDER',
    'EVENT_DISTANCE', 'EVENT_COURSE', 'EVENT_STROKE', 'IS_RELAY', 'MEET_YEAR',
]

# columns that are allowed to be blank/NaN under normal circumstances
NULLABLE = {'FINAL_TIME', 'REACTION', 'RELAY_SWIMMERS', 'YEAR'}


def check_schema(df):
    """All expected columns are present."""
    errors = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Missing columns: {missing}")
    return errors


def check_unexpected_nulls(df):
    """No nulls in columns that should always be populated."""
    errors = []
    for col in REQUIRED_COLUMNS:
        if col in NULLABLE or col not in df.columns:
            continue
        n_null = df[col].isna().sum()
        if n_null:
            errors.append(f"{col}: {n_null} unexpected null value(s)")
    return errors


def check_duplicate_results(df):
    """Flag rows sharing a place in the same event/year/section - unless every one of
    those rows has the same final time, in which case it's a legitimate tie (common in
    swimming) rather than a parsing error."""
    errors = []
    dupe_keys = ['EVENT_NAME', 'MEET_YEAR', 'SECTION', 'PLACE']
    dupes = df[df.duplicated(subset=dupe_keys, keep=False)]
    for (event, year, section, place), g in dupes.groupby(dupe_keys):
        if g['NAME'].duplicated().any():
            names = ', '.join(g['NAME'])
            errors.append(f"Exact duplicate row(s) for place {place} in {event} ({year}, {section}): {names}")
        elif g['FINAL_TIME'].nunique() > 1:
            detail = ', '.join(f"{n} ({t})" for n, t in zip(g['NAME'], g['FINAL_TIME']))
            errors.append(f"Place {place} in {event} ({year}, {section}) shared by swimmers with different times (not a tie - check parsing): {detail}")
        # else: same place, same time -> legitimate tie, not an error
    return errors


def check_place_sequence(df):
    """Finals results for an event/year should have no gaps between 1 and the max place."""
    errors = []
    finals = df[df['SECTION'] == 'finals']
    for (event, year), g in finals.groupby(['EVENT_NAME', 'MEET_YEAR']):
        places = set(g['PLACE'])
        max_place = max(places)
        missing = sorted(set(range(1, max_place + 1)) - places)
        if missing:
            errors.append(f"{event} ({year}): missing place(s) {missing} (max place {max_place})")
    return errors


def check_split_counts(df):
    """Each row's split count should match the typical count for its event distance/type."""
    errors = []
    counts = df['SPLITS_50'].str.split('|').apply(len)
    for (distance, is_relay), g in df.groupby(['EVENT_DISTANCE', 'IS_RELAY']):
        expected = counts[g.index].mode().iloc[0]
        off = g[counts[g.index] != expected]
        for _, row in off.iterrows():
            n = len(str(row['SPLITS_50']).split('|'))
            errors.append(
                f"{row['EVENT_NAME']} ({row['MEET_YEAR']}), {row['NAME']}: "
                f"{n} splits, expected {expected}"
            )
    return errors


def check_time_parsing(df):
    """PRELIM_TIME/FINAL_TIME should parse to a positive number of seconds (or be blank/NT/DQ)."""
    errors = []
    for col in ['PRELIM_TIME', 'FINAL_TIME']:
        for idx, val in df[col].items():
            if pd.isna(val) or val in ('', 'NT', 'DQ'):
                continue
            try:
                seconds = parse_time(val)
            except (ValueError, IndexError):
                errors.append(f"{col} row {idx} ({df.loc[idx,'NAME']}): unparseable value {val!r}")
                continue
            if seconds <= 0:
                errors.append(f"{col} row {idx} ({df.loc[idx,'NAME']}): non-positive time {seconds}")
    return errors


def check_relay_consistency(df):
    """IS_RELAY rows should have a roster and no swimmer class; individual rows the reverse."""
    errors = []
    relay = df[df['IS_RELAY']]
    missing_roster = relay[relay['RELAY_SWIMMERS'].isna() | (relay['RELAY_SWIMMERS'] == '')]
    for _, row in missing_roster.iterrows():
        errors.append(f"{row['EVENT_NAME']} ({row['MEET_YEAR']}), place {row['PLACE']}: relay with no roster parsed")

    individual = df[~df['IS_RELAY']]
    missing_year = individual[individual['YEAR'].isna()]
    for _, row in missing_year.iterrows():
        errors.append(f"{row['EVENT_NAME']} ({row['MEET_YEAR']}), {row['NAME']}: individual swimmer with no class/year")
    return errors


CHECKS = [
    ('Schema', check_schema),
    ('Unexpected nulls', check_unexpected_nulls),
    ('Duplicate results', check_duplicate_results),
    ('Place sequence gaps', check_place_sequence),
    ('Split counts', check_split_counts),
    ('Time parsing', check_time_parsing),
    ('Relay/individual consistency', check_relay_consistency),
]


def main():
    file_name = sys.argv[1] if len(sys.argv) > 1 else 'ncaa_2026_results.csv'
    df = pd.read_csv(file_name)

    total_errors = 0
    for name, check in CHECKS:
        errors = check(df)
        status = 'OK' if not errors else f'{len(errors)} issue(s)'
        print(f'[{status}] {name}')
        for e in errors[:20]:
            print(f'    - {e}')
        if len(errors) > 20:
            print(f'    ... and {len(errors) - 20} more')
        total_errors += len(errors)

    print()
    if total_errors:
        print(f'FAILED: {total_errors} issue(s) found across {len(df)} rows.')
        sys.exit(1)
    else:
        print(f'PASSED: all checks clean across {len(df)} rows.')


if __name__ == '__main__':
    main()
