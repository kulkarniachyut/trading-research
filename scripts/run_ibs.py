"""Step 4, family 3 — IBS mean reversion on index micro futures (design years 2017-2022 ONLY).

One continuous run per symbol (200d trend-MA warm-up needs cross-year history). H1 base / D1
decisions; long-only with a trend gate by design (see ``IbsRev``). GC included as a non-equity
control — IBS is documented on *equity* indices, so GC *should* be weaker; if it isn't, suspect
luck rather than signal.

Usage: run_ibs.py [START_YEAR END_YEAR] [--buy-below X] [--exit-above X] [--no-trend-gate]
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
from src.strategies.meanrev.ibs import IbsRev

FUT = [
    ("ES.c.0", 5.0, 0.25),
    ("NQ.c.0", 2.0, 0.25),
    ("RTY.c.0", 5.0, 0.10),
    ("YM.c.0", 0.50, 1.0),
    ("GC.c.0", 10.0, 0.10),   # non-equity control
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
    params = {
        "buy_below": _opt(args, "--buy-below", 0.2),
        "exit_above": _opt(args, "--exit-above", 0.8),
    }
    if "--no-trend-gate" in args:
        params["trend_ma"] = 1  # MA(1) = close — gate always passes

    prov = DatabentoProvider()
    uni = [UniverseItem(s, AssetClass.FUTURE, multiplier=m, tick_size=t) for s, m, t in FUT]
    res = run_portfolio(
        lambda: IbsRev(params), uni,
        pd.Timestamp(f"{y0}-01-01", tz="America/New_York"),
        pd.Timestamp(f"{y1}-12-31", tz="America/New_York"),
        provider=prov, base_tf=TimeFrame.H1,
        initial_equity=INITIAL_EQUITY, risk_pct=RISK_PCT, max_leverage=4.0,
    )
    risk = RISK_PCT * INITIAL_EQUITY
    trades = [t for r in res.results.values() for t in r.trades]
    gate = "no-gate" if "--no-trend-gate" in args else "MA200 gate"
    print(f"=== IBS buy<{params['buy_below']:g} exit>{params['exit_above']:g} [{gate}]  "
          f"{y0}-{y1}  (R=${risk:,.0f}) ===")
    if res.errors:
        print(f"  errors: {res.errors}")

    by_year: dict[int, list] = defaultdict(list)
    for t in trades:
        by_year[pd.Timestamp(t.exit_ts).year].append(t)
    for yr in sorted(by_year):
        ts = by_year[yr]
        net = sum(t.net_pnl for t in ts)
        win = sum(1 for t in ts if t.net_pnl > 0) / len(ts) * 100
        print(f"  {yr}: {len(ts):3d} tr  win {win:4.1f}%  net {net:+10,.0f}  "
              f"exp {net / len(ts) / risk:+.3f}R")

    if trades:
        n = len(trades)
        net = sum(t.net_pnl for t in trades)
        gross = sum(t.gross_pnl for t in trades)
        win = sum(1 for t in trades if t.net_pnl > 0) / n * 100
        print(f"  POOLED: {n} tr  win {win:.1f}%  net {net:+,.0f}  "
              f"exp {net / n / risk:+.3f}R (gross {gross / n / risk:+.3f}R, "
              f"cost {(gross - net) / n / risk:.3f}R/tr)")
        print("  per-symbol:")
        for sym, n_s, win_s, net_s in res.per_symbol():
            if n_s:
                print(f"    {sym:8s} {n_s:3d} tr  win {win_s:4.1f}%  net {net_s:+10,.0f}  "
                      f"exp {net_s / n_s / risk:+.3f}R")


if __name__ == "__main__":
    main()
