"""Breadth runner — ict_2022 across a US equity (+optional crypto) universe; reports PORTFOLIO
frequency + edge, split by side. Reference years only — 2025/26 stay reserved.

Usage: run_breadth.py [YEAR ...] [--long-only] [--equities-only] [--indices-only]
  --long-only     take only long setups (exp-014: stock shorts are drift-doomed)
  --equities-only drop crypto (exp-013: crypto is a %-notional, wrong-session drag)
  --indices-only  SPY/QQQ/IWM/DIA only (exp-013: single-name shorts are the bleed)
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass
from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.alpaca import AlpacaProvider
from src.data.alpaca_crypto import AlpacaCryptoProvider
from src.strategies.ict.ict_2022 import Ict2022

EQUITIES = [
    "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN",
    "META", "GOOGL", "TSLA", "AMD", "NFLX", "JPM", "XLE", "GLD",
]
INDICES = ["SPY", "QQQ", "IWM", "DIA"]
CRYPTO = ["BTCUSD", "ETHUSD", "LTCUSD", "BCHUSD", "SOLUSD", "AVAXUSD", "LINKUSD", "DOGEUSD"]


def _stat(ts: list) -> str:
    if not ts:
        return "  0 tr"
    n = len(ts); w = sum(1 for t in ts if t.net_pnl > 0); net = sum(t.net_pnl for t in ts)
    st = sum(1 for t in ts if t.reason_out == "stop"); tg = sum(1 for t in ts if t.reason_out == "target")
    return f"{n:3d} tr  {w / n * 100:3.0f}% win  net {net:9,.0f}  (stop {st}/tgt {tg})"


def main() -> None:
    args = sys.argv[1:]
    long_only = "--long-only" in args
    equities_only = "--equities-only" in args or "--indices-only" in args
    indices_only = "--indices-only" in args
    years = [a for a in args if a.isdigit()] or ["2024"]
    params = {"long_only": True} if long_only else {}

    prov = AlpacaProvider()
    syms = INDICES if indices_only else EQUITIES
    universe = [UniverseItem(s) for s in syms]
    crypto_prov = None
    if not equities_only:
        crypto_prov = AlpacaCryptoProvider()
        universe += [UniverseItem(s, AssetClass.CRYPTO) for s in CRYPTO]

    for yr in years:
        res = run_portfolio(
            lambda: Ict2022(params), universe,
            pd.Timestamp(f"{yr}-01-01", tz="America/New_York"),
            pd.Timestamp(f"{yr}-12-31", tz="America/New_York"),
            provider=prov, crypto_provider=crypto_prov, base_tf=TimeFrame.M5,
        )
        trades = [t for r in res.results.values() for t in r.trades]
        longs = [t for t in trades if t.side == "long"]; shorts = [t for t in trades if t.side == "short"]
        flags = " ".join(f for f in ("--long-only", "--equities-only", "--indices-only") if f in args) or "full"
        print(f"\n=== breadth {yr} [{flags}]: {len(res.results)}/{len(universe)} symbols "
              f"({', '.join(res.errors) or 'no errors'}) ===", flush=True)
        print(f"  trades     : {res.trade_count}   ({res.trades_per_week:.1f}/week)")
        print(f"  win rate   : {res.win_rate:.0f}%")
        print(f"  total net  : {res.total_net:,.0f}  (per-symbol $100k sleeves)")
        print(f"  expectancy : ${res.expectancy_dollars:,.0f}/trade   ({res.expectancy_r:+.3f} R)")
        print(f"  long  : {_stat(longs)}")
        print(f"  short : {_stat(shorts)}")
        print("  per symbol (n / win% / net):")
        for sym, n, win, net in res.per_symbol():
            if n:
                print(f"    {sym:8s} {n:3d}  {win:3.0f}%  {net:9,.0f}")


if __name__ == "__main__":
    main()
