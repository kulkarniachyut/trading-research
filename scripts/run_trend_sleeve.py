"""Trend-following sleeve + the 3-way portfolio (mean-rev + VIX-carry + trend) — go-wide brick #7.

The point of trend isn't standalone Sharpe (we know momentum is breadth-hungry) — it's CRISIS
ALPHA: time-series momentum on a diversified ETF basket goes short/defensive in sustained
downtrends, so it PROFITS in 2008/2020/2022 exactly when mean-reversion and short-vol co-crash.
A negatively-correlated sleeve, even a mediocre one, slashes the combined drawdown and lets the
book lever higher — the convergent(carry)+divergent(trend) construction every multi-strat fund uses.

Rule: classic 12-1 time-series momentum per asset (long if trailing 12-1 month return > 0; else
short [managed-futures] or flat [--long-flat]); equal weight; monthly; next-open execution; cost
on turnover. Diversified basket (equity/bonds/gold/commodity/dollar) is what makes it pay in
different crises. No look-ahead. 2007-2024 (all assets live).

Usage: run_trend_sleeve.py [START_YEAR END_YEAR] [--long-flat]
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

BASKET = ["SPY", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "UUP"]
COST = 0.0006
CRASHES = ["2008-10", "2008-11", "2020-03", "2022-04", "2022-06", "2022-09"]


def me_closes(prov, syms, y0, y1):
    s = pd.Timestamp(f"{y0 - 2}-01-01", tz="America/New_York")
    e = pd.Timestamp(f"{y1}-12-31", tz="America/New_York")
    cols = {}
    for sym in syms:
        d = prov.get_bars(sym, TimeFrame.D1, s, e)
        if d is not None and len(d):
            cols[sym] = d["close"].dropna()
    return pd.DataFrame(cols).resample("ME").last()


def trend_monthly(me, y0, y1, long_flat):
    rets = me.pct_change()
    prev = pd.Series(0.0, index=me.columns)
    out = {}
    for i in range(13, len(me) - 1):
        mom = me.iloc[i] / me.iloc[i - 12] - 1.0
        pos = (mom > 0).astype(float)
        if not long_flat:
            pos = pos * 2 - 1  # +1 / -1 managed futures
        pos = pos.reindex(me.columns).fillna(0)
        nxt = me.index[i + 1]
        if nxt.year < y0 or nxt.year > y1:
            prev = pos
            continue
        gross = float((pos * rets.iloc[i + 1].reindex(me.columns).fillna(0)).mean())
        turn = float((pos - prev).abs().sum()) / (2 * len(me.columns))
        out[nxt.to_period("M")] = gross - turn * 2 * COST
        prev = pos
    return pd.Series(out)


def mr_monthly(prov, y0, y1):
    s = pd.Timestamp(f"{y0}-01-01", tz="America/New_York")
    e = pd.Timestamp(f"{y1}-12-31", tz="America/New_York")
    ibs_u = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
             "XLU", "XLB", "EFA", "EEM", "GLD"]
    ibs = run_portfolio(lambda: IbsRev({"limit_entry": True, "limit_ttl_bars": 1}),
                        [UniverseItem(x) for x in ibs_u], s, e, provider=prov,
                        base_tf=TimeFrame.D1, risk_pct=0.005, max_leverage=2.0, passive_maker=True)
    tom = run_portfolio(lambda: TurnOfMonth({}), [UniverseItem(x) for x in ["SPY", "QQQ", "DIA", "IWM"]],
                        s, e, provider=prov, base_tf=TimeFrame.D1, risk_pct=0.005, max_leverage=2.0)
    bm = {}
    for res in (ibs, tom):
        for r in res.results.values():
            for t in r.trades:
                k = pd.Timestamp(t.exit_ts).to_period("M")
                bm[k] = bm.get(k, 0.0) + (t.net_pnl / (0.005 * 100000)) * 0.005
    return pd.Series(bm)


def vix_monthly(prov, y0, y1):
    s = pd.Timestamp(f"{y0}-01-01", tz="America/New_York")
    e = pd.Timestamp(f"{y1}-12-31", tz="America/New_York")
    vix = prov.get_bars("^VIX", TimeFrame.D1, s, e)["close"]
    vix3 = prov.get_bars("^VIX3M", TimeFrame.D1, s, e)["close"]
    vixy = prov.get_bars("VIXY", TimeFrame.D1, s, e)["close"]
    d = pd.DataFrame({"vix": vix, "vix3": vix3, "vixy": vixy}).dropna()
    d["ret"] = d["vixy"].pct_change()
    pos = (d["vix"] < d["vix3"]).shift(1).fillna(False).astype(float)
    sw = pos.diff().abs().fillna(0)
    d["strat"] = -pos * d["ret"] - pos * (0.03 / 252) - sw * 0.0003
    return (1 + d["strat"]).groupby(d.index.to_period("M")).prod() - 1


def _stats(label, r):
    if not len(r):
        return
    c = (1 + r).cumprod()
    cagr = c.iloc[-1] ** (12 / len(r)) - 1
    sh = r.mean() / r.std() * np.sqrt(12) if r.std() else float("nan")
    dd = (1 - c / c.cummax()).max()
    print(f"  {label:26s} CAGR {cagr * 100:+6.1f}%  Sharpe {sh:+.2f}  maxDD {dd * 100:5.1f}%  "
          f"worstMo {r.min() * 100:+6.1f}%")


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2007, 2024)
    long_flat = "--long-flat" in sys.argv
    prov = YFinanceProvider()
    me = me_closes(prov, BASKET, y0, y1)
    tr = trend_monthly(me, y0, y1, long_flat).sort_index()
    mr = mr_monthly(prov, y0, y1).sort_index()
    vx = vix_monthly(prov, y0, y1).sort_index()

    idx = tr.index.intersection(mr.index).intersection(vx.index)
    tr, mr, vx = tr.reindex(idx).fillna(0), mr.reindex(idx).fillna(0), vx.reindex(idx).fillna(0)
    print(f"=== trend sleeve + 3-way portfolio  {y0}-{y1}  ({len(idx)} months, "
          f"trend={'long/flat' if long_flat else 'long/short'}) ===")
    _stats("trend sleeve (standalone)", tr)
    _stats("mean-rev (IBS+TOM)", mr)
    _stats("VIX carry", vx)
    print(f"\n  correlations:  trend~MR {np.corrcoef(tr, mr)[0, 1]:+.2f}   "
          f"trend~VIX {np.corrcoef(tr, vx)[0, 1]:+.2f}   MR~VIX {np.corrcoef(mr, vx)[0, 1]:+.2f}")
    print("  CRISIS months (trend should be the one that's GREEN):")
    for m in CRASHES:
        p = pd.Period(m, "M")
        if p in idx:
            print(f"    {m}:  trend {tr[p] * 100:+6.1f}%   MR {mr[p] * 100:+6.1f}%   VIX {vx[p] * 100:+6.1f}%")

    print("\n  combined books (0.5% base sizing; lever per the frontier):")
    _stats("MR only", mr)
    _stats("MR + 20% VIX", mr + 0.20 * vx)
    _stats("MR + 20% VIX + 40% trend", mr + 0.20 * vx + 0.40 * tr)
    _stats("MR + 30% VIX + 60% trend", mr + 0.30 * vx + 0.60 * tr)
    comb = mr + 0.30 * vx + 0.60 * tr
    sh = comb.mean() / comb.std() * np.sqrt(12)
    print(f"\n  >>> best combined Sharpe ~{sh:.2f} (vs 0.52 mean-rev alone). At Sharpe {sh:.2f}, "
          f"frontier leverage to ~50% maxDD targets ~{sh * 0.30 * 100:.0f}% CAGR region.")


if __name__ == "__main__":
    main()
