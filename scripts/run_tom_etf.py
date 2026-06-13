"""Turn-of-month on index ETFs, 2000-2024 — pre-registered one-shot read (Step 4, family 5).

Theory-fixed spec (see ``TurnOfMonth``), market entry (12 trades/yr/symbol — the ~7-session
hold makes taker friction a small share of R, unlike the intraday families). GLD is the
non-equity control: the effect is a month-end equity-flow story, so gold *should* be weaker.

Usage: run_tom_etf.py [START_YEAR END_YEAR]
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.yfinance_provider import YFinanceProvider
from src.strategies.meanrev.turn_of_month import TurnOfMonth
from src.validation import monte_carlo

ETFS = ["SPY", "QQQ", "DIA", "IWM", "GLD"]  # GLD = control
INITIAL_EQUITY = 100_000.0
RISK_PCT = 0.005
ERAS = [(2000, 2008), (2009, 2016), (2017, 2022), (2023, 2024)]


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2000, 2024)
    if y1 >= 2025:
        raise SystemExit("2025/26 stays sealed")

    res = run_portfolio(
        lambda: TurnOfMonth({}), [UniverseItem(s) for s in ETFS],
        pd.Timestamp(f"{y0}-01-01", tz="America/New_York"),
        pd.Timestamp(f"{y1}-12-31", tz="America/New_York"),
        provider=YFinanceProvider(), base_tf=TimeFrame.D1,
        initial_equity=INITIAL_EQUITY, risk_pct=RISK_PCT, max_leverage=2.0,
    )
    risk = RISK_PCT * INITIAL_EQUITY
    trades = [t for r in res.results.values() for t in r.trades]
    print(f"=== turn-of-month ETFs  {y0}-{y1}  {len(res.results)}/{len(ETFS)} symbols "
          f"(R=${risk:,.0f}) ===")
    if res.errors:
        print(f"  errors: {res.errors}")
    if not trades:
        print("  no trades")
        return

    for e0, e1 in ERAS:
        ts = [t for t in trades if e0 <= pd.Timestamp(t.exit_ts).year <= e1]
        if not ts:
            continue
        net = sum(t.net_pnl for t in ts)
        print(f"  {e0}-{e1}  {len(ts):4d} tr  win {sum(1 for t in ts if t.net_pnl > 0) / len(ts) * 100:4.1f}%  "
              f"net {net:+10,.0f}  exp {net / len(ts) / risk:+.3f}R")

    n = len(trades)
    net = sum(t.net_pnl for t in trades)
    gross = sum(t.gross_pnl for t in trades)
    print(f"  POOLED: {n} tr  win {sum(1 for t in trades if t.net_pnl > 0) / n * 100:.1f}%  "
          f"net {net:+,.0f}  exp {net / n / risk:+.3f}R (gross {gross / n / risk:+.3f}R, "
          f"cost {(gross - net) / n / risk:.3f}R/tr)")
    for sym, n_s, win_s, net_s in res.per_symbol():
        if n_s:
            print(f"    {sym:5s} {n_s:4d} tr  win {win_s:4.1f}%  net {net_s:+10,.0f}  "
                  f"exp {net_s / n_s / risk:+.3f}R")
    mc = monte_carlo([t.net_pnl / risk for t in trades], n_resamples=2000, seed=42)
    print(f"  MC pooled: total {mc.observed_total_r:+.1f}R  p5 {mc.p5_total_r:+.1f}R  "
          f"P(<=0) {mc.prob_total_r_le_0 * 100:.1f}%  -> {'SURVIVES' if mc.survives else 'FAILS'}")
    pre17 = [t.net_pnl / risk for t in trades if pd.Timestamp(t.exit_ts).year < 2017]
    if pre17:
        mc2 = monte_carlo(pre17, n_resamples=2000, seed=42)
        print(f"  MC pre-2017: total {mc2.observed_total_r:+.1f}R  p5 {mc2.p5_total_r:+.1f}R  "
              f"P(<=0) {mc2.prob_total_r_le_0 * 100:.1f}%  -> "
              f"{'SURVIVES' if mc2.survives else 'FAILS'}")

    # Clustered MC: all symbols trade the SAME monthly window, so per-trade resampling
    # understates variance. Aggregate R per month-event and bootstrap months instead —
    # the honest unit of independence (~N months, not N_trades).
    by_month: dict[str, float] = {}
    for t in trades:
        key = pd.Timestamp(t.entry_ts).strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0.0) + t.net_pnl / risk
    mc3 = monte_carlo(list(by_month.values()), n_resamples=2000, seed=42)
    print(f"  MC month-clustered ({len(by_month)} events): total {mc3.observed_total_r:+.1f}R  "
          f"p5 {mc3.p5_total_r:+.1f}R  P(<=0) {mc3.prob_total_r_le_0 * 100:.1f}%  -> "
          f"{'SURVIVES' if mc3.survives else 'FAILS'}")


if __name__ == "__main__":
    main()
