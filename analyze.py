#!/usr/local/bin/python3

'''
Use the csv to answer key questions about 2026 NCAA Men's Swimming & Diving Championships

1. What separated the winner from the rest of the pack, and how did gold medal splits compare to the 16th place finisher?
2. How were the 200s paced across each event? Were they back-half heavy, or more of an aggressive approach?
3. Which 25 split of each of the 100s of stroke were the best indicators of final place?
4. Does reaction time have any correlation with place across events?
5. What leg was the difference maker in the 400 IM?
'''

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
import re
import os

# Convert the swimmer times from strings into seconds
# remove any letters associated
def parse_time(time_str):
    time_str = re.sub(r'[^0-9:.]','',str(time_str))
    total_time = 0.0

    # if colon has a colon in it
    if ':' in time_str:
        mins, time_str = time_str.split(':')
        total_time += int(mins) * 60
    total_time += float(time_str)
    return total_time

def calculate_pacing(splits):
    # splits is a list of 4 50 splits
    sum_splits = sum(splits)
    # get the front half and back half of the splits
    front_half = sum(splits[:2])
    back_half = sum(splits[2:])
    # calculate the differential between the front half and back half
    differential = back_half - front_half
    # percentage that's front, back, and differential
    return front_half / sum_splits, back_half / sum_splits, differential

def load_data(filepath):
    df = pd.read_csv(filepath)
    # Convert time columns to seconds
    df['SPLITS_50'] = df['SPLITS_50'].str.split('|')
    df['FINAL_TIME'] = df['FINAL_TIME'].apply(lambda x: parse_time(x) if pd.notna(x) and x != '' else None)
    df['PRELIM_TIME'] = df['PRELIM_TIME'].apply(lambda x: parse_time(x) if pd.notna(x) and x != '' else None)
    # Detect gender from event names in the data
    genders = df['EVENT_GENDER'].dropna().unique()
    gender = genders[0] if len(genders) == 1 else 'Men'
    return df, gender

def get_1650_split_comparison(df, gender):
    # filter by event
    mile = df[df['EVENT_NAME'] == f'{gender} 1650 Yard Freestyle']
    gold = [ float(s) for s in mile[mile['PLACE'] == 1]['SPLITS_50'].values[0] ]
    silver = [ float(s) for s in mile[mile['PLACE'] == 2]['SPLITS_50'].values[0] ]
    sixteenth = [float (s) for s in mile[mile['PLACE'] == 16]['SPLITS_50'].values[0] ]
    return gold, silver, sixteenth

def get_200_pacing(df, gender):
    # filter by event and calculate pacing for each event
    strokes = ['Butterfly', 'Backstroke', 'Breaststroke', 'Freestyle', 'IM']
    result = {}
    for stroke in strokes:
        event_name = f'{gender} 200 Yard {stroke}'
        event = df[df['EVENT_NAME'] == event_name]
        splits_list = event[event['PLACE'] <= 16]['SPLITS_50'].dropna().tolist()
        splits_array = np.array([[float(s) for s in row] for row in splits_list if len(row) == 4])
        avg_splits = splits_array.mean(axis=0)
        front_pct, back_pct, differential = calculate_pacing(avg_splits)
        result[stroke] = {'front_pct': front_pct, 'back_pct': back_pct, 'differential': differential}
    return result

def get_100_split_place_correlation(df, gender):
    # for each 100 of stroke, calculate the correlation between each 25 split and final place
    events = {
        'freestyle': f'{gender} 100 Yard Freestyle',
        'backstroke': f'{gender} 100 Yard Backstroke',
        'breaststroke': f'{gender} 100 Yard Breaststroke',
        'butterfly': f'{gender} 100 Yard Butterfly',
    }
    correlations = {}
    # for each event of interest
    for stroke, event_name in events.items():
        event = df[df['EVENT_NAME'] == event_name]
        # extract place, splits
        places = event['PLACE'].values
        splits = event['SPLITS_50'].tolist()
        # Calculate correlation between reaction time and place for this event
        split_corrs = {}
        # calculate split for each leg of the race
        for pos in range(4):
            split_vals = [ float(swimmer[pos]) for swimmer in splits if len(swimmer) > pos ]
            r = np.corrcoef(places[:len(split_vals)], split_vals)[0,1]
            split_corrs[f'split_{pos + 1}'] = round(r,3)
        correlations[stroke] = split_corrs
    # largest correlation -> best indicator of winning
    return correlations

def get_reaction_time_place_correlation(df, gender):
    events = {
        '50 Free': f'{gender} 50 Yard Freestyle',
        '100 Free': f'{gender} 100 Yard Freestyle',
        '200 Free': f'{gender} 200 Yard Freestyle',
        '500 Free': f'{gender} 500 Yard Freestyle',
        '1650 Free': f'{gender} 1650 Yard Freestyle',
    }
    correlations = {}
    for distance, event_name in events.items():
        event = df[df['EVENT_NAME'] == event_name]
        scoring = event[event['PLACE'] <= 16 ].dropna(subset=['REACTION'])
        places = scoring['PLACE'].values
        reactions = scoring['REACTION'].values
        r = np.corrcoef(places, reactions)[0,1]
        correlations[distance] = round(r,3)
    return correlations

def get_400_im_breakdown(df, gender):
    four_hundred_im = df[df['EVENT_NAME'] == f'{gender} 400 Yard IM']
    scoring = four_hundred_im[four_hundred_im['PLACE'] <= 16]
    splits = scoring['SPLITS_50'].tolist()
    leg_times = {
        'Butterfly': [],
        'Backstroke': [],
        'Breaststroke': [],
        'Freestyle': []
    }
    for swimmer_splits in splits:
        if len(swimmer_splits) == 8:
            leg_times['Butterfly'].append(float(swimmer_splits[0]) + float(swimmer_splits[1]))
            leg_times['Backstroke'].append(float(swimmer_splits[2]) + float(swimmer_splits[3]))
            leg_times['Breaststroke'].append(float(swimmer_splits[4]) + float(swimmer_splits[5]))
            leg_times['Freestyle'].append(float(swimmer_splits[6]) + float(swimmer_splits[7]))
    for leg, times in leg_times.items():
        leg_times[leg] = round(np.std(times), 3)
    return leg_times

# ~~~~~~~~~~~~~~~~~~~~~ plotting functions ~~~~~~~~~~~~~~~~~~~~~

def plot_200_pacing(pacing_data):
    events = list(pacing_data.keys())
    front_pcts = [pacing_data[i]['front_pct'] * 100 for i in events]
    back_pcts = [pacing_data[i]['back_pct'] * 100 for i in events]

    x = range(len(events))
    plt.bar(x,front_pcts, label = 'First 100', color='#DC143C')
    plt.bar(x, back_pcts, bottom=front_pcts, label = 'Second 100', color='#4169E1')
    plt.xticks(x, events)
    plt.ylabel('% of Race')
    plt.title('200 Pacing Breakdown by Stroke')
    plt.ylim(45, 55)
    plt.legend()
    plt.show()

def plot_mile_splits(mile_data):
    gold, silver, sixteenth = mile_data
    # adjust frame
    plt.figure(figsize=(12,5))
    plt.plot(range(1,len(gold) + 1), gold, label = '1st Place', color='gold', marker='o', markersize=4)
    plt.plot(range(1,len(gold) + 1), silver, label = '2nd Place', color='silver', marker='o', markersize=4)
    # plt.plot(range(1,len(gold) + 1), bronze, label = '3rd Place', color='#cd7f32', marker='o')
    plt.plot(range(1,len(gold) + 1), sixteenth, label = '16th Place', color='gray', linestyle='dashed', marker='o', markersize=4)
    plt.xlabel('Split Number (Each 50 Yards)')
    plt.ylabel('Time (s)')
    plt.title('1650 Freestyle Split Comparison by Place')
    plt.tight_layout()
    plt.ylim(22, 28)

    plt.legend()
    plt.show()

def plot_100_split_correlation(correlation_data):
    strokes = list(correlation_data.keys())
    x = np.arange(len(strokes))
    # width of bars
    width = 0.2

    plt.bar(x - 1.5 * width, [correlation_data[s]['split_1'] for s in strokes], width, label = 'Split 1 (0-25yd)', color='#DC143C')
    plt.bar(x - 0.5 * width, [correlation_data[s]['split_2'] for s in strokes], width, label = 'Split 2 (25-50yd)',color='#4169E1')
    plt.bar(x + 0.5 * width, [correlation_data[s]['split_3'] for s in strokes], width, label = 'Split 3 (50-75yd)',color='#11C611')
    plt.bar(x + 1.5 * width, [correlation_data[s]['split_4'] for s in strokes], width, label = 'Split 4 (75-100yd)',color="#D1EB13")

    plt.xticks(x,strokes)
    plt.ylabel('Correlation with Place')
    plt.title('100 Split Correlation with Final Place by Stroke')

    plt.legend()
    plt.show()

def plot_reaction_time_correlation(correlation_data):
    distances = list(correlation_data.keys())
    correlations = list(correlation_data.values())
    x = np.arange(len(distances))

    plt.bar(distances, correlations, color='skyblue')
    plt.axhline(y=0, color='black',linewidth=0.8)
    plt.xticks(x,distances)
    plt.ylabel('Correlation with Place')
    plt.xlabel('Event Distance')
    plt.title('Reaction Time Correlation to Final Place across Freestyle Disciplines')

    plt.show()

def plot_400_im_breakdown(im_data):
    legs = list(im_data.keys())
    stdevs = list(im_data.values())

    plt.bar(legs, stdevs, color=['#DC143C', '#4169E1', "#11C611", "#D1EB13"])
    plt.ylabel('Standard Deviation (s)')
    plt.title('400 IM: Variability by Leg (Top 16)')
    plt.axhline(y=sum(stdevs)/len(stdevs), color='black', linestyle='--', label='Average')
    plt.legend()
    plt.show()

def main():
    # parse cmdline args
    file_name = None
    demo = False
    if len(sys.argv) > 2:
        print('Error: Too many arguments provided')
        sys.exit(1)
    elif len(sys.argv) == 1:
        print('Error: Must provide a csv file to analyze')
        sys.exit(1)
    else:
        if sys.argv[1] in ['-d', '--demo']:
            demo = True
            file_name = 'ncaa_2026_results.csv'
        elif not os.path.exists(sys.argv[1]):
            print('Error: file does not exist')
            sys.exit(1)
        else:
            file_name = sys.argv[1]

    df, gender = load_data(file_name)

    menu = {
        '1': ('1650 Free split comparison (1st vs 2nd vs 16th)', lambda: plot_mile_splits(get_1650_split_comparison(df, gender))),
        '2': ('200 pacing breakdown by stroke', lambda: plot_200_pacing(get_200_pacing(df, gender))),
        '3': ('100 split correlation with final place', lambda: plot_100_split_correlation(get_100_split_place_correlation(df, gender))),
        '4': ('Reaction time correlation with final place', lambda: plot_reaction_time_correlation(get_reaction_time_place_correlation(df, gender))),
        '5': ('400 IM variability by leg', lambda: plot_400_im_breakdown(get_400_im_breakdown(df, gender))),
    }

    # demo mode - run all analyses and show all plots
    if demo:
        for key, (label, func) in menu.items():
            print(f'\n--- {label} ---')
            func()
        return
    
    # interactive mode
    while True:
        print('\n--- NCAA Swim Analysis ---')
        for key, (label, _) in menu.items():
            print(f'  {key}. {label}')
        print('  q. Quit')
        choice = input('Select an analysis: ').strip().lower()
        if choice == 'q':
            break
        if choice in menu:
            menu[choice][1]()
        else:
            print('Invalid choice.')

if __name__ == '__main__':
    main()