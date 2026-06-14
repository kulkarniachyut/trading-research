"""Intraday crypto MOMENTUM backtest (1h continuation after extreme moves) — net of real costs.

The diagnostic found crypto is intraday-MOMENTUM not reversion: after a z>THR up-bar, price
continues (+22.7bp/3h at z>3); after z<-THR down-bars it continues down. This may dodge the
breadth wall that killed DAILY momentum because intraday gives thousands of independent events.

Rule (theory-fixed, causal): when the just-completed 1h bar's return z-score (vs trailing 24h vol)
exceeds +THR, go LONG at the next bar's open; below -THR, go SHORT. Hold H hours, exit at market.
Cost: chasing a fast move = take liquidity, so TAKER round-trip (default 10bp — conservative for
Binance; maker would rarely fill on a spike). One position per coin at a time.

Discipline: DESIGN on 2023-2024, one-shot OOS on 2025-2026. Report net bp/trade, trades, win,
per-year, and a rough annualized return at modest sizing. Smooth-variation across THR/H.

Usage: run_intraday_momo.py [--thr 3] [--hold 3] [--cost-bp 10] [--short]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from scripts.diag_crypto_intraday import BASKET, fetch_klines

_BPD = {"1h": 24, "15m": 96, "5m": 288}


def _opt_f(flag, d):
    a = sys.argv[1:]; return float(a[a.index(flag) + 1]) if flag in a else d


def backtest(px: pd.Series, thr: float, hold: int, cost_bp: float, allow_short: bool,
             vol_gate: bool = False, bpd: int = 24, revert: bool = False,
             calm_gate: bool = False):
    r = np.log(px).diff()
    vol = r.rolling(bpd).std()              # ~24h vol in bars
    z = (r / vol)
    # vol-regime gate (causal): trailing 7d realized vol > its trailing 90d median
    rv7 = r.rolling(7 * bpd).std()
    rv_med = rv7.rolling(90 * bpd).median().shift(1)
    regime_on = (rv7.shift(1) > rv_med)
    trades = []
    i = bpd + 1
    n = len(px)
    arr_z = z.values
    arr_p = px.values
    arr_gate = regime_on.values
    idx = px.index
    while i < n - hold - 1:
        zz = arr_z[i]
        if np.isnan(zz):
            i += 1; continue
        if vol_gate and not arr_gate[i]:        # high-vol regime only (momentum)
            i += 1; continue
        if calm_gate and arr_gate[i]:           # low-vol/ranging regime only (mean-reversion)
            i += 1; continue
        side = 0
        if revert:                      # fade: buy oversold dips (maker limit fills), short rips
            if -3.0 < zz <= -thr:        # moderate dip only — extreme (z<-3) CONTINUES down (diag)
                side = 1
            elif allow_short and 3.0 > zz >= thr:
                side = -1
        else:                           # momentum: ride strong moves
            if zz >= thr:
                side = 1
            elif allow_short and zz <= -thr:
                side = -1
        if side == 0:
            i += 1; continue
        entry = arr_p[i + 1]            # next bar open ~ this close; causal
        exit_ = arr_p[i + 1 + hold]
        gross = side * (exit_ / entry - 1)
        net = gross - cost_bp / 1e4     # round-trip taker
        trades.append((idx[i + 1], net))
        i += hold + 1                   # no overlap per coin
    return trades


def _summary(label, all_tr, cost_bp):
    if not all_tr:
        print(f"  {label}: no trades"); return
    nets = np.array([t[1] for t in all_tr])
    n = len(nets); mean_bp = nets.mean() * 1e4
    win = (nets > 0).mean() * 100
    # rough annualized: trades/yr * mean, naive single-position sizing across the basket
    yrs = (max(t[0] for t in all_tr) - min(t[0] for t in all_tr)).days / 365
    tr_yr = n / yrs if yrs else 0
    sharpe = nets.mean() / nets.std() * np.sqrt(tr_yr) if nets.std() and tr_yr else 0
    print(f"  {label:14s} n={n:5d}  net {mean_bp:+6.1f}bp/tr  win {win:4.1f}%  "
          f"~{tr_yr:.0f} tr/yr  Sharpe~{sharpe:+.2f}  sum {nets.sum()*100:+.1f}%")


def main():
    thr = _opt_f("--thr", 3.0); hold_h = _opt_f("--hold", 3.0)
    cost_bp = _opt_f("--cost-bp", 10.0); allow_short = "--short" in sys.argv
    vol_gate = "--vol-gate" in sys.argv
    calm_gate = "--calm-gate" in sys.argv
    revert = "--revert" in sys.argv
    a = sys.argv[1:]; tf = a[a.index("--tf") + 1] if "--tf" in a else "1h"
    bpd = _BPD[tf]
    hold = max(1, round(hold_h * bpd / 24))   # hold hours -> bars at this TF
    mode = "MEAN-REVERSION (maker dip-buy)" if revert else "MOMENTUM"
    print(f"=== INTRADAY {mode}  tf={tf}  |z|>={thr} hold={hold_h}h({hold}bars)  RT {cost_bp}bp  "
          f"{'long+short' if allow_short else 'long-only'}"
          f"{'  [VOL-GATE]' if vol_gate else ''} ===")
    by_period = {"DESIGN 2023-24": [], "OOS 2025-26": []}
    per_coin = {}
    for sym in BASKET:
        try:
            px = fetch_klines(sym, tf)
        except Exception as exc:  # noqa: BLE001
            print(f"  {sym}: {exc}"); continue
        tr = backtest(px, thr, hold, cost_bp, allow_short, vol_gate, bpd, revert, calm_gate)
        per_coin[sym] = np.mean([t[1] for t in tr]) * 1e4 if tr else 0
        for ts, net in tr:
            (by_period["DESIGN 2023-24"] if ts.year <= 2024 else by_period["OOS 2025-26"]).append((ts, net))
    for label, tr in by_period.items():
        _summary(label, tr, cost_bp)
    pos = sum(1 for v in per_coin.values() if v > 0)
    detail = ", ".join(f"{s.replace('USDT', '')}:{v:+.0f}" for s, v in per_coin.items())
    print(f"  breadth: {pos}/{len(per_coin)} coins net-positive  ({detail})")


if __name__ == "__main__":
    main()
