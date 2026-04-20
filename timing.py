#!/usr/local/bin/python3

'''
benchmark the 5 analysis functions on the full csv vs a sliced section
'''

import time
import pandas as pd
import create_csv
from analyze import load_data, get_100_split_place_correlation, get_1650_split_comparison, get_200_pacing, get_400_im_breakdown, get_reaction_time_place_correlation

def create_it():
    start = time.time()
    create_csv.main()
    finish = time.time()
    elapsed = finish - start
    print(f'CSV creation took {elapsed:.4f} seconds')
    return elapsed

def time_it(df, gender, name):
    start = time.time()
    try:
        get_1650_split_comparison(df, gender)
    except:
        pass

    get_200_pacing(df,gender)
    get_100_split_place_correlation(df, gender)
    get_reaction_time_place_correlation(df, gender)
    get_400_im_breakdown(df,gender)
    finish = time.time()
    elapsed = finish - start
    print(f'{name:<15}| {len(df)} rows in {elapsed:.4f} seconds')
    return elapsed

def main():
    df, gender = load_data('ncaa_2026_results.csv')
    sample = df.groupby('EVENT_NAME').head(8)

    print('~~~ Timing Analysis for create_csv.py ~~~')
    print()
    create_time = create_it()
    print()

    print('~~~ Timing Analysis for analyze.py ~~~')
    print()

    full_time = time_it(df, gender, 'Full dataset')
    sample_time = time_it(sample, gender, 'Sliced dataset')

    ratio_rows = len(df) / len(sample)
    ratio_time = full_time / sample_time
    print()
    print(f'Full Dataset has {ratio_rows} times as many rows as sample dataset')
    print(f'Full Dataset is {ratio_time} times slower than sample dataset')
    print()

if __name__ == '__main__':
    main()