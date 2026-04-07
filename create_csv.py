#!usr/bin/env python3

'''
Goal: create a csv file by reading the data in each text file of event results from the 2026 NCAA championships.

Rows Swimmer/Team name
Columns
    School Represented, Date swam, Event number, Event name, Relay/Individual, Prelims/Finals, Final place, Points scored, Record type,
    1st Swimmer name, 1st Swimmer year, 1st swimmer reaction time, 1st swimmer splits aggregated, 1st swimmer 50 splits, 1st swimmer Final time,
    2nd Swimmer name, 2nd Swimmer year, 2nd swimmer reaction time, 2nd swimmer splits aggregated, 2nd swimmer 50 splits, 2nd swimmer final time,
    3rd Swimmer name, 3rd Swimmer year, 3rd swimmer reaction time, 3rd swimmer splits aggregated, 3rd swimmer 50 splits, 3rd swimmer final time,
    4th Swimmer name, 4th Swimmer year, 4th swimmer reaction time, 4th swimmer splits aggregated, 4th swimmer 50 splits, 4th swimmer final time

Open each txt file and split by lines
TODO
'''
import csv
import pandas as pd
import re
import os

EVENT_DATES = {
    1: '2026-03-25',
    2: '2026-03-25',
    3: '2026-03-25',
    4: '2026-03-26',
    5: '2026-03-26',
    6: '2026-03-26',
    7: '2026-03-26',
    8: '2026-03-26',
    9: '2026-03-26',
    10: '2026-03-27',
    11: '2026-03-27',
    12: '2026-03-27',
    13: '2026-03-27',
    14: '2026-03-27',
    15: '2026-03-27',
    16: '2026-03-28',
    17: '2026-03-28',
    18: '2026-03-28',
    19: '2026-03-28',
    20: '2026-03-28',
    21: '2026-03-28',
}
                  
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

def parse_event_header(lines):
      """Return the event name from the file lines."""
      for line in lines:
          m = re.search(r'Event\s+\d+\s+(.+)', line)
          if m:
              return m.group(1).strip()
      return None

def parse_swimmer_info(lines):
     pass