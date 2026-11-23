"""Read-only Hyperliquid prices using only Python's standard library.

No pip install needed, so it runs on tablets (iPad: a-Shell / Pyto; Android: Termux / Pydroid 3).
Cannot trade or move funds.

Usage: python prices_lite.py [COIN ...]
"""
import json
import sys
import urllib.request

API_URL = "https://api.hyperliquid.xyz/info"


def all_mids():
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"type": "allMids"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def main(coins):
    mids = all_mids()
    for coin in coins or ["BTC", "ETH", "SOL", "HYPE"]:
        price = mids.get(coin.upper())
        print(f"{coin.upper():>6}  {price if price else 'not found'}")


if __name__ == "__main__":
    main(sys.argv[1:])
