"""Crypto ORB (opening-range breakout) on the UTC day — causal, user's named-strategy list.

Crypto is 24/7 so the "open" is arbitrary; the 00:00 UTC daily boundary is the common convention
(and where Binance funding/marks anchor). OR = first `or_bars` 15m bars of the UTC day. Long on a
break above the OR high, short below the OR low; stop at the opposite OR extreme; target = RR×OR
width; flat at UTC day end. Breakout entry takes liquidity → TAKER cost (~6bp). OOS split.

This is the same family that was RETIRED on futures (gross edge real, never clears micro costs).
Testing on crypto for completeness of the user's ORB/IBS/VMC list. Causal by construction (OR is
complete before any breakout is acted on; entry on the bar AFTER the break).

Usage: run_crypto_orb.py [--or-bars 4] [--rr 2] [--cost-bp 6] [--long-only]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from scripts.diag_crypto_intraday import BASKET
from scripts.run_mtf_fvg import fetch_ohlc_15m


def _opt(flag, d, cast=float):
    a = sys.argv[1:]
    return cast(a[a.index(flag) + 1]) if flag in a else d


def backtest(df: pd.DataFrame, or_bars: int, rr: float, cost_bp: float, long_only: bool):
    df = df.copy()
    df["day"] = df.index.normalize()
    trades = []
    for day, g in df.groupby("day"):
        if len(g) < or_bars + 2:
            continue
        opening = g.iloc[:or_bars]
        or_hi, or_lo = opening["high"].max(), opening["low"].min()
        width = or_hi - or_lo
        if width <= 0:
            continue
        rest = g.iloc[or_bars:]
        pos = 0; entry = stop = target = 0.0
        for ts, row in rest.iterrows():
            if pos == 0:
                if row["high"] >= or_hi:                 # break up -> long next (use break level)
                    pos = 1; entry = or_hi; stop = or_lo; target = entry + rr * width
                elif not long_only and row["low"] <= or_lo:
                    pos = -1; entry = or_lo; stop = or_hi; target = entry - rr * width
                continue
            # manage open position (causal: same/next bars)
            if pos == 1:
                if row["low"] <= stop:
                    trades.append(-1.0 - cost_bp / 1e4 / (width / entry)); pos = 0; break
                if row["high"] >= target:
                    trades.append(rr - cost_bp / 1e4 / (width / entry)); pos = 0; break
            else:
                if row["high"] >= stop:
                    trades.append(-1.0 - cost_bp / 1e4 / (width / entry)); pos = 0; break
                if row["low"] <= target:
                    trades.append(rr - cost_bp / 1e4 / (width / entry)); pos = 0; break
        if pos != 0:  # EOD flat -> mark at last close in R
            last = g.iloc[-1]["close"]
            r = (last - entry) / width * pos - cost_bp / 1e4 / (width / entry)
            trades.append(r)
    return trades


def main() -> None:
    or_bars = _opt("--or-bars", 4, int); rr = _opt("--rr", 2.0); cost_bp = _opt("--cost-bp", 6.0)
    long_only = "--long-only" in sys.argv
    print(f"=== CRYPTO ORB  OR={or_bars}x15m({or_bars*15}min) RR={rr} taker={cost_bp}bp "
          f"{'long-only' if long_only else 'long+short'} ===")
    design, oos = [], []
    per_coin = {}
    for sym in BASKET:
        try:
            df = fetch_ohlc_15m(sym)
        except Exception as exc:  # noqa: BLE001
            print(f"  {sym}: {exc}"); continue
        tr = backtest(df, or_bars, rr, cost_bp, long_only)
        # split by trade timestamp not tracked here; re-run split via index of days
        # simpler: recompute with year filter
        per_coin[sym] = np.mean(tr) if tr else 0
    # year split: redo per coin with masks
    for sym in BASKET:
        try:
            df = fetch_ohlc_15m(sym)
        except Exception:  # noqa: BLE001
            continue
        for label, lst in [(2024, design), (2026, oos)]:
            sub = df[df.index.year <= 2024] if label == 2024 else df[df.index.year >= 2025]
            if len(sub) > 100:
                lst += backtest(sub, or_bars, rr, cost_bp, long_only)
    for label, rs in [("DESIGN 2023-24", design), ("OOS 2025-26", oos)]:
        if not rs:
            print(f"  {label}: no trades"); continue
        rs = np.array(rs)
        print(f"  {label:14s} n={len(rs):5d}  exp {rs.mean():+.3f}R  win {(rs>0).mean()*100:4.1f}%  sumR {rs.sum():+.0f}")
    pos = sum(1 for v in per_coin.values() if v > 0)
    print(f"  breadth: {pos}/{len(per_coin)} coins net-positive R (full sample)")


if __name__ == "__main__":
    main()
