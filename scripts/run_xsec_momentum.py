"""Cross-sectional (relative-strength) momentum — go-wide brick #4.

Classic 12-1 monthly momentum (Jegadeesh-Titman / Faber): each month-end rank a liquid ETF
universe by trailing 12-month return SKIPPING the most recent month (avoids 1-month reversal),
hold the top-K equal-weight, rebalance monthly. The highest-value diversifier in the program —
it buys winners while IBS/TOM buy weakness, so it should be *negatively* correlated to them.

Portfolio-level backtest (cross-symbol ranking can't use the per-symbol event engine), but honest:
- No look-ahead: signal uses month-end-m closes (with the skip), positions are HELD during m+1,
  i.e. entered at the start of m+1 on information fully available at end of m.
- Real cost: per-side cost from the equity cost model applied to rebalance turnover.
Pre-registered criteria in docs/STEP4_EDGE_SEARCH_PLAN.md.

Usage: run_xsec_momentum.py [START_YEAR END_YEAR] [--k 3] [--lookback 12] [--skip 1]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.data.yfinance_provider import YFinanceProvider
from src.core.types import TimeFrame
from src.validation import max_drawdown_r, monte_carlo

UNIVERSE = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB",
            "SPY", "QQQ", "IWM", "EFA", "EEM", "GLD", "TLT"]
COST_PER_SIDE = 0.0003  # ~3 bps, matches cost_model("US","equity") on a liquid ETF
ERAS = [(1999, 2006), (2007, 2012), (2013, 2018), (2019, 2024)]


def _opt(flag: str, default: int) -> int:
    a = sys.argv[1:]
    return int(a[a.index(flag) + 1]) if flag in a else default


def monthly_closes(y0: int, y1: int) -> pd.DataFrame:
    prov = YFinanceProvider()
    start = pd.Timestamp(f"{y0 - 2}-01-01", tz="America/New_York")  # +2y warmup for the lookback
    end = pd.Timestamp(f"{y1}-12-31", tz="America/New_York")
    cols = {}
    for s in UNIVERSE:
        try:
            d = prov.get_bars(s, TimeFrame.D1, start, end)
            if d is not None and len(d):
                cols[s] = d["close"].dropna()
        except Exception as exc:  # noqa: BLE001
            print(f"  {s}: fetch failed ({exc})")
    px = pd.DataFrame(cols)
    # month-end last close per symbol
    return px.resample("ME").last()


def backtest(me: pd.DataFrame, k: int, lookback: int, skip: int, y0: int, y1: int):
    """Return a Series of net monthly portfolio returns indexed by the month they were EARNED."""
    rets = me.pct_change()
    prev_holdings: set[str] = set()
    out: dict[pd.Timestamp, float] = {}
    months = me.index
    for i in range(lookback + 1, len(months) - 1):
        # signal at end of month i: trailing-lookback return skipping the last `skip` months
        past = me.iloc[i - lookback] if i - lookback >= 0 else None
        recent = me.iloc[i - skip]
        if past is None:
            continue
        mom = (recent / past - 1.0)
        ranked = mom.dropna().sort_values(ascending=False)
        if len(ranked) < k:
            continue
        longs = set(ranked.index[:k])
        shorts = set(ranked.index[-k:]) if "--long-short" in sys.argv else set()
        holdings = longs | shorts
        # return EARNED next month (i+1) on info known at end of i; long-short is beta-neutral
        nxt = months[i + 1]
        if nxt.year < y0 or nxt.year > y1:
            prev_holdings = holdings
            continue
        gross = float(rets.loc[nxt, list(longs)].mean())
        if shorts:
            gross -= float(rets.loc[nxt, list(shorts)].mean())
        # turnover cost: names changed across both legs * sides * cost
        legs = 2 * k if shorts else k
        turnover = len(holdings ^ prev_holdings) / (2 * legs) if prev_holdings else 1.0
        cost = turnover * 2 * COST_PER_SIDE
        out[nxt] = gross - cost
        prev_holdings = holdings
    return pd.Series(out).sort_index()


def _stats(label: str, r: pd.Series) -> None:
    if not len(r):
        print(f"  {label}: no data")
        return
    ann = (1 + r.mean()) ** 12 - 1
    sharpe = r.mean() / r.std() * np.sqrt(12) if r.std() else float("nan")
    dd = max_drawdown_r(list(r))  # in return units (approx, on the additive curve)
    print(f"  {label:18s} n={len(r):3d}mo  ann {ann * 100:+6.1f}%  Sharpe {sharpe:+.2f}  "
          f"mo-win {(r > 0).mean() * 100:4.0f}%  maxDD~{dd * 100:4.0f}%")


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (1999, 2024)
    k, lb, skip = _opt("--k", 3), _opt("--lookback", 12), _opt("--skip", 1)
    me = monthly_closes(y0, y1)
    print(f"=== cross-sectional momentum  {y0}-{y1}  univ={len(me.columns)}  top-{k}  "
          f"{lb}-{skip} rule ===")

    r = backtest(me, k, lb, skip, y0, y1)
    bh = me.pct_change().mean(axis=1).dropna()  # equal-weight buy&hold benchmark
    bh = bh[(bh.index.year >= y0) & (bh.index.year <= y1)]

    _stats("momentum (net)", r)
    _stats("buy&hold (EW)", bh)
    print("  era split (momentum net):")
    for e0, e1 in ERAS:
        sub = r[(r.index.year >= e0) & (r.index.year <= e1)]
        if len(sub):
            _stats(f"  {e0}-{e1}", sub)

    mc = monte_carlo(list(r), n_resamples=2000, seed=42)
    print(f"  MC (monthly bootstrap): total {mc.observed_total_r * 100:+.0f}%  "
          f"p5 {mc.p5_total_r * 100:+.0f}%  P(<=0) {mc.prob_total_r_le_0 * 100:.1f}%  -> "
          f"{'SURVIVES' if mc.survives else 'FAILS'}")
    first_half = r[r.index.year <= (y0 + y1) // 2]
    if len(first_half):
        mc2 = monte_carlo(list(first_half), n_resamples=2000, seed=42)
        print(f"  MC first-half ({first_half.index[0].year}-{first_half.index[-1].year}): "
              f"p5 {mc2.p5_total_r * 100:+.0f}%  P(<=0) {mc2.prob_total_r_le_0 * 100:.1f}%  -> "
              f"{'SURVIVES' if mc2.survives else 'FAILS'}")


if __name__ == "__main__":
    main()
