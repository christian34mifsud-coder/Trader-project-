"""Read-only Hyperliquid market data. No keys needed; cannot trade or move funds.

Usage: .venv/bin/python hyperliquid/prices.py [COIN ...]
"""
import sys

from hyperliquid.info import Info
from hyperliquid.utils import constants


def main(coins):
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    mids = info.all_mids()
    for coin in coins or ["BTC", "ETH", "SOL", "HYPE"]:
        price = mids.get(coin.upper())
        print(f"{coin.upper():>6}  {price if price else 'not found'}")


if __name__ == "__main__":
    main(sys.argv[1:])
