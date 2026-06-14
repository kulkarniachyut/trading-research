"""Pre-holiday effect — go-wide brick #5 (same calendar family as the validated TOM).

Lakonishok-Smidt (1988): the trading session immediately before a market holiday earns
abnormally high returns. Zero external data — holidays come from pandas-market-calendars
(forward-safe, known years ahead). Capture: hold the ETF THROUGH the pre-holiday session
(buy at prior close, sell at the pre-holiday close), ~9 events/yr; apply round-trip equity cost.

Pre-registered in docs/STEP4_EDGE_SEARCH_PLAN.md. Portfolio-level (pooled across ETFs); honest
costs and no look-ahead (the holiday schedule is public ahead of time, like TOM's calendar).

Usage: run_preholiday.py [START_YEAR END_YEAR]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from src.core.types import TimeFrame
from src.data.yfinance_provider import YFinanceProvider
from src.validation import monte_carlo

UNIVERSE = ["SPY", "QQQ", "DIA", "IWM"]
COST_ROUNDTRIP = 0.0006  # ~3 bps/side, equity cost model on a liquid ETF
ERAS = [(2000, 2006), (2007, 2012), (2013, 2018), (2019, 2024)]


def preholiday_dates(y0: int, y1: int) -> set:
    cal = mcal.get_calendar("NYSE")
    sched = cal.schedule(start_date=f"{y0 - 1}-06-01", end_date=f"{y1}-12-31")
    sessions = pd.DatetimeIndex(sched.index).normalize()
    hols = pd.DatetimeIndex([pd.Timestamp(h) for h in cal.holidays().holidays])
    hols = hols[(hols.year >= y0) & (hols.year <= y1)]
    out = set()
    for h in hols:
        before = sessions[sessions < h]
        if len(before):
            out.add(before[-1].normalize())
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2000, 2024)
    if y1 >= 2025:
        raise SystemExit("2025/26 stays sealed")

    pre = preholiday_dates(y0, y1)
    prov = YFinanceProvider()
    start = pd.Timestamp(f"{y0 - 1}-06-01", tz="America/New_York")
    end = pd.Timestamp(f"{y1}-12-31", tz="America/New_York")

    pre_rets: list[float] = []          # net return on pre-holiday hold, pooled across ETFs
    other_rets: list[float] = []        # all other 1-day holds (benchmark)
    dated: list[tuple[pd.Timestamp, float]] = []
    for s in UNIVERSE:
        try:
            d = prov.get_bars(s, TimeFrame.D1, start, end)
        except Exception as exc:  # noqa: BLE001
            print(f"  {s}: fetch failed ({exc})")
            continue
        if d is None or len(d) < 2:
            continue
        c = d["close"].dropna()
        r = c.pct_change().dropna()
        for ts, val in r.items():
            day = pd.Timestamp(ts).tz_localize(None).normalize()
            if y0 <= day.year <= y1 and day in pre:
                net = val - COST_ROUNDTRIP
                pre_rets.append(net)
                dated.append((day, net))
            elif y0 <= day.year <= y1:
                other_rets.append(val)

    if not pre_rets:
        print("no pre-holiday observations")
        return
    pre_a = np.array(pre_rets)
    oth_a = np.array(other_rets)
    t = pre_a.mean() / (pre_a.std(ddof=1) / np.sqrt(len(pre_a)))
    print(f"=== pre-holiday effect  {y0}-{y1}  ({len(pre_a)} pre-holiday holds, "
          f"{len(UNIVERSE)} ETFs) ===")
    print(f"  pre-holiday: mean {pre_a.mean() * 1e4:+.1f} bps/event (NET)  "
          f"win {(pre_a > 0).mean() * 100:.0f}%  t={t:+.2f}")
    print(f"  other days : mean {oth_a.mean() * 1e4:+.1f} bps/day (gross)  "
          f"(pre-holiday edge over baseline: {(pre_a.mean() - oth_a.mean()) * 1e4:+.1f} bps)")
    ann_events = len(pre_a) / (y1 - y0 + 1)
    print(f"  ~{ann_events:.0f} events/yr -> ~{pre_a.mean() * ann_events * 100:+.2f}%/yr gross-of-"
          f"compounding if fully allocated each event")

    print("  era split (net mean bps/event):")
    df = pd.DataFrame(dated, columns=["d", "r"])
    for e0, e1 in ERAS:
        sub = df[(df.d.dt.year >= e0) & (df.d.dt.year <= e1)]["r"]
        if len(sub):
            tt = sub.mean() / (sub.std(ddof=1) / np.sqrt(len(sub))) if sub.std(ddof=1) else float("nan")
            print(f"    {e0}-{e1}: n={len(sub):3d}  {sub.mean() * 1e4:+6.1f} bps  t={tt:+.2f}")

    mc = monte_carlo(list(pre_a), n_resamples=2000, seed=42)
    print(f"  MC: total {mc.observed_total_r * 1e4:+.0f}bps-units  p5 {mc.p5_total_r * 1e4:+.0f}  "
          f"P(<=0) {mc.prob_total_r_le_0 * 100:.1f}%  -> {'SURVIVES' if mc.survives else 'FAILS'}")
    half = df[df.d.dt.year <= (y0 + y1) // 2]["r"]
    if len(half):
        mc2 = monte_carlo(list(half), n_resamples=2000, seed=42)
        print(f"  MC first-half (<= {(y0 + y1) // 2}): p5 {mc2.p5_total_r * 1e4:+.0f}  "
              f"P(<=0) {mc2.prob_total_r_le_0 * 100:.1f}%  -> {'SURVIVES' if mc2.survives else 'FAILS'}")


if __name__ == "__main__":
    main()
