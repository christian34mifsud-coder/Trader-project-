#!/usr/bin/env python3
"""
Crypto.com spot-market direction check (standard library only).

What it does
  1. Downloads recent daily (1D) and 4-hour (4h) candles for one trading pair
     from Crypto.com Exchange's public market-data API (no account, no key).
  2. Throws away the candle that is still forming, so only COMPLETED candles
     are used.
  3. Finds swing highs and swing lows and says, in plain English, whether
     they are rising or falling.
  4. Classifies each timeframe as BULLISH, BEARISH or SIDEWAYS.
  5. Prints the level that would strengthen the bullish case (a candle CLOSE
     above it) and the level that would strengthen the bearish case (a candle
     CLOSE below it).
  6. Shows every time in Malta time (CET in winter, CEST in summer).

It only reads public prices. It never logs in, never places or cancels an
order, and never asks for a password, API key or recovery phrase.

How to run on an Android phone or tablet
  * Install a Python app such as "Pydroid 3" (Play Store) or Termux.
    No extra Python packages are needed.
  * Open this file and press Run. It will ask for the pair (e.g. BTC_EUR).
  * Or from a terminal:  python spot_analysis.py BTC_EUR

Options
  python spot_analysis.py PAIR [--swing N] [--file1d PATH --file4h PATH]
    PAIR      Crypto.com Exchange instrument, e.g. BTC_EUR, ETH_EUR, CRO_USD
    --swing   candles needed on EACH side of a swing point (default 2)
    --file1d / --file4h
              analyse saved JSON responses instead of downloading
              (useful with no internet, or for testing)

This is an educational tool, not financial advice. Prices on the Crypto.com
App can differ slightly from the Crypto.com Exchange.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_BASE = "https://api.crypto.com/exchange/v1/public/"
SOURCE_NAME = "Crypto.com Exchange public API (public/get-candlestick)"
TIMEFRAMES = {"1D": 24 * 3600 * 1000, "4h": 4 * 3600 * 1000}
CANDLE_COUNT = 120
USER_AGENT = "spot-analysis-script/1.0"


# --------------------------------------------------------------------------
# Malta time (Europe/Malta). Done by hand because Android Python apps often
# ship without a time-zone database, so zoneinfo can fail there.
# EU rule: summer time (UTC+2) from the last Sunday of March 01:00 UTC
# until the last Sunday of October 01:00 UTC; otherwise UTC+1.
# --------------------------------------------------------------------------
def _last_sunday(year, month):
    # Day after the end of the month, then walk back to Sunday.
    first_next = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc)
    last_day = first_next - timedelta(days=1)
    return last_day - timedelta(days=(last_day.weekday() + 1) % 7)


def to_malta(dt_utc):
    year = dt_utc.year
    start = _last_sunday(year, 3).replace(hour=1)
    end = _last_sunday(year, 10).replace(hour=1)
    if start <= dt_utc < end:
        return dt_utc + timedelta(hours=2), "CEST"
    return dt_utc + timedelta(hours=1), "CET"


def malta_str(ms):
    dt_utc = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    local, label = to_malta(dt_utc)
    return local.strftime("%a %d %b %Y %H:%M ") + label + " (Malta)"


# --------------------------------------------------------------------------
# Data download and parsing
# --------------------------------------------------------------------------
def http_get_json(method, params):
    url = API_BASE + method + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_time(value):
    """Accepts milliseconds, seconds or an ISO-8601 string; returns ms."""
    if isinstance(value, (int, float)):
        return int(value if value > 1e11 else value * 1000)
    text = str(value)
    if text.isdigit():
        return _parse_time(int(text))
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def parse_candles(payload):
    """Turn an API response (or a saved copy of one) into a sorted list."""
    if isinstance(payload, dict):
        if payload.get("code", 0) not in (0, "0"):
            raise ValueError("Crypto.com returned an error: %s" % payload.get("message", payload.get("code")))
        rows = payload.get("result", payload).get("data", [])
    else:
        rows = payload
    candles = []
    for r in rows:
        candles.append({
            "t": _parse_time(r.get("t", r.get("timestamp"))),
            "o": float(r.get("o", r.get("open"))),
            "h": float(r.get("h", r.get("high"))),
            "l": float(r.get("l", r.get("low"))),
            "c": float(r.get("c", r.get("close"))),
        })
    candles.sort(key=lambda x: x["t"])
    # Remove duplicates that can appear at page edges.
    unique = []
    for c in candles:
        if not unique or unique[-1]["t"] != c["t"]:
            unique.append(c)
    return unique


def completed_only(candles, interval_ms, now_ms):
    """Keep candles whose period has fully ended."""
    return [c for c in candles if c["t"] + interval_ms <= now_ms]


def fetch_candles(pair, timeframe):
    payload = http_get_json("get-candlestick", {
        "instrument_name": pair, "timeframe": timeframe, "count": CANDLE_COUNT,
    })
    return parse_candles(payload)


def fetch_last_price(pair):
    try:
        payload = http_get_json("get-tickers", {"instrument_name": pair})
        data = payload.get("result", {}).get("data", [])
        if data:
            return float(data[0]["a"]), _parse_time(data[0]["t"])
    except Exception:
        pass
    return None, None


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------
def find_swings(candles, k):
    """A swing high is a high with k lower highs on each side (lows mirror)."""
    highs, lows = [], []
    for i in range(k, len(candles) - k):
        h, l = candles[i]["h"], candles[i]["l"]
        left = candles[i - k:i]
        right = candles[i + 1:i + 1 + k]
        if all(h > c["h"] for c in left) and all(h >= c["h"] for c in right):
            highs.append((candles[i]["t"], h))
        if all(l < c["l"] for c in left) and all(l <= c["l"] for c in right):
            lows.append((candles[i]["t"], l))
    return highs, lows


def classify(candles, k):
    highs, lows = find_swings(candles, k)
    last = candles[-1]
    close = last["c"]
    result = {"close": close, "close_time": last["t"], "highs": highs, "lows": lows}

    if len(highs) < 2 or len(lows) < 2:
        result["trend"] = "SIDEWAYS"
        result["story"] = "Not enough clear swing points yet to judge direction."
    else:
        (_, h1), (_, h2) = highs[-2], highs[-1]
        (_, l1), (_, l2) = lows[-2], lows[-1]
        hi_word = "higher" if h2 > h1 else "lower" if h2 < h1 else "equal"
        lo_word = "higher" if l2 > l1 else "lower" if l2 < l1 else "equal"
        result["story"] = (
            "The last swing high (%s) was %s than the one before (%s). "
            "The last swing low (%s) was %s than the one before (%s)."
            % (fmt(h2), hi_word, fmt(h1), fmt(l2), lo_word, fmt(l1))
        )
        if hi_word == "higher" and lo_word == "higher":
            trend = "BULLISH"
        elif hi_word == "lower" and lo_word == "lower":
            trend = "BEARISH"
        else:
            trend = "SIDEWAYS"
        # A close beyond the latest swing point overrides a stale pattern.
        if close > h2 and trend != "BULLISH":
            result["story"] += " But price has since closed ABOVE the last swing high."
            trend = "BULLISH" if lo_word != "lower" else "SIDEWAYS"
        elif close < l2 and trend != "BEARISH":
            result["story"] += " But price has since closed BELOW the last swing low."
            trend = "BEARISH" if hi_word != "higher" else "SIDEWAYS"
        result["trend"] = trend

    # Key levels: nearest swing high above the close, nearest swing low below.
    above = [p for _, p in reversed(highs) if p > close]
    below = [p for _, p in reversed(lows) if p < close]
    result["bull_level"] = above[0] if above else max(c["h"] for c in candles)
    result["bull_note"] = "last swing high above price" if above else "highest high in the data (no swing high above price)"
    result["bear_level"] = below[0] if below else min(c["l"] for c in candles)
    result["bear_note"] = "last swing low below price" if below else "lowest low in the data (no swing low below price)"
    return result


def fmt(x):
    if x >= 100:
        return "{:,.2f}".format(x)
    if x >= 1:
        return "{:,.4f}".format(x)
    return "{:.8f}".format(x).rstrip("0")


def verdict(daily, four_hour):
    d, f = daily["trend"], four_hour["trend"]
    if d == f == "BULLISH":
        return "BULLISH (both timeframes agree)"
    if d == f == "BEARISH":
        return "BEARISH (both timeframes agree)"
    return "WAIT (the evidence is mixed)"


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def print_report(pair, results, now_ms, last_price, price_time, source):
    quote = pair.split("_")[-1] if "_" in pair else "?"
    line = "=" * 60
    print(line)
    print("MARKET DIRECTION  -  %s" % pair)
    print(line)
    print("Data source : %s" % source)
    print("Checked at  : %s" % malta_str(now_ms))
    print("Prices in   : %s%s" % (quote, "" if quote == "EUR" else
                                   "  (not euros - try the %s_EUR pair if it exists)" % pair.split("_")[0]))
    if last_price is not None:
        print("Last trade  : %s %s at %s" % (fmt(last_price), quote, malta_str(price_time)))
    print("Only completed candles are used. The candle still forming is ignored.")

    for tf, label in (("1D", "DAILY"), ("4h", "4-HOUR")):
        r = results[tf]
        print()
        print("-- %s: %s --" % (label, r["trend"]))
        print("Latest completed candle: %s" % malta_str(r["close_time"]))
        print("  to %s" % malta_str(r["close_time"] + TIMEFRAMES[tf]))
        print("  closed at %s %s" % (fmt(r["close"]), quote))
        print("What the swings say: " + r["story"])
        print("Bullish case gets stronger on a %s candle CLOSE above %s %s"
              % (label.lower(), fmt(r["bull_level"]), quote))
        print("  (%s)" % r["bull_note"])
        print("Bearish case gets stronger on a %s candle CLOSE below %s %s"
              % (label.lower(), fmt(r["bear_level"]), quote))
        print("  (%s)" % r["bear_note"])

    v = verdict(results["1D"], results["4h"])
    print()
    print(line)
    print("OVERALL: " + v)
    if v.startswith("WAIT"):
        print("What to watch:")
        print("  * A 4-hour close above %s %s would line up with a bullish daily picture."
              % (fmt(results["4h"]["bull_level"]), quote))
        print("  * A 4-hour close below %s %s would line up with a bearish daily picture."
              % (fmt(results["4h"]["bear_level"]), quote))
        print("  * The daily levels above matter more than the 4-hour ones.")
    print()
    print("Remember: a price alert can fire DURING a candle even if that candle")
    print("later closes back on the other side of the level. A 'close above' or")
    print("'close below' only counts once the candle has finished.")
    print("This is a scenario check, not a promise or financial advice.")
    print(line)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Crypto.com spot direction check")
    parser.add_argument("pair", nargs="?", help="e.g. BTC_EUR")
    parser.add_argument("--swing", type=int, default=2, help="candles each side of a swing (default 2)")
    parser.add_argument("--file1d", help="saved JSON for daily candles")
    parser.add_argument("--file4h", help="saved JSON for 4-hour candles")
    parser.add_argument("--now", help=argparse.SUPPRESS)  # ISO time, for testing
    args = parser.parse_args(argv)

    pair = args.pair
    if not pair:
        try:
            pair = input("Trading pair (for example BTC_EUR): ").strip() or "BTC_EUR"
        except EOFError:
            pair = "BTC_EUR"
    pair = pair.upper().replace("/", "_").replace("-", "_")

    now_ms = _parse_time(args.now) if args.now else int(time.time() * 1000)
    offline = bool(args.file1d or args.file4h)
    if offline and not (args.file1d and args.file4h):
        parser.error("give both --file1d and --file4h")

    results = {}
    try:
        for tf, interval in TIMEFRAMES.items():
            if offline:
                with open(args.file1d if tf == "1D" else args.file4h, encoding="utf-8") as fh:
                    candles = parse_candles(json.load(fh))
            else:
                candles = fetch_candles(pair, tf)
            candles = completed_only(candles, interval, now_ms)
            if len(candles) < 2 * args.swing + 3:
                print("Not enough completed %s candles for %s (got %d)." % (tf, pair, len(candles)))
                print("Check the pair name on the Crypto.com Exchange, or send a")
                print("timestamped chart screenshot instead.")
                return 2
            results[tf] = classify(candles, args.swing)
    except (urllib.error.URLError, OSError) as exc:
        print("Could not reach Crypto.com: %s" % exc)
        print("No signal given. Check your internet, or share timestamped chart screenshots.")
        return 1
    except ValueError as exc:
        print(str(exc))
        print("Check that %s is a valid Crypto.com Exchange pair (for example BTC_EUR)." % pair)
        return 1

    last_price, price_time = (None, None) if offline else fetch_last_price(pair)
    source = "saved files (%s, %s)" % (args.file1d, args.file4h) if offline else SOURCE_NAME
    print_report(pair, results, now_ms, last_price, price_time, source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
