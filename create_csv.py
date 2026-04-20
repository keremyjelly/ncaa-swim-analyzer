#!/usr/local/bin/python3

'''
Goal: create a csv file by reading the data in each text file of event results from the NCAA championships.

Rows Swimmer/Team name
Columns
    School Represented, Meet Year, Event number, Event name, Relay/Individual, Prelims/Finals, Final place, Points scored,
    Swimmer name, Swimmer year, reaction time, 50 splits, Final time

Open each txt file and split by lines
TODO
'''
import pandas as pd
import re
import sys
import os

def get_txt_files(data_dir):
    """Return a sorted list of full file paths for every .txt in data_dir."""    
    return sorted([os.path.join(data_dir, file) for file in os.listdir(data_dir) if file.endswith('.txt')])

def read_file(filepath):
    with open(filepath,'r') as f:
        data = f.read().splitlines()
    return data

def parse_filename(filepath):
      filename = os.path.basename(filepath)
      parts = filename.split('_')
      event_num = int(parts[1][1:])
      is_relay = 'relay' in filename
      return event_num, is_relay

def parse_year(lines):
    """Return the meet year from the file header lines."""
    for line in lines:
        m = re.search(r'\b(20\d{2})\b', line)
        if m:
            return int(m.group(1))
    return None

def parse_event_header(lines):
      """Return the event name from the file lines."""
      for line in lines:
          m = re.search(r'Event\s+\d+\s+(.+)', line)
          if m:
              return m.group(1).strip()
      return None

def parse_swimmers(lines):
        """Return a list of swimmer info dicts from the file lines."""
        results = []
        i = 0
        section = 'finals'
        while i < len(lines):

            if '=== Preliminaries ===' in lines[i]:
                section = 'prelims'
            elif '=== Championship Final ===' in lines[i]:
                section = 'finals'
            # try to match lines[i] to a swimmer name and school
            m = re.match(r'^\s{1,4}(\d+)\s+([\w ,.\-\']+?)\s{2,}(FR|SO|JR|SR|5Y|GR)\s+([\w ]+?)\s{2,}([\d:.]+|NT)\s*([\d:]*\d+\.\d{2,}\w?|NT|DQ)?\s*(\d*\.?\d*)', lines[i])
            # if no match, increment i and continue
            if not m:
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
            split_lines = []
            j = i + 1
            while j < len(lines):
                if re.match(r'^\s{1,4}\d+\s+', lines[j]):
                     break
                if lines[j].strip().startswith('='):
                    break
                if lines[j].strip().startswith('--'):
                    break
                if lines[j].strip():
                    split_lines.append(lines[j].strip())
                j += 1

            # from split lines, get reaction time and 50 yd splits
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

        return results

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
        event_num, is_relay = parse_filename(filepath)
        event_name = parse_event_header(lines)
        meet_year = parse_year(lines)
        swimmers = parse_swimmers(lines)
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
