"""exp-015: ICT 2022 on real CME futures (Databento) — the two-sided, drift-neutral instruments the
model is actually built for. Trades continuous front-month data with MICRO economics (MES/MNQ/…,
what Robinhood offers). Reference years only — 2025/26 stay reserved.

Usage: run_futures.py [YEAR ...] [--long-only]
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass
from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.databento_provider import DatabentoProvider
from src.strategies.ict.ict_2022 import Ict2022

# databento continuous symbol -> micro (point value, tick) economics.
FUT = [
    ("ES.c.0", 5.0, 0.25),   # MES — Micro S&P
    ("NQ.c.0", 2.0, 0.25),   # MNQ — Micro Nasdaq
    ("RTY.c.0", 5.0, 0.10),  # M2K — Micro Russell
    ("YM.c.0", 0.50, 1.0),   # MYM — Micro Dow
    ("GC.c.0", 10.0, 0.10),  # MGC — Micro Gold
]


def _stat(ts: list) -> str:
    if not ts:
        return "  0 tr"
    n = len(ts); w = sum(1 for t in ts if t.net_pnl > 0); net = sum(t.net_pnl for t in ts)
    st = sum(1 for t in ts if t.reason_out == "stop"); tg = sum(1 for t in ts if t.reason_out == "target")
    return f"{n:3d} tr  {w / n * 100:3.0f}% win  net {net:9,.0f}  (stop {st}/tgt {tg})"


def main() -> None:
    args = sys.argv[1:]
    long_only = "--long-only" in args
    years = [a for a in args if a.isdigit()] or ["2023"]
    params = {"long_only": True} if long_only else {}

    prov = DatabentoProvider()
    uni = [UniverseItem(s, AssetClass.FUTURE, multiplier=m, tick_size=t) for s, m, t in FUT]

    for yr in years:
        res = run_portfolio(
            lambda: Ict2022(params), uni,
            pd.Timestamp(f"{yr}-01-01", tz="America/New_York"),
            pd.Timestamp(f"{yr}-12-31", tz="America/New_York"),
            provider=prov, base_tf=TimeFrame.M5,
        )
        trades = [t for r in res.results.values() for t in r.trades]
        longs = [t for t in trades if t.side == "long"]
        shorts = [t for t in trades if t.side == "short"]
        tag = "LONG-ONLY" if long_only else "both"
        print(f"\n=== FUTURES {yr} [{tag}]: {res.trade_count} tr ({res.trades_per_week:.1f}/wk)  "
              f"win {res.win_rate:.0f}%  net {res.total_net:,.0f}  exp {res.expectancy_r:+.3f}R  "
              f"errs={res.errors or 'none'}", flush=True)
        print(f"    long : {_stat(longs)}")
        print(f"    short: {_stat(shorts)}")
        for sym, n, win, net in res.per_symbol():
            if n:
                print(f"    {sym:8s} {n:3d} tr  {win:3.0f}%  {net:9,.0f}")


if __name__ == "__main__":
    main()
