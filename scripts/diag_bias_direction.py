"""exp-007 — Daily-bias direction diagnostic: is our compass inverted?

Pure directional study (no engine, no costs): for each session day, compute the daily bias from the
*completed* daily bars before it, then check whether that bias predicts the day's own open→close move.

We race three bias rules on the same days:
  • current        — `daily_rebalance()` as shipped (purge/revert keys off a WICK; ignores the close).
  • close_confirmed — candidate fix: sweep + the daily CLOSE relative to the swept level
                      (close back inside = reversal; close beyond = continuation) — the "next-day model".
  • continuation   — naive baseline: yesterday's candle color continues.

Headline number per rule: mean **signed return** = bias.direction × (close−open)/open, in bps. If the
current rule's signed return is negative, COUNTER-bias beats aligned → the compass is inverted
(confirms exp-006). Broken down by `basis` to localize where it breaks.

Causal: bias for day t uses only daily bars strictly before t, and t's open as the price reference.
Reference years only — 2025/26 stay reserved. Usage: diag_bias_direction.py [YEAR] [SYM ...]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.data.yfinance_provider import YFinanceProvider
from src.core.types import TimeFrame
from src.strategies.ict.ict_2022._bias import daily_rebalance

EQUITIES = [
    "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN",
    "META", "GOOGL", "TSLA", "AMD", "NFLX", "JPM", "XLE", "GLD",
]


def bias_close_confirmed(d1: pd.DataFrame, price: float, lookback: int = 3) -> int:
    """Candidate fix: daily bias from yesterday's sweep + CLOSE vs the swept level (the next-day model)."""
    if len(d1) < 2:
        return 0
    last, prior = d1.iloc[-1], d1.iloc[-2]
    lo, hi, cl = float(last["low"]), float(last["high"]), float(last["close"])
    plo, phi = float(prior["low"]), float(prior["high"])
    swept_low = lo < plo
    swept_high = hi > phi
    if swept_low and not swept_high:
        return 1 if cl > plo else -1      # closed back inside -> bull reversal; closed below -> bear cont.
    if swept_high and not swept_low:
        return -1 if cl < phi else 1      # closed back inside -> bear reversal; closed above -> bull cont.
    return 0                              # both/neither side swept -> no call


def bias_continuation(d1: pd.DataFrame, price: float) -> int:
    """Naive baseline: yesterday's body direction continues today."""
    if len(d1) < 1:
        return 0
    last = d1.iloc[-1]
    if last["close"] > last["open"]:
        return 1
    if last["close"] < last["open"]:
        return -1
    return 0


# --- exp-008: isolate + sharpen the purge-revert (sweep→reversal) component ------------------------
def _swept(d1: pd.DataFrame) -> tuple[bool, bool, float, float, float]:
    last, prior = d1.iloc[-1], d1.iloc[-2]
    plo, phi, cl = float(prior["low"]), float(prior["high"]), float(last["close"])
    return float(last["low"]) < plo, float(last["high"]) > phi, plo, phi, cl


def purge_revert_only(d1: pd.DataFrame, price: float) -> int:
    """Pure sweep→revert: yesterday swept ONE side of the prior day → revert (no FVG/pd fallback)."""
    if len(d1) < 2:
        return 0
    spl, sph, *_ = _swept(d1)
    if spl and not sph:
        return 1
    if sph and not spl:
        return -1
    return 0


def purge_revert_close(d1: pd.DataFrame, price: float) -> int:
    """Top-trader 'show me rejection': a sweep only counts as a reversal if it CLOSED back inside the
    prior range (a failed sweep). Closed beyond the swept level → stand aside (that's continuation)."""
    if len(d1) < 2:
        return 0
    spl, sph, plo, phi, cl = _swept(d1)
    if spl and not sph:
        return 1 if cl > plo else 0
    if sph and not spl:
        return -1 if cl < phi else 0
    return 0


def purge_revert_cont(d1: pd.DataFrame, price: float) -> int:
    """Failed sweep (closed back inside) → revert; sweep that closed BEYOND → trade the continuation."""
    if len(d1) < 2:
        return 0
    spl, sph, plo, phi, cl = _swept(d1)
    if spl and not sph:
        return 1 if cl > plo else -1
    if sph and not spl:
        return -1 if cl < phi else 1
    return 0


def evaluate(records: list[tuple[int, float]]) -> dict:
    """records = (direction, realized_open_to_close_return). Drops direction==0 (no call)."""
    called = [(d, r) for d, r in records if d != 0]
    if not called:
        return {"n": 0, "hit": 0.0, "signed_bps": 0.0, "t": 0.0}
    dirs = np.array([d for d, _ in called])
    rets = np.array([r for _, r in called])
    signed = dirs * rets
    hit = float(np.mean(np.sign(rets) == dirs))
    mean_bps = float(signed.mean() * 1e4)
    t = float(signed.mean() / (signed.std(ddof=1) / np.sqrt(len(signed)))) if len(signed) > 1 and signed.std() > 0 else 0.0
    return {"n": len(called), "hit": hit * 100, "signed_bps": mean_bps, "t": t}


def fmt(name: str, m: dict, total_days: int) -> str:
    cov = m["n"] / total_days * 100 if total_days else 0.0
    return (f"  {name:16s} n={m['n']:4d} ({cov:4.0f}% of days)  hit={m['hit']:5.1f}%  "
            f"signed={m['signed_bps']:+6.1f} bps/day  t={m['t']:+5.2f}")


def main() -> None:
    args = sys.argv[1:]
    year = next((a for a in args if a.isdigit()), "2024")
    symbols = [a for a in args if not a.isdigit()] or EQUITIES
    start = pd.Timestamp(f"{year}-01-01", tz="America/New_York")
    end = pd.Timestamp(f"{year}-12-31", tz="America/New_York")
    warm = start - pd.Timedelta(days=40)   # warmup so the first January days have prior history
    prov = YFinanceProvider()

    variants = {
        "current": lambda d1, op: daily_rebalance(d1, op, lookback=3).direction,
        "close_confirmed": bias_close_confirmed,
        "continuation": bias_continuation,
        "purge_revert_only": purge_revert_only,
        "purge_revert_close": purge_revert_close,
        "purge_revert_cont": purge_revert_cont,
    }
    recs: dict[str, list[tuple[int, float]]] = {k: [] for k in variants}
    by_basis: dict[str, list[tuple[int, float]]] = {}
    total_days = 0

    print(f"\nexp-007 daily-bias direction diagnostic — {year}, {len(symbols)} symbols (yfinance D1)\n")
    for sym in symbols:
        try:
            d1 = prov.get_bars(sym, TimeFrame.D1, warm, end)
        except Exception as e:  # noqa: BLE001
            print(f"  {sym}: fetch failed: {e}")
            continue
        if d1 is None or d1.empty:
            continue
        for i in range(4, len(d1)):
            if d1.index[i] < start:        # warmup days build history but aren't scored
                continue
            prior = d1.iloc[:i]
            day = d1.iloc[i]
            op, clo = float(day["open"]), float(day["close"])
            if op <= 0:
                continue
            ret = (clo - op) / op
            total_days += 1
            for name, fn in variants.items():
                recs[name].append((fn(prior, op), ret))
            draw = daily_rebalance(prior, op, lookback=3)
            if draw.direction != 0:
                by_basis.setdefault(draw.basis, []).append((draw.direction, ret))

    print(f"total session-days evaluated: {total_days}\n")
    for name in variants:
        print(fmt(name, evaluate(recs[name]), total_days))

    # exp-008 side-split: is the trend-fade bleed concentrated on one side? (long = fade low sweeps,
    # short = fade high sweeps). If shorts bleed in a bull year, a weekly-direction gate fixes it.
    print("\n  purge_revert_close by side (long=fade-low-sweep, short=fade-high-sweep):")
    pc = recs["purge_revert_close"]
    longs = [r for d, r in pc if d == 1]
    shorts = [r for d, r in pc if d == -1]
    if longs:
        print(f"    long   n={len(longs):4d}  mean={np.mean(longs)*1e4:+6.1f} bps  hit={np.mean(np.array(longs)>0)*100:4.1f}%")
    if shorts:
        print(f"    short  n={len(shorts):4d}  mean={np.mean(shorts)*1e4:+6.1f} bps (want <0)  hit={np.mean(np.array(shorts)<0)*100:4.1f}%")

    print("\n  current bias by basis:")
    for basis, recs in sorted(by_basis.items()):
        print(fmt(f"    {basis}", evaluate(recs), total_days))
    print("\n  read: signed<0 ⇒ counter-bias beats aligned (compass inverted). "
          "hit% near 50 ⇒ no directional information.\n")


if __name__ == "__main__":
    main()
