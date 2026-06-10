"""IBS breadth scale-up — the FROZEN futures rule on 16 US equity ETFs, 2000-2024 (one shot).

IBS replicated OOS on index futures (+0.028R IS -> +0.026R OOS) but is sub-scale on 5
instruments. This widens the *identical* rule (0.2/0.8/MA200, long-only, 5d time exit, 3-ATR
stop — zero parameter changes) to liquid equity ETFs over 25 years. The instruments and the
pre-2017 era are fresh evidence: criteria pre-registered in docs/STEP4_EDGE_SEARCH_PLAN.md
(pooled exp > 0, breadth >= 60%, MC p5 >= 0, pre-2017 era alone positive).

Accepted conservative biases: yfinance unadjusted prices (dividend ex-dates read as long losses)
and 0.05x *daily*-ATR slippage (overstated for SPY-class liquidity). If it passes under those,
the pass is stronger.

Usage: run_ibs_etf.py [START_YEAR END_YEAR]
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.yfinance_provider import YFinanceProvider
from src.strategies.meanrev.ibs import IbsRev
from src.validation import monte_carlo

# Liquid, long-history US-listed ETFs. GLD is the non-equity control (expects weakest).
ETFS = [
    "SPY", "QQQ", "IWM", "DIA",                                    # broad index
    "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB",  # S&P sectors (1998+)
    "EFA", "EEM",                                                   # international (2001/2003+)
    "GLD",                                                          # control (2004+)
]

INITIAL_EQUITY = 100_000.0
RISK_PCT = 0.005

ERAS = [(2000, 2008), (2009, 2016), (2017, 2022), (2023, 2024)]


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2000, 2024)
    if y1 >= 2025:
        raise SystemExit("2025/26 stays sealed everywhere, including yfinance reads")

    prov = YFinanceProvider()
    uni = [UniverseItem(s) for s in ETFS]  # EQUITY defaults: multiplier 1, bps-spread cost model
    res = run_portfolio(
        lambda: IbsRev({}), uni,
        pd.Timestamp(f"{y0}-01-01", tz="America/New_York"),
        pd.Timestamp(f"{y1}-12-31", tz="America/New_York"),
        provider=prov, base_tf=TimeFrame.D1,
        initial_equity=INITIAL_EQUITY, risk_pct=RISK_PCT, max_leverage=2.0,
    )
    risk = RISK_PCT * INITIAL_EQUITY
    trades = [t for r in res.results.values() for t in r.trades]
    print(f"=== IBS-ETF frozen rule  {y0}-{y1}  {len(res.results)}/{len(ETFS)} symbols  "
          f"(R=${risk:,.0f}) ===")
    if res.errors:
        print(f"  errors: {res.errors}")
    if not trades:
        print("  no trades")
        return

    def _line(tag: str, ts: list) -> None:
        if not ts:
            print(f"  {tag:12s}    0 tr")
            return
        net = sum(t.net_pnl for t in ts)
        win = sum(1 for t in ts if t.net_pnl > 0) / len(ts) * 100
        print(f"  {tag:12s} {len(ts):5d} tr  win {win:4.1f}%  net {net:+12,.0f}  "
              f"exp {net / len(ts) / risk:+.3f}R")

    for e0, e1 in ERAS:
        _line(f"{e0}-{e1}", [t for t in trades if e0 <= pd.Timestamp(t.exit_ts).year <= e1])

    n = len(trades)
    net = sum(t.net_pnl for t in trades)
    gross = sum(t.gross_pnl for t in trades)
    win = sum(1 for t in trades if t.net_pnl > 0) / n * 100
    print(f"  POOLED: {n} tr  win {win:.1f}%  net {net:+,.0f}  exp {net / n / risk:+.3f}R "
          f"(gross {gross / n / risk:+.3f}R, cost {(gross - net) / n / risk:.3f}R/tr)")
    pos = sum(1 for _, n_s, _, net_s in res.per_symbol() if n_s and net_s > 0)
    tot = sum(1 for _, n_s, _, _ in res.per_symbol() if n_s)
    print(f"  breadth+: {pos}/{tot} = {pos / tot * 100:.0f}%")
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


if __name__ == "__main__":
    main()
