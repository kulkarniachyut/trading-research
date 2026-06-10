"""The two-system paper portfolio — IBS-limit + turn-of-month on ETFs, measured together.

Both candidates are validated separately; this measures what the user actually trades: one
account running both. Reports the monthly R streams' correlation (the diversification claim),
combined expectancy, combined month-clustered MC, and the combined drawdown profile.
Read-only over already-validated configurations — no new tuning surface.

Usage: run_two_system_portfolio.py [START_YEAR END_YEAR]
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
from src.validation import max_drawdown_r, monte_carlo

IBS_ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
            "XLU", "XLB", "EFA", "EEM", "GLD"]
TOM_ETFS = ["SPY", "QQQ", "DIA", "IWM"]
INITIAL_EQUITY = 100_000.0
RISK_PCT = 0.005


def _monthly_r(trades, risk: float) -> pd.Series:
    out: dict[str, float] = {}
    for t in trades:
        key = pd.Timestamp(t.entry_ts).strftime("%Y-%m")
        out[key] = out.get(key, 0.0) + t.net_pnl / risk
    return pd.Series(out).sort_index()


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2000, 2024)
    if y1 >= 2025:
        raise SystemExit("2025/26 stays sealed")
    start = pd.Timestamp(f"{y0}-01-01", tz="America/New_York")
    end = pd.Timestamp(f"{y1}-12-31", tz="America/New_York")
    prov = YFinanceProvider()
    risk = RISK_PCT * INITIAL_EQUITY

    ibs_res = run_portfolio(
        lambda: IbsRev({"limit_entry": True, "limit_ttl_bars": 1}),
        [UniverseItem(s) for s in IBS_ETFS], start, end,
        provider=prov, base_tf=TimeFrame.D1, initial_equity=INITIAL_EQUITY,
        risk_pct=RISK_PCT, max_leverage=2.0, passive_maker=True)
    tom_res = run_portfolio(
        lambda: TurnOfMonth({}), [UniverseItem(s) for s in TOM_ETFS], start, end,
        provider=prov, base_tf=TimeFrame.D1, initial_equity=INITIAL_EQUITY,
        risk_pct=RISK_PCT, max_leverage=2.0)

    ibs_tr = [t for r in ibs_res.results.values() for t in r.trades]
    tom_tr = [t for r in tom_res.results.values() for t in r.trades]
    m_ibs = _monthly_r(ibs_tr, risk)
    m_tom = _monthly_r(tom_tr, risk)
    months = sorted(set(m_ibs.index) | set(m_tom.index))
    a = m_ibs.reindex(months).fillna(0.0)
    b = m_tom.reindex(months).fillna(0.0)
    combo = a + b

    print(f"=== two-system ETF portfolio  {y0}-{y1}  (R=${risk:,.0f}/trade) ===")
    print(f"  IBS-limit : {len(ibs_tr):5d} tr  total {a.sum():+7.1f}R   "
          f"({a.sum() / len(months) * 12:+.1f}R/yr)")
    print(f"  TOM       : {len(tom_tr):5d} tr  total {b.sum():+7.1f}R   "
          f"({b.sum() / len(months) * 12:+.1f}R/yr)")
    print(f"  COMBINED  : {len(ibs_tr) + len(tom_tr):5d} tr  total {combo.sum():+7.1f}R   "
          f"({combo.sum() / len(months) * 12:+.1f}R/yr)")
    print(f"  monthly-R correlation(IBS, TOM): {np.corrcoef(a, b)[0, 1]:+.2f}")
    print(f"  max drawdown (monthly R curve): IBS {max_drawdown_r(list(a)):.1f}R  "
          f"TOM {max_drawdown_r(list(b)):.1f}R  COMBINED {max_drawdown_r(list(combo)):.1f}R")
    mc = monte_carlo(list(combo), n_resamples=2000, seed=42)
    print(f"  combined month-clustered MC ({len(months)} months): p5 {mc.p5_total_r:+.1f}R  "
          f"P(<=0) {mc.prob_total_r_le_0 * 100:.1f}%  p95 maxDD {mc.p95_max_dd_r:.1f}R  -> "
          f"{'SURVIVES' if mc.survives else 'FAILS'}")
    # worst combined months — what the account holder must be able to sit through
    worst = combo.nsmallest(3)
    print("  worst months: " + "  ".join(f"{k} {v:+.1f}R" for k, v in worst.items()))


if __name__ == "__main__":
    main()
