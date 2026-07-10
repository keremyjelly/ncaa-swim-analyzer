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

def get_txt_files(data_dir):
    """Return a sorted list of full file paths for every .txt/.rtf in data_dir."""
    return sorted([os.path.join(data_dir, file) for file in os.listdir(data_dir) if file.endswith(('.txt', '.rtf'))])

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
      filename = os.path.basename(filepath)
      parts = filename.split('_')
      event_num = int(parts[1][1:])
      return event_num

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

# A ranked result line always starts with a 1-4 digit place followed by whitespace
# and more content (as opposed to a deeply-indented split line or divider).
CANDIDATE_RESULT_LINE = re.compile(r'^\s{1,4}\d+\s+\S')

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
    """Return (reaction, splits_50) parsed out of the lines following a result row."""
    reaction = None
    first_split = None
    for sl in split_lines:
        rt = re.search(r'r:[+\-]?([\d.]+)\s+([\d.]+)', sl)
        if rt:
            reaction = float(rt.group(1))
            first_split = rt.group(2)
            break

    splits_50 = []
    if first_split:
        splits_50.append(first_split)
    for sl in split_lines:
        for val in re.findall(r'\(([\d:.]+)\)', sl):
            splits_50.append(val)

    return reaction, splits_50

def parse_swimmers(lines):
        """Return (results, skipped_count) of individual swimmer info dicts from the file lines."""
        results = []
        skipped = 0
        i = 0
        section = 'finals'
        while i < len(lines):

            if '=== Preliminaries ===' in lines[i]:
                section = 'prelims'
            elif '=== Championship Final ===' in lines[i]:
                section = 'finals'
            # try to match lines[i] to a swimmer name and school
            m = re.match(r'^\s{1,4}(\d+)\s+([\w ,.\-\']+?)\s{2,}(FR|SO|JR|SR|5Y|GR)\s+([\w .()\-\']+?)\s{2,}([\d:.]+|NT)\s*([\d:]*\d+\.\d{2,}\w?|NT|DQ)?\s*(\d*\.?\d*)', lines[i])
            # if no match, increment i and continue
            if not m:
                if CANDIDATE_RESULT_LINE.match(lines[i]):
                    skipped += 1
                i += 1
                continue
            # extract all the fields from the match
            place = int(m.group(1))
            name = m.group(2).strip()
            year = m.group(3)
            school = m.group(4)
            prelim_time = m.group(5)
            final_time = m.group(6) if m.group(6) else ''
            points = float(m.group(7)) if m.group(7) else 0

            # collect the split lines (while not a new swimmer and not a divider, add that line to split_lines)
            split_lines, j = _collect_split_lines(lines, i + 1)
            reaction, splits_50 = _extract_reaction_and_splits(split_lines)

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

        return results, skipped

def parse_relay_teams(lines):
        """Return (results, skipped_count) of relay team info dicts from the file lines."""
        results = []
        skipped = 0
        i = 0
        section = 'finals'
        while i < len(lines):

            if '=== Preliminaries ===' in lines[i]:
                section = 'prelims'
            elif '=== Championship Final ===' in lines[i]:
                section = 'finals'
            # try to match lines[i] to a relay team row: place, school, seed, final, points
            m = re.match(r'^\s{1,4}(\d+)\s+([A-Za-z][\w &.()\-\']*?)\s{2,}([\d:.]+|NT)\s*([\d:]*\d+\.\d{2,}\w?|NT|DQ)?\s*(\d*\.?\d*)', lines[i])
            if not m:
                if CANDIDATE_RESULT_LINE.match(lines[i]):
                    skipped += 1
                i += 1
                continue
            place = int(m.group(1))
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

        return results, skipped

def parse_event_name(event_name):
    m = re.match(r'(Men|Women)\s+(\d+)\s+(Yard|Meter)\s+(.+)', event_name)
    if m:
        return m.group(1), int(m.group(2)), m.group(3), m.group(4)
    return None, None, None, None

def main():
    # parse cmdline args
    data_dir = None
    if len(sys.argv) > 2:
        print('Error: Too Many Arguments!')
        print(f'Usage: python3 create_csv.py <data directory>')
        sys.exit(1)
    elif len(sys.argv) == 1:
        data_dir = 'data'
    else:
        if not os.path.exists(sys.argv[1]):
            print('Error: Invalid Data Path')
            sys.exit(1)
        data_dir = sys.argv[1]
            
    txt_files = get_txt_files(data_dir)
    all_swimmers = []
    for filepath in txt_files:
        lines = read_file(filepath)
        header_event_num, event_name = parse_event_header(lines)
        event_num = header_event_num if header_event_num is not None else parse_filename(filepath)
        if header_event_num is not None and header_event_num != parse_filename(filepath):
            print(f"Warning: {filepath} is named event {parse_filename(filepath)} but its header says Event {header_event_num}; using {header_event_num}")
        meet_year = parse_year(lines)
        # relay events are detected from the event name itself (the header text),
        # not the filename, since filenames aren't consistent (e.g. "..._mr_m.txt")
        is_relay = bool(event_name) and 'relay' in event_name.lower()
        if is_relay:
            swimmers, skipped = parse_relay_teams(lines)
        else:
            swimmers, skipped = parse_swimmers(lines)
        if skipped:
            print(f"Warning: skipped {skipped} unrecognized result line(s) in {filepath}")
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
        df.to_csv('ncaa_2026_results.csv', index=False)
        print(f"Saved {len(all_swimmers)} swimmer results to ncaa_2026_results.csv")

if __name__ == "__main__":
     main()
