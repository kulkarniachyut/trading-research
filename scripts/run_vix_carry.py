"""VIX term-structure / short-vol carry — go-wide brick #6 (highest-Sharpe retail edge).

VIX futures are in contango ~80% of days, so long-vol ETFs (VIXY) bleed and shorting them
harvests the roll. Risk-managed: short VIXY ONLY when VIX < VIX3M (contango, signal from the
PRIOR close — no look-ahead); flat when VIX >= VIX3M (backwardation/stress). The filter is the
whole strategy — it must dodge the Feb-2018 / Mar-2020 vol spikes, not just collect carry.

Honest accounting: ~3%/yr short borrow on days held + 3bps per position switch. Daily close-to-
close. A high Sharpe with a ruinous single-day drawdown is a FAIL (short-vol's left tail killed
XIV in one day). Pre-registered in docs/STEP4_EDGE_SEARCH_PLAN.md.

Usage: run_vix_carry.py [START_YEAR END_YEAR] [--always-short]   (--always-short = no filter, to
                                                                  show what the filter is worth)
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.core.types import TimeFrame
from src.data.yfinance_provider import YFinanceProvider
from src.validation import monte_carlo

BORROW_DAILY = 0.03 / 252      # ~3%/yr borrow while short
SWITCH_COST = 0.0003           # 3 bps when the position turns on/off
ERAS = [(2011, 2014), (2015, 2018), (2019, 2021), (2022, 2024)]


def _series(prov, sym, s, e):
    d = prov.get_bars(sym, TimeFrame.D1, s, e)
    return d["close"].dropna() if d is not None and len(d) else pd.Series(dtype=float)


def max_dd(curve: np.ndarray) -> float:
    peak = np.maximum.accumulate(curve)
    return float((1 - curve / peak).max())


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2011, 2024)
    if y1 >= 2025:
        raise SystemExit("2025/26 stays sealed")
    filtered = "--always-short" not in sys.argv

    prov = YFinanceProvider()
    s = pd.Timestamp(f"{y0}-01-01", tz="America/New_York")
    e = pd.Timestamp(f"{y1}-12-31", tz="America/New_York")
    vix = _series(prov, "^VIX", s, e)
    vix3m = _series(prov, "^VIX3M", s, e)
    vixy = _series(prov, "VIXY", s, e)
    df = pd.DataFrame({"vix": vix, "vix3m": vix3m, "vixy": vixy}).dropna()
    df["vixy_ret"] = df["vixy"].pct_change()
    # contango signal from the PRIOR close (no look-ahead)
    df["contango"] = (df["vix"] < df["vix3m"]).shift(1).fillna(False)
    short_on = df["contango"] if filtered else pd.Series(True, index=df.index)

    # strategy daily return = short VIXY when on; borrow cost while short; switch cost on changes
    pos = short_on.astype(float)
    switch = pos.diff().abs().fillna(0)
    df["strat"] = (-pos * df["vixy_ret"]) - (pos * BORROW_DAILY) - (switch * SWITCH_COST)
    r = df["strat"].dropna()
    r = r[(r.index.year >= y0) & (r.index.year <= y1)]

    tag = "contango-filtered" if filtered else "ALWAYS short (no filter)"
    print(f"=== VIX short-vol carry [{tag}]  {y0}-{y1}  ({len(r)} days, "
          f"{pos.mean() * 100:.0f}% time short) ===")
    curve = (1 + r).cumprod().values
    cagr = curve[-1] ** (252 / len(r)) - 1
    sharpe = r.mean() / r.std() * np.sqrt(252)
    dd = max_dd(np.concatenate([[1.0], curve]))
    print(f"  CAGR {cagr * 100:+.1f}%  Sharpe {sharpe:+.2f}  maxDD {dd * 100:.1f}%  "
          f"worst day {r.min() * 100:+.1f}%  best day {r.max() * 100:+.1f}%")
    print("  era split:")
    for a, b in ERAS:
        sub = r[(r.index.year >= a) & (r.index.year <= b)]
        if len(sub):
            c = (1 + sub).cumprod().values
            cg = c[-1] ** (252 / len(sub)) - 1
            sh = sub.mean() / sub.std() * np.sqrt(252) if sub.std() else float("nan")
            print(f"    {a}-{b}: CAGR {cg * 100:+6.1f}%  Sharpe {sh:+.2f}  "
                  f"maxDD {max_dd(np.concatenate([[1.0], c])) * 100:5.1f}%  worst day {sub.min() * 100:+.1f}%")
    mc = monte_carlo(list(r), n_resamples=2000, seed=42)
    print(f"  MC (daily bootstrap): p5 total {mc.p5_total_r * 100:+.0f}%  "
          f"P(<=0) {mc.prob_total_r_le_0 * 100:.1f}%  -> {'SURVIVES' if mc.survives else 'FAILS'}")
    # the tail check: worst 5 single days (volmageddon detector)
    worst = r.nsmallest(5)
    print("  worst 5 days (tail check): " + "  ".join(f"{d.date()} {v * 100:+.1f}%"
                                                      for d, v in worst.items()))


if __name__ == "__main__":
    main()
