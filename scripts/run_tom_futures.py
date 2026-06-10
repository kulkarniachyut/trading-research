"""Turn-of-month cross-asset confirmation — frozen rule on the Databento index futures.

The ETF read (2000-2024, yfinance) passed every pre-registered gate. This is the independent
confirmation: same frozen rule, different data source (Databento 1m archive), different
instrument class (CME index micros), 2017-2024. H1 base for slippage realism (as IBS/TSMOM).
Criteria pre-registered in docs/STEP4_EDGE_SEARCH_PLAN.md before running.

Usage: run_tom_futures.py [START_YEAR END_YEAR]
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass
from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.archive import HOLDOUT_START_YEAR
from src.data.databento_provider import DatabentoProvider
from src.strategies.meanrev.turn_of_month import TurnOfMonth
from src.validation import monte_carlo

FUT = [
    ("ES.c.0", 5.0, 0.25),
    ("NQ.c.0", 2.0, 0.25),
    ("RTY.c.0", 5.0, 0.10),
    ("YM.c.0", 0.50, 1.0),
]
INITIAL_EQUITY = 250_000.0
RISK_PCT = 0.01


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2017, 2024)
    if y1 >= HOLDOUT_START_YEAR:
        raise SystemExit("holdout stays sealed")

    uni = [UniverseItem(s, AssetClass.FUTURE, multiplier=m, tick_size=t) for s, m, t in FUT]
    res = run_portfolio(
        lambda: TurnOfMonth({}), uni,
        pd.Timestamp(f"{y0}-01-01", tz="America/New_York"),
        pd.Timestamp(f"{y1}-12-31", tz="America/New_York"),
        provider=DatabentoProvider(), base_tf=TimeFrame.H1,
        initial_equity=INITIAL_EQUITY, risk_pct=RISK_PCT, max_leverage=4.0,
    )
    risk = RISK_PCT * INITIAL_EQUITY
    trades = [t for r in res.results.values() for t in r.trades]
    print(f"=== turn-of-month FUTURES confirmation  {y0}-{y1}  (R=${risk:,.0f}) ===")
    if res.errors:
        print(f"  errors: {res.errors}")
    if not trades:
        print("  no trades")
        return
    by_year: dict[int, list] = {}
    for t in trades:
        by_year.setdefault(pd.Timestamp(t.exit_ts).year, []).append(t)
    for yr in sorted(by_year):
        ts = by_year[yr]
        net = sum(t.net_pnl for t in ts)
        print(f"  {yr}: {len(ts):3d} tr  net {net:+10,.0f}  exp {net / len(ts) / risk:+.3f}R")
    n = len(trades)
    net = sum(t.net_pnl for t in trades)
    gross = sum(t.gross_pnl for t in trades)
    print(f"  POOLED: {n} tr  win {sum(1 for t in trades if t.net_pnl > 0) / n * 100:.1f}%  "
          f"net {net:+,.0f}  exp {net / n / risk:+.3f}R (gross {gross / n / risk:+.3f}R)")
    for sym, n_s, win_s, net_s in res.per_symbol():
        if n_s:
            print(f"    {sym:8s} {n_s:3d} tr  win {win_s:4.1f}%  net {net_s:+10,.0f}  "
                  f"exp {net_s / n_s / risk:+.3f}R")
    by_month: dict[str, float] = {}
    for t in trades:
        key = pd.Timestamp(t.entry_ts).strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0.0) + t.net_pnl / risk
    mc = monte_carlo(list(by_month.values()), n_resamples=2000, seed=42)
    print(f"  MC month-clustered ({len(by_month)} events): total {mc.observed_total_r:+.1f}R  "
          f"p5 {mc.p5_total_r:+.1f}R  P(<=0) {mc.prob_total_r_le_0 * 100:.1f}%  -> "
          f"{'SURVIVES' if mc.survives else 'FAILS'}")


if __name__ == "__main__":
    main()
