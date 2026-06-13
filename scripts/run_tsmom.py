"""Step 4, family 2 — TSMOM on the full 9-future micro basket (design years 2017-2022 ONLY).

One continuous run per symbol (the 252d lookback needs cross-year warm-up, so no per-year
chopping); the first ~year is warm-up and produces no trades. H1 base / D1 decisions — see
``Tsmom`` for why. Sleeves are $250k at 1% risk for integer-contract granularity with micros
under 3-ATR daily stops (a $100k sleeve floors many entries to 0 contracts in high-vol years);
the edge is reported in R (risk-normalized), so sleeve size does not inflate it.

FX micro economics are full-contract/10 approximations (M6E/M6B/M6A; micro-JPY approximated).

Usage: run_tsmom.py [START_YEAR END_YEAR] [--lookback N] [--long-only-report]
"""

from __future__ import annotations

import sys
from collections import defaultdict

import pandas as pd

from src.backtest.costs import AssetClass
from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.archive import HOLDOUT_START_YEAR
from src.data.databento_provider import DatabentoProvider
from src.strategies.momentum.tsmom import Tsmom

# databento continuous symbol -> micro (point value, tick).
FUT = [
    ("ES.c.0", 5.0, 0.25),        # MES
    ("NQ.c.0", 2.0, 0.25),        # MNQ
    ("RTY.c.0", 5.0, 0.10),       # M2K
    ("YM.c.0", 0.50, 1.0),        # MYM
    ("GC.c.0", 10.0, 0.10),       # MGC
    ("6E.c.0", 12_500.0, 0.0001),     # M6E
    ("6B.c.0", 6_250.0, 0.0001),      # M6B
    ("6A.c.0", 10_000.0, 0.0001),     # M6A
    ("6J.c.0", 1_250_000.0, 0.000001),  # micro-JPY approximation
]

INITIAL_EQUITY = 250_000.0
RISK_PCT = 0.01


def _opt(args: list[str], flag: str, default: float) -> float:
    return float(args[args.index(flag) + 1]) if flag in args else default


def main() -> None:
    args = sys.argv[1:]
    years = [a for a in args if a.isdigit() and len(a) == 4]
    y0, y1 = (int(years[0]), int(years[1])) if len(years) >= 2 else (2017, 2022)
    if y1 >= HOLDOUT_START_YEAR:
        raise SystemExit("refusing holdout years")
    lookback = int(_opt(args, "--lookback", 252))

    prov = DatabentoProvider()
    uni = [UniverseItem(s, AssetClass.FUTURE, multiplier=m, tick_size=t) for s, m, t in FUT]
    res = run_portfolio(
        lambda: Tsmom({"lookback": lookback}), uni,
        pd.Timestamp(f"{y0}-01-01", tz="America/New_York"),
        pd.Timestamp(f"{y1}-12-31", tz="America/New_York"),
        provider=prov, base_tf=TimeFrame.H1,
        initial_equity=INITIAL_EQUITY, risk_pct=RISK_PCT, max_leverage=4.0,
    )
    risk = RISK_PCT * INITIAL_EQUITY
    trades = [t for r in res.results.values() for t in r.trades]
    print(f"=== TSMOM lookback={lookback}d  {y0}-{y1}  (H1 base, D1 decisions, micro econ, "
          f"R=${risk:,.0f}) ===")
    if res.errors:
        print(f"  errors: {res.errors}")

    by_year: dict[int, list] = defaultdict(list)
    for t in trades:
        by_year[pd.Timestamp(t.exit_ts).year].append(t)
    for yr in sorted(by_year):
        ts = by_year[yr]
        net = sum(t.net_pnl for t in ts)
        win = sum(1 for t in ts if t.net_pnl > 0) / len(ts) * 100
        print(f"  {yr}: {len(ts):3d} closed tr  win {win:4.1f}%  net {net:+10,.0f}  "
              f"exp {net / len(ts) / risk:+.3f}R")

    if trades:
        n = len(trades)
        net = sum(t.net_pnl for t in trades)
        gross = sum(t.gross_pnl for t in trades)
        win = sum(1 for t in trades if t.net_pnl > 0) / n * 100
        hold = sum(t.bars_held for t in trades) / n
        print(f"  POOLED: {n} tr  win {win:.1f}%  net {net:+,.0f}  "
              f"exp {net / n / risk:+.3f}R (gross {gross / n / risk:+.3f}R, "
              f"cost {(gross - net) / n / risk:.3f}R/tr)  avg hold {hold:.0f} H1 bars")
        print("  per-symbol:")
        for sym, n_s, win_s, net_s in res.per_symbol():
            if n_s:
                print(f"    {sym:8s} {n_s:3d} tr  win {win_s:4.1f}%  net {net_s:+10,.0f}  "
                      f"exp {net_s / n_s / risk:+.3f}R")


if __name__ == "__main__":
    main()
