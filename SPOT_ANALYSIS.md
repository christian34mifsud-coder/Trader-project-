# Crypto.com spot direction check

`spot_analysis.py` reads the latest **completed** daily and 4-hour candles for one
Crypto.com Exchange pair and prints, in plain English:

- whether each timeframe is **BULLISH**, **BEARISH** or **SIDEWAYS**, based on
  whether recent swing highs and swing lows are rising or falling;
- the price a candle must **close above** to strengthen the bullish case, and
  the price it must **close below** to strengthen the bearish case;
- an overall verdict, which is **WAIT** whenever the two timeframes disagree;
- every timestamp in **Malta time** (CET / CEST), with the data source named.

It uses only the Python standard library and Crypto.com's public market-data API.
It never logs in, never places orders, and never asks for passwords, API keys or
recovery phrases.

## Run it on Android

1. Install a Python app, for example **Pydroid 3** from the Play Store (or Termux).
   No extra packages are needed.
2. Copy `spot_analysis.py` to your device and open it in the app.
3. Press **Run** and type the pair when asked, for example `BTC_EUR`.

From a terminal (Termux):

```
python spot_analysis.py BTC_EUR
python spot_analysis.py ETH_EUR --swing 3
```

Use a `_EUR` pair to see prices in euros. Euro pairs can be thinly traded, so
the `_USD` pair may show cleaner swings; the script tells you which currency it
is showing.

## How it decides

- A **swing high** is a candle whose high is above the 2 candles before and after
  it (change with `--swing`). Swing lows mirror this.
- Higher highs **and** higher lows → bullish. Lower highs **and** lower lows →
  bearish. Anything else → sideways.
- The candle that is still forming is always ignored.

A price alert can trigger during a candle even if that candle later closes back
on the other side of the level. The levels here refer to candle **closes**.

This is an educational scenario tool, not financial advice.

## Tests

```
python -m unittest discover -s tests
```
