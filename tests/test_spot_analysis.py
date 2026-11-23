import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import spot_analysis as sa  # noqa: E402

H4 = 4 * 3600 * 1000


def make(points, step=H4):
    """points: list of (high, low); closes sit mid-range."""
    return [{"t": 1700000000000 + i * step, "o": (h + l) / 2, "h": h, "l": l, "c": (h + l) / 2}
            for i, (h, l) in enumerate(points)]


UP = [(10, 8), (11, 9), (13, 10), (12, 10), (11, 9.5), (12, 10.5), (15, 12),
      (14, 12), (13, 11), (14, 12.5), (17, 14), (16, 14), (15.5, 13.5)]
DOWN = [(30 - h, 30 - l) for h, l in [(l, h) for h, l in UP]]


class SpotAnalysisTest(unittest.TestCase):
    def test_bullish_when_highs_and_lows_rise(self):
        self.assertEqual(sa.classify(make(UP), 2)["trend"], "BULLISH")

    def test_bearish_when_highs_and_lows_fall(self):
        self.assertEqual(sa.classify(make(DOWN), 2)["trend"], "BEARISH")

    def test_levels_bracket_the_close(self):
        r = sa.classify(make(UP), 2)
        self.assertGreater(r["bull_level"], r["close"])
        self.assertLess(r["bear_level"], r["close"])

    def test_forming_candle_is_dropped(self):
        candles = make(UP)
        now = candles[-1]["t"] + H4 - 1  # last candle not finished yet
        self.assertEqual(len(sa.completed_only(candles, H4, now)), len(candles) - 1)

    def test_parses_raw_api_shape_and_sorts(self):
        payload = {"code": 0, "result": {"data": [
            {"t": 1700000002000, "o": "1", "h": "2", "l": "0.5", "c": "1.5"},
            {"t": 1700000001000, "o": "1", "h": "2", "l": "0.5", "c": "1.2"}]}}
        out = sa.parse_candles(payload)
        self.assertEqual([c["t"] for c in out], [1700000001000, 1700000002000])

    def test_malta_time_switches_with_eu_summer_time(self):
        winter = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        summer = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)
        self.assertEqual(sa.to_malta(winter)[1], "CET")
        self.assertEqual(sa.to_malta(winter)[0].hour, 13)
        self.assertEqual(sa.to_malta(summer)[1], "CEST")
        self.assertEqual(sa.to_malta(summer)[0].hour, 14)
        # Change-over instants (last Sunday of March / October, 01:00 UTC)
        self.assertEqual(sa.to_malta(datetime(2026, 3, 29, 1, tzinfo=timezone.utc))[1], "CEST")
        self.assertEqual(sa.to_malta(datetime(2026, 10, 25, 1, tzinfo=timezone.utc))[1], "CET")


if __name__ == "__main__":
    unittest.main()
