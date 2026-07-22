#!/usr/local/bin/python3

'''
Goal: create a csv file by reading the data in each text file of event results from the NCAA championships.

Rows Swimmer/Team name
Columns
    School Represented, Meet Year, Event number, Event name, Relay/Individual, Prelims/Finals, Final place, Points scored,
    Swimmer name, Swimmer year, reaction time, 50 splits, Final time

Open each txt file and split by lines
'''
import pandas as pd
import re
import sys
import os
import subprocess

def get_txt_files(data_dir, year=None):
    """Return a sorted list of full file paths for every .txt/.rtf in data_dir.

    If year is given (e.g. '21'), only files named 'ncaa<year>_...' are returned.
    """
    prefix = f'ncaa{year}_' if year else ''
    return sorted([
        os.path.join(data_dir, file) for file in os.listdir(data_dir)
        if file.endswith(('.txt', '.rtf')) and file.startswith(prefix)
    ])

def read_file(filepath):
    if filepath.endswith('.rtf'):
        # meet results are sometimes saved as rtf (e.g. pasted into TextEdit);
        # convert to plain text with macOS's built-in textutil rather than
        # trying to hand-parse RTF control codes.
        proc = subprocess.run(
            ['textutil', '-convert', 'txt', '-stdout', filepath],
            capture_output=True, text=True, check=True,
        )
        return proc.stdout.splitlines()
    with open(filepath,'r') as f:
        data = f.read().splitlines()
    return data

def parse_filename(filepath):
      """Return the event number encoded in the filename, or None if the filename
      doesn't follow the '..._eNN_...' convention (e.g. 'ncaa24_400_free_relay_m.rtf')."""
      filename = os.path.basename(filepath)
      parts = filename.split('_')
      if len(parts) < 2 or not re.match(r'^e\d+$', parts[1]):
          return None
      return int(parts[1][1:])

def parse_year(lines):
    """Return the meet year from the file header lines."""
    for line in lines:
        m = re.search(r'\b(20\d{2})\b', line)
        if m:
            return int(m.group(1))
    return None

def parse_event_header(lines):
      """Return (event_num, event_name) parsed from the file's 'Event N ...' header line.
      This is the source of truth for event_num - filenames have been observed
      to be mislabeled (e.g. a file named '..._e10_...' whose header says 'Event 9')."""
      for line in lines:
          m = re.search(r'Event\s+(\d+)\s+(.+)', line)
          if m:
              return int(m.group(1)), m.group(2).strip()
      return None, None

# A ranked result line always starts with a 1-4 digit place (or '--' for a
# disqualified/scratched swimmer) followed by whitespace and more content (as
# opposed to a deeply-indented split line or divider).
CANDIDATE_RESULT_LINE = re.compile(r'^\s{1,4}(?:\d+|--)\s+\S')

ROSTER_SWIMMER = re.compile(r'\d\)\s+(?:r:[+\-]?[\d.]+\s+)?([A-Za-z][\w ,.\-\']*?)\s+(FR|SO|JR|SR|5Y|GR)')

def _collect_split_lines(lines, start):
    """Gather the non-divider lines following a result row (splits, reaction, roster, etc.)
    until the next result row or a divider is hit. Returns (split_lines, next_index)."""
    split_lines = []
    j = start
    while j < len(lines):
        if CANDIDATE_RESULT_LINE.match(lines[j]):
            break
        if lines[j].strip().startswith('='):
            break
        if lines[j].strip().startswith('--'):
            break
        if lines[j].strip():
            split_lines.append(lines[j].strip())
        j += 1
    return split_lines, j

def _extract_reaction_and_splits(split_lines):
    """Return (reaction, splits_50) parsed out of the lines following a result row.

    The line carrying the opening 50 looks like either
      'r:+0.65  21.83        45.79 (45.79)'   (reaction time recorded)
    or
      '20.95        44.24 (23.29)'            (no reaction time recorded)
    The reaction-time prefix is optional; the opening split itself (the first
    bare, non-parenthesized number) is not, so it must be captured either way.
    """
    # The split value itself always has 2+ decimal digits (e.g. '24.58'); requiring
    # that excludes unrelated trailing document text that can get swept into a
    # DQ'd/scratched swimmer's split_lines (e.g. a '1. Arizona St ... 369' team-
    # rankings line), which would otherwise falsely match as a bare '1.' split.
    reaction = None
    first_split = None
    for sl in split_lines:
        m = re.match(r'^(?:r:[+\-]?([\d.]+)\s+)?(\d+\.\d{2,})\s', sl)
        if m:
            if m.group(1):
                reaction = float(m.group(1))
            first_split = m.group(2)
            break

    splits_50 = []
    if first_split:
        splits_50.append(first_split)
    for sl in split_lines:
        for val in re.findall(r'\(([\d:.]+)\)', sl):
            splits_50.append(val)

    return reaction, splits_50

def parse_swimmers(lines):
        """Return (results, skipped_count, deduped_count) of individual swimmer info dicts
        from the file lines. Some source files have been observed to have an entire results
        block pasted in twice (copy-paste error at data-collection time); deduped_count
        tracks how many exact-repeat rows (same section/place/name/school/final time) were
        dropped as a result."""
        results = []
        skipped = 0
        deduped = 0
        seen = set()
        i = 0
        section = 'finals'
        while i < len(lines):

            if '=== Preliminaries ===' in lines[i]:
                section = 'prelims'
            elif '=== Championship Final ===' in lines[i]:
                section = 'finals'
            # try to match lines[i] to a swimmer name and school. Place is normally
            # a number, but a disqualified/scratched swimmer is shown as '--' instead.
            m = re.match(r'^\s{1,4}(\d+|--)\s+([\w ,.\-\']+?)\s{2,}(FR|SO|JR|SR|5Y|GR)\s+([\w .()\-\']+?)\s{2,}([\d:.]+|NT)\s*([\d:]*\d+\.\d{2,}\w?|NT|DQ)?\s*(\d*\.?\d*)', lines[i])
            # if no match, increment i and continue
            if not m:
                if CANDIDATE_RESULT_LINE.match(lines[i]):
                    skipped += 1
                i += 1
                continue
            # extract all the fields from the match
            place = int(m.group(1)) if m.group(1) != '--' else None
            name = m.group(2).strip()
            year = m.group(3)
            school = m.group(4)
            prelim_time = m.group(5)
            final_time = m.group(6) if m.group(6) else ''
            points = float(m.group(7)) if m.group(7) else 0

            # collect the split lines (while not a new swimmer and not a divider, add that line to split_lines)
            split_lines, j = _collect_split_lines(lines, i + 1)
            reaction, splits_50 = _extract_reaction_and_splits(split_lines)

            # skip exact repeats of a row we've already recorded in this section
            # (source file had the same block pasted in more than once)
            key = (section, place, name, school, final_time)
            if key in seen:
                deduped += 1
                i = j
                continue
            seen.add(key)

            # build a dict with everything
            results.append({
                'PLACE': place,
                'NAME': name,
                'YEAR': year,
                'SCHOOL': school,
                'PRELIM_TIME': prelim_time,
                'FINAL_TIME': final_time,
                'POINTS': points,
                'REACTION': reaction,
                'SPLITS_50': splits_50,
                'SECTION': section,
            })

            # append the dict to results
            i = j

        return results, skipped, deduped

def parse_relay_teams(lines):
        """Return (results, skipped_count, deduped_count) of relay team info dicts from the
        file lines. See parse_swimmers() for why deduped_count exists."""
        results = []
        skipped = 0
        deduped = 0
        seen = set()
        i = 0
        section = 'finals'
        while i < len(lines):

            if '=== Preliminaries ===' in lines[i]:
                section = 'prelims'
            elif '=== Championship Final ===' in lines[i]:
                section = 'finals'
            # try to match lines[i] to a relay team row: place, school, seed, final, points.
            # Place is normally a number, but a disqualified relay is shown as '--'.
            m = re.match(r'^\s{1,4}(\d+|--)\s+([A-Za-z][\w &.()\-\']*?)\s{2,}([\d:.]+|NT)\s*([\d:]*\d+\.\d{2,}\w?|NT|DQ)?\s*(\d*\.?\d*)', lines[i])
            if not m:
                if CANDIDATE_RESULT_LINE.match(lines[i]):
                    skipped += 1
                i += 1
                continue
            place = int(m.group(1)) if m.group(1) != '--' else None
            school = m.group(2).strip()
            prelim_time = m.group(3)
            final_time = m.group(4) if m.group(4) else ''
            points = float(m.group(5)) if m.group(5) else 0

            split_lines, j = _collect_split_lines(lines, i + 1)
            reaction, splits_50 = _extract_reaction_and_splits(split_lines)

            # pull the 4 relay swimmers (name + class) out of the roster lines
            roster = []
            for sl in split_lines:
                roster.extend(ROSTER_SWIMMER.findall(sl))
            relay_swimmers = '|'.join(f'{name.strip()} ({cls})' for name, cls in roster)

            key = (section, place, school, final_time)
            if key in seen:
                deduped += 1
                i = j
                continue
            seen.add(key)

            results.append({
                'PLACE': place,
                'NAME': school,
                'YEAR': '',
                'SCHOOL': school,
                'PRELIM_TIME': prelim_time,
                'FINAL_TIME': final_time,
                'POINTS': points,
                'REACTION': reaction,
                'SPLITS_50': splits_50,
                'SECTION': section,
                'RELAY_SWIMMERS': relay_swimmers,
            })

            i = j

        return results, skipped, deduped

def parse_event_name(event_name):
    m = re.match(r'(Men|Women)\s+(\d+)\s+(Yard|Meter)\s+(.+)', event_name)
    if m:
        return m.group(1), int(m.group(2)), m.group(3), m.group(4)
    return None, None, None, None

def main():
    # parse cmdline args
    data_dir = 'data'
    year = None
    out_path = 'ncaa_2026_results.csv'
    if len(sys.argv) > 2:
        print('Error: Too Many Arguments!')
        print('Usage: python3 create_csv.py [<2-digit year, e.g. 21-26>]')
        sys.exit(1)
    elif len(sys.argv) == 2:
        year = sys.argv[1]
        if not re.match(r'^\d{2}$', year):
            print('Error: Invalid Year')
            print('Usage: python3 create_csv.py [<2-digit year, e.g. 21-26>]')
            sys.exit(1)
        out_dir = 'raw'
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f'ncaa{year}.csv')

    txt_files = get_txt_files(data_dir, year)
    if not txt_files:
        print(f"Error: no data files found for year '{year}' in {data_dir}")
        sys.exit(1)
    all_swimmers = []
    for filepath in txt_files:
        lines = read_file(filepath)
        header_event_num, event_name = parse_event_header(lines)
        filename_event_num = parse_filename(filepath)
        event_num = header_event_num if header_event_num is not None else filename_event_num
        if header_event_num is not None and filename_event_num is not None and header_event_num != filename_event_num:
            print(f"Warning: {filepath} is named event {filename_event_num} but its header says Event {header_event_num}; using {header_event_num}")
        meet_year = parse_year(lines)
        # relay events are detected from the event name itself (the header text),
        # not the filename, since filenames aren't consistent (e.g. "..._mr_m.txt")
        is_relay = bool(event_name) and 'relay' in event_name.lower()
        if is_relay:
            swimmers, skipped, deduped = parse_relay_teams(lines)
        else:
            swimmers, skipped, deduped = parse_swimmers(lines)
        if skipped:
            print(f"Warning: skipped {skipped} unrecognized result line(s) in {filepath}")
        if deduped:
            print(f"Warning: deduped {deduped} repeated result line(s) in {filepath}")
        event_gender, event_distance, event_course, event_stroke = parse_event_name(event_name)
        for s in swimmers:
            s['EVENT_NUM'] = event_num
            s['EVENT_NAME'] = event_name
            s['EVENT_GENDER'] = event_gender
            s['EVENT_DISTANCE'] = event_distance
            s['EVENT_COURSE'] = event_course
            s['EVENT_STROKE'] = event_stroke
            s['IS_RELAY'] = is_relay
            s['MEET_YEAR'] = meet_year
            all_swimmers.append(s)
    if all_swimmers:
        df = pd.DataFrame(all_swimmers)
        df['SPLITS_50'] = df['SPLITS_50'].apply(lambda x: '|'.join(str(s) for s in x))
        df.to_csv(out_path, index=False)
        print(f"Saved {len(all_swimmers)} swimmer results to {out_path}")

if __name__ == "__main__":
     main()
