#!/usr/local/bin/python3

import unittest
import os
from analyze import (
    get_1650_split_comparison, 
    load_data, parse_time, 
    calculate_pacing, 
    get_200_pacing, 
    get_100_split_place_correlation, 
    get_reaction_time_place_correlation,
    get_400_im_breakdown
)

class TestData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df, cls.gender = load_data(str("sample.csv"))

    def test_parse_time(self):
        time = "1:23.45"
        expected = 83.45
        self.assertEqual(parse_time(time), expected)

    def test_load_data(self):
        filepath = str("sample.csv")
        df, gender = load_data(filepath)
        self.assertEqual(gender, 'Men')
        self.assertIn('SPLITS_50', df.columns)
        self.assertIn('REACTION', df.columns)
        self.assertIn('EVENT_NAME', df.columns)

    def test_calculate_pacing(self):
        splits = [24.0, 24.0, 26.0, 26.0]
        expected = (0.48, 0.52, 4.0)
        self.assertEqual(calculate_pacing(splits), expected)

    def test_get_1650_split_comparison(self):
        result = get_1650_split_comparison(self.df, self.gender)
        self.assertEqual(3, len(result))
        self.assertEqual(33, len(result[0]))
        self.assertEqual(33, len(result[1]))
        self.assertEqual(33, len(result[2]))
        self.assertEqual(22.73, result[0][-1])

    def test_get_200_pacing(self):
        result = get_200_pacing(self.df, self.gender)
        self.assertEqual(['Butterfly', 'Backstroke', 'Breaststroke', 'Freestyle', 'IM'], list(result.keys()))
        for stroke in result:
            self.assertEqual(3, len(result[stroke]))
            self.assertIsInstance(result[stroke]['front_pct'], float)
            self.assertIsInstance(result[stroke]['back_pct'], float)
            self.assertIsInstance(result[stroke]['differential'], float)

    def test_get_100_split_place_correlation(self):
        result = get_100_split_place_correlation(self.df, self.gender)
        for stroke_corr in result.values():
            for r in stroke_corr.values():
                self.assertLessEqual(r, 1.0)
                self.assertGreaterEqual(r, -1.0)
        
    def test_get_reaction_time_place_correlation(self):
        result = get_reaction_time_place_correlation(self.df, self.gender)
        for r in result.values():
            self.assertLessEqual(r, 1.0)
            self.assertGreaterEqual(r, -1.0)

    def test_400_im_breakdown(self):
        result = get_400_im_breakdown(self.df, self.gender)
        self.assertEqual(4, len(result))
        for stroke in result:
            self.assertIn(stroke, ['Butterfly', 'Backstroke', 'Breaststroke', 'Freestyle'])
            self.assertIsInstance(result[stroke], float)

if __name__ == '__main__':
    unittest.main()
