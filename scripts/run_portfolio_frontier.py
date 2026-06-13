"""Risk/return frontier of the two VALIDATED edges (IBS-limit + turn-of-month).

Turns the abstract "+4.8%/yr at 0.5% risk" into the actual menu: at each risk-per-trade
(= leverage) level, what annual return, max drawdown, worst year, and ruin risk does the
combined 2-edge portfolio produce over 2000-2024? This is the decision artifact — it shows
exactly where on the risk/return line the user can sit, and whether the 25-30% bar is reachable
at a survivable drawdown with the edges we actually have.

Honest mechanics: base monthly return series at 0.5%-risk sizing (from the validated portfolio),
scaled by the risk multiple and compounded; margin interest (~5%/yr) charged on the borrowed
fraction when risk > 1x base does not apply here (this is risk-per-trade scaling within an
unlevered cash book until size caps bind, then it's true leverage — noted in output).
No new edge, no tuning — a read on the validated portfolio.

Usage: run_portfolio_frontier.py [START_YEAR END_YEAR]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.yfinance_provider import YFinanceProvider
from src.strategies.meanrev.ibs import IbsRev
from src.strategies.meanrev.turn_of_month import TurnOfMonth

IBS_ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
            "XLU", "XLB", "EFA", "EEM", "GLD"]
TOM_ETFS = ["SPY", "QQQ", "DIA", "IWM"]
EQUITY = 100_000.0
BASE_RISK = 0.005


def monthly_returns(y0: int, y1: int) -> pd.Series:
    prov = YFinanceProvider()
    s = pd.Timestamp(f"{y0}-01-01", tz="America/New_York")
    e = pd.Timestamp(f"{y1}-12-31", tz="America/New_York")
    ibs = run_portfolio(lambda: IbsRev({"limit_entry": True, "limit_ttl_bars": 1}),
                        [UniverseItem(x) for x in IBS_ETFS], s, e, provider=prov,
                        base_tf=TimeFrame.D1, initial_equity=EQUITY, risk_pct=BASE_RISK,
                        max_leverage=2.0, passive_maker=True)
    tom = run_portfolio(lambda: TurnOfMonth({}), [UniverseItem(x) for x in TOM_ETFS], s, e,
                        provider=prov, base_tf=TimeFrame.D1, initial_equity=EQUITY,
                        risk_pct=BASE_RISK, max_leverage=2.0)
    tr = [t for r in ibs.results.values() for t in r.trades] + \
         [t for r in tom.results.values() for t in r.trades]
    risk = BASE_RISK * EQUITY
    by_month: dict[str, float] = {}
    for t in tr:
        key = pd.Timestamp(t.exit_ts).strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0.0) + (t.net_pnl / risk) * BASE_RISK  # -> account %
    idx = pd.PeriodIndex(sorted(by_month), freq="M")
    return pd.Series([by_month[str(p)] for p in idx], index=idx)


def max_dd(curve: np.ndarray) -> float:
    peak = np.maximum.accumulate(curve)
    return float((1 - curve / peak).max())


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2000, 2024)
    r = monthly_returns(y0, y1)
    yrs = (y1 - y0 + 1)
    sharpe = r.mean() / r.std() * np.sqrt(12)
    print(f"=== Risk/return frontier · validated 2-edge portfolio (IBS+TOM) · {y0}-{y1} ===")
    print(f"  base: {len(r)} months, Sharpe {sharpe:.2f} (constant across leverage)\n")
    print(f"  {'risk/trade':>10} {'~leverage':>9} {'CAGR':>7} {'maxDD':>7} {'worstYr':>8} "
          f"{'worstMo':>8} {'ruin?':>6}")
    yearly = r.groupby(r.index.year)
    for mult in (1, 2, 3, 4, 5, 6):
        rr = r * mult
        if (rr <= -1).any():
            print(f"  {BASE_RISK * mult * 100:9.1f}% {mult:8d}x   --- WIPED OUT (a month hit -100%) ---")
            continue
        curve = (1 + rr).cumprod().values
        cagr = curve[-1] ** (1 / yrs) - 1
        dd = max_dd(np.concatenate([[1.0], curve]))
        worst_yr = min((1 + rr[rr.index.year == y]).prod() - 1 for y in range(y0, y1 + 1)
                       if (rr.index.year == y).any())
        worst_mo = rr.min()
        print(f"  {BASE_RISK * mult * 100:9.1f}% {mult:8d}x {cagr * 100:+6.1f}% {dd * 100:6.1f}% "
              f"{worst_yr * 100:+7.1f}% {worst_mo * 100:+7.1f}% {'yes' if dd > 0.9 else 'no':>6}")
    print("\n  Reading: 'risk/trade' is the fraction of equity risked per IBS trade (TOM is")
    print("  equal-notional). 1x = the validated 0.5% baseline. Higher = more aggressive sizing;")
    print("  CAGR and drawdown scale together — that is the whole point. Pick the row whose")
    print("  maxDD you could actually hold through with real money.")


if __name__ == "__main__":
    main()
