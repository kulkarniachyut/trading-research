"""Multi-timeframe FVG (Fair Value Gap) — HTF imbalance, LTF retrace entry. User idea 2026-06-13.

ICT-style multi-TF: detect a 3-bar Fair Value Gap on a HIGHER timeframe (1h/4h), then on a LOWER
timeframe (15m) enter when price RETRACES into the gap zone — a maker limit at the gap edge (price
comes to you, ~2bp fill, not chasing). This is genuinely different from the single-TF z-score tests:
the signal is a HTF structural level, the entry is a passive LTF limit.

FVG definition (causal, completed HTF bars i-2,i-1,i):
  bullish: high[i-2] < low[i]  -> up-imbalance, zone [high[i-2], low[i]]  (expect support/continuation up)
  bearish: low[i-2]  > high[i] -> down-imbalance, zone [high[i], low[i-2]] (resistance/continuation down)
Trade: when a later LTF bar trades into an active zone, enter in the FVG direction at the near edge
(maker limit), stop at the far edge, R = zone width, target = entry + RR*R. Outcome in R-multiples
net of maker cost. Active window = next `htf_life` HTF bars; one trade per FVG.

Data: Binance 15m OHLC (fetched+cached), resampled up to HTF. OOS split DESIGN 2023-24 / OOS 2025-26.
Usage: run_mtf_fvg.py [--htf 4h] [--rr 1.5] [--life 12] [--cost-bp 4] [--short]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.diag_crypto_intraday import BASKET

CACHE = Path("data/intraday")
START = pd.Timestamp("2023-01-01", tz="UTC")
END = pd.Timestamp("2026-06-13", tz="UTC")


def _opt(flag, d, cast=float):
    a = sys.argv[1:]
    return cast(a[a.index(flag) + 1]) if flag in a else d


def fetch_ohlc_15m(symbol: str) -> pd.DataFrame:
    fp = CACHE / f"{symbol}_15m_ohlc.parquet"
    if fp.exists():
        df = pd.read_parquet(fp); df.index = pd.to_datetime(df.index, utc=True); return df
    rows = []
    cur = int(START.timestamp() * 1000); end_ms = int(END.timestamp() * 1000)
    while cur < end_ms:
        req = urllib.request.Request(
            f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m"
            f"&startTime={cur}&endTime={end_ms}&limit=1000", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            b = json.loads(r.read())
        if not b:
            break
        rows += [(x[0], float(x[1]), float(x[2]), float(x[3]), float(x[4])) for x in b]
        if b[-1][0] <= cur:
            break
        cur = b[-1][0] + 900_000
        time.sleep(0.12)
    idx = pd.to_datetime([r[0] for r in rows], unit="ms", utc=True)
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close"]).drop(columns="t")
    df.index = idx
    df = df[~df.index.duplicated()]
    df.to_parquet(fp)
    return df


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return df.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def find_fvgs(htf: pd.DataFrame, allow_short: bool):
    """Yield (formed_ts, direction, near_edge, far_edge). Causal: uses bars up to i."""
    H, L = htf["high"].values, htf["low"].values
    ts = htf.index
    out = []
    for i in range(2, len(htf)):
        if H[i - 2] < L[i]:                       # bullish FVG
            out.append((ts[i], 1, L[i], H[i - 2]))   # near=low[i] (top of gap), far=high[i-2] (bottom)
        elif allow_short and L[i - 2] > H[i]:     # bearish FVG
            out.append((ts[i], -1, H[i], L[i - 2]))  # near=high[i], far=low[i-2]
    return out


def backtest(ltf: pd.DataFrame, htf: pd.DataFrame, rr: float, life_htf_bars: int,
             cost_bp: float, allow_short: bool, htf_rule: str,
             bias_gate: bool = False, killzone: bool = False):
    fvgs = find_fvgs(htf, allow_short)
    htf_step = pd.Timedelta(htf_rule)
    lo_arr, hi_arr = ltf["low"].values, ltf["high"].values
    idx = ltf.index
    # ICT layer 1 -- HTF bias: causal EMA50 on HTF close, mapped onto LTF bars (shifted to avoid peek)
    ema = htf["close"].ewm(span=50, adjust=False).mean()
    bias_htf = pd.Series(np.where(htf["close"] > ema, 1, -1), index=htf.index).shift(1)
    bias_on_ltf = bias_htf.reindex(idx, method="ffill").values
    # ICT layer 2 -- killzone hours (UTC): London 07-10, NY 12-16
    kz_hours = {7, 8, 9, 12, 13, 14, 15}
    hours = idx.hour.values
    trades = []
    for formed, direction, near, far in fvgs:
        # CAUSAL: a FVG using bars up to the one left-labeled `formed` is only KNOWN when that bar
        # closes = formed + htf_step. Entries may only happen AFTER that (no look-ahead).
        win_start = formed + htf_step
        win_end = win_start + life_htf_bars * htf_step
        mask = (idx > win_start) & (idx <= win_end)
        if not mask.any():
            continue
        seg = np.where(mask)[0]
        # entry: first LTF bar that trades into the zone (price reaches `near` edge)
        entered = False
        entry = near
        zone_lo, zone_hi = min(near, far), max(near, far)
        risk = abs(near - far)
        if risk <= 0:
            continue
        target = entry + direction * rr * risk
        stop = far
        for j in seg:
            if not entered:
                # price retraces into zone: for bullish, low dips to <= near (top); for bearish, high >= near
                if (direction == 1 and lo_arr[j] <= near) or (direction == -1 and hi_arr[j] >= near):
                    # ICT aggregate gates (applied at the entry bar, causal):
                    if bias_gate and bias_on_ltf[j] != direction:
                        break  # HTF bias must align with the FVG direction
                    if killzone and hours[j] not in kz_hours:
                        continue  # wait for a killzone bar to take this setup
                    entered = True
                    continue  # enter at near (maker limit) at this bar; resolve from next bars
            else:
                hit_stop = (direction == 1 and lo_arr[j] <= stop) or (direction == -1 and hi_arr[j] >= stop)
                hit_tgt = (direction == 1 and hi_arr[j] >= target) or (direction == -1 and lo_arr[j] <= target)
                if hit_stop and hit_tgt:
                    r_mult = -1.0  # ambiguous bar -> assume stop first (conservative)
                elif hit_stop:
                    r_mult = -1.0
                elif hit_tgt:
                    r_mult = rr
                else:
                    continue
                trades.append((idx[j], r_mult))  # gross R; maker cost applied in main (cost_R)
                break
    return trades, fvgs


def main() -> None:
    htf_rule = _opt("--htf", "4h", str); rr = _opt("--rr", 1.5); life = _opt("--life", 12, int)
    cost_bp = _opt("--cost-bp", 4.0); allow_short = "--short" in sys.argv
    bias_gate = "--bias-gate" in sys.argv; killzone = "--killzone" in sys.argv
    layers = "".join([" +BIAS" if bias_gate else "", " +KILLZONE" if killzone else ""])
    print(f"=== MTF FVG  HTF={htf_rule} entry=15m  RR={rr} life={life}HTFbars  RT={cost_bp}bp  "
          f"{'long+short' if allow_short else 'long-only'}{layers} ===")
    design, oos = [], []
    per_coin = {}
    for sym in BASKET:
        try:
            ltf = fetch_ohlc_15m(sym)
        except Exception as exc:  # noqa: BLE001
            print(f"  {sym}: {exc}"); continue
        htf = resample(ltf, htf_rule)
        trades, fvgs = backtest(ltf, htf, rr, life, cost_bp, allow_short, htf_rule,
                                bias_gate, killzone)
        # apply a flat cost in R: assume R averages ~0.6% of price for these gaps; cost_bp/ (R%*1e4)
        # use measured: cost in R = cost_bp/1e4 divided by typical risk fraction ~0.006 -> ~cost_bp/60 R
        cost_R = (cost_bp / 1e4) / 0.006
        rs = [t[1] - cost_R for t in trades]
        per_coin[sym] = np.mean(rs) if rs else 0
        for (ts, _), r in zip(trades, rs):
            (design if ts.year <= 2024 else oos).append(r)
    for label, rs in [("DESIGN 2023-24", design), ("OOS 2025-26", oos)]:
        if not rs:
            print(f"  {label}: no trades"); continue
        rs = np.array(rs)
        print(f"  {label:14s} n={len(rs):5d}  exp {rs.mean():+.3f}R  win {(rs>0).mean()*100:4.1f}%  "
              f"sumR {rs.sum():+.0f}")
    pos = sum(1 for v in per_coin.values() if v > 0)
    print(f"  breadth: {pos}/{len(per_coin)} coins net-positive R")


if __name__ == "__main__":
    main()
