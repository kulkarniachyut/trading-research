"""Phase B.5 breadth baseline — run ict_2022 (selective defaults: Silver-Bullet entry + strong
displacement) across a universe of liquid US equities/ETFs and report PORTFOLIO frequency + edge.

The question: across breadth, do we get a *few trades/week* and is the *pooled* expectancy better
than the single-symbol bleed? (Crypto 24/7 is added in B.5.2.) Reference years only — 2025/26 stay
reserved. Usage: run_breadth.py [YEAR ...]   (default 2024)
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.alpaca import AlpacaProvider
from src.strategies.ict.ict_2022 import Ict2022

UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN",
    "META", "GOOGL", "TSLA", "AMD", "NFLX", "JPM", "XLE", "GLD",
]


def main() -> None:
    years = sys.argv[1:] or ["2024"]
    prov = AlpacaProvider()
    universe = [UniverseItem(s) for s in UNIVERSE]
    for yr in years:
        res = run_portfolio(
            lambda: Ict2022({}), universe,
            pd.Timestamp(f"{yr}-01-01", tz="America/New_York"),
            pd.Timestamp(f"{yr}-12-31", tz="America/New_York"),
            provider=prov, base_tf=TimeFrame.M5,
        )
        print(f"\n=== breadth {yr}: {len(res.results)}/{len(universe)} symbols "
              f"({', '.join(res.errors) or 'no errors'}) ===")
        print(f"  trades        : {res.trade_count}   ({res.trades_per_week:.1f}/week)")
        print(f"  win rate      : {res.win_rate:.0f}%")
        print(f"  total net     : {res.total_net:,.0f}  (per-symbol $100k sleeves)")
        print(f"  expectancy    : ${res.expectancy_dollars:,.0f}/trade   ({res.expectancy_r:+.2f} R)")
        print("  per symbol (n / win% / net):")
        for sym, n, win, net in res.per_symbol():
            if n:
                print(f"    {sym:6s} {n:3d}  {win:3.0f}%  {net:8.0f}")


if __name__ == "__main__":
    main()
