"""Intraday crypto alpha diagnostic (1h bars, MAKER-cost realism) — pure measurement.

User redirect 2026-06-13: find a real intraday edge (5m/15m/1h), not marginal carry. KEY reframe:
on Binance with MAKER/limit orders the round-trip fee is ~1-2bp, not the 10-20bp taker I wrongly
used to dismiss intraday before. That reopens the question. This measures base rates (no trade sim):
  1. CONDITIONAL MEAN-REVERSION: bucket bars by return z-score (vs trailing 24h vol); measure
     forward 1h/3h/6h returns. Edge if extreme-negative z -> positive forward return >> ~2bp maker.
  2. HOUR-OF-DAY (UTC) effect: session/funding-settlement structure (00/08/16 UTC funding).
  3. BREAKOUT momentum: forward return after breaking the trailing 24h high.
Data: Binance 1h klines (free, deep), cached to data/intraday/. Universe = the 9-coin basket.

Usage: diag_crypto_intraday.py [--refresh]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path("data/intraday")
BASKET = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
          "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]
START = pd.Timestamp("2023-01-01", tz="UTC")
END = pd.Timestamp("2026-06-13", tz="UTC")
MAKER_RT_BP = 2.0  # round-trip maker cost assumption on Binance


def _get(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fetch_1h(symbol: str, refresh: bool = False) -> pd.Series:
    CACHE.mkdir(parents=True, exist_ok=True)
    fp = CACHE / f"{symbol}_1h.parquet"
    if fp.exists() and not refresh:
        s = pd.read_parquet(fp)["close"]; s.index = pd.to_datetime(s.index, utc=True); return s
    rows = []
    cur = int(START.timestamp() * 1000); end_ms = int(END.timestamp() * 1000)
    while cur < end_ms:
        b = _get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h"
                 f"&startTime={cur}&endTime={end_ms}&limit=1000")
        if not b:
            break
        rows += [(x[0], float(x[4])) for x in b]
        if b[-1][0] <= cur:
            break
        cur = b[-1][0] + 3600_000
        time.sleep(0.12)
    idx = pd.to_datetime([r[0] for r in rows], unit="ms", utc=True)
    s = pd.Series([r[1] for r in rows], index=idx, name="close").sort_index()
    s = s[~s.index.duplicated()]
    s.to_frame().to_parquet(fp)
    return s


def main() -> None:
    refresh = "--refresh" in sys.argv
    print(f"=== INTRADAY CRYPTO DIAGNOSTIC (1h, {START.date()}..{END.date()}, "
          f"maker RT ~{MAKER_RT_BP}bp) ===")
    series = {}
    for s in BASKET:
        try:
            series[s] = fetch_1h(s, refresh)
        except Exception as exc:  # noqa: BLE001
            print(f"  {s}: fetch failed ({exc})")
    if not series:
        raise SystemExit("no data")

    # build per-coin frames: 1h log return, trailing-24h vol, z-score
    fwd_by_z = {b: [] for b in ["z<-3", "-3..-2", "-2..-1", "-1..1", "1..2", "2..3", "z>3"]}
    fwd3_by_z = {k: [] for k in fwd_by_z}
    hod = {h: [] for h in range(24)}
    bo_fwd = []  # breakout forward 3h
    for sym, px in series.items():
        r = np.log(px).diff()
        vol = r.rolling(24).std()
        z = r / vol
        f1 = np.log(px).shift(-1) - np.log(px)      # next 1h
        f3 = np.log(px).shift(-3) - np.log(px)      # next 3h
        df = pd.DataFrame({"r": r, "z": z, "f1": f1, "f3": f3}).dropna()
        def bucket(zz):
            if zz < -3: return "z<-3"
            if zz < -2: return "-3..-2"
            if zz < -1: return "-2..-1"
            if zz < 1: return "-1..1"
            if zz < 2: return "1..2"
            if zz < 3: return "2..3"
            return "z>3"
        for _, row in df.iterrows():
            b = bucket(row["z"]); fwd_by_z[b].append(row["f1"]); fwd3_by_z[b].append(row["f3"])
        # hour-of-day
        for h in range(24):
            hod[h] += list(df[df.index.hour == h]["f1"])
        # breakout: close > trailing 24h max(close) -> forward 3h
        hi = px.rolling(24).max().shift(1)
        bo = (px > hi)
        bo_fwd += list((np.log(px).shift(-3) - np.log(px))[bo].dropna())

    print("\n  1) CONDITIONAL MEAN-REVERSION (forward return by entry z-score, bp):")
    print(f"     {'bucket':8s} {'n':>7s} {'fwd1h':>9s} {'fwd3h':>9s}   (reversion if low-z -> positive fwd)")
    for b in ["z<-3", "-3..-2", "-2..-1", "-1..1", "1..2", "2..3", "z>3"]:
        n = len(fwd_by_z[b])
        if n:
            m1 = np.mean(fwd_by_z[b]) * 1e4; m3 = np.mean(fwd3_by_z[b]) * 1e4
            print(f"     {b:8s} {n:7d} {m1:+8.1f} {m3:+8.1f}")
    print(f"     [maker round-trip ~{MAKER_RT_BP}bp — a bucket's fwd must exceed this to trade]")

    print("\n  2) HOUR-OF-DAY (UTC) mean next-1h return (bp), funding settles 00/08/16:")
    hod_means = {h: (np.mean(hod[h]) * 1e4 if hod[h] else 0) for h in range(24)}
    best = sorted(hod_means.items(), key=lambda kv: kv[1], reverse=True)[:4]
    worst = sorted(hod_means.items(), key=lambda kv: kv[1])[:4]
    print(f"     best hours:  " + "  ".join(f"{h:02d}h {v:+.1f}" for h, v in best))
    print(f"     worst hours: " + "  ".join(f"{h:02d}h {v:+.1f}" for h, v in worst))

    print("\n  3) BREAKOUT (close > trailing-24h high) forward 3h return:")
    if bo_fwd:
        print(f"     n={len(bo_fwd)}  fwd3h {np.mean(bo_fwd)*1e4:+.1f}bp  "
              f"({'momentum' if np.mean(bo_fwd) > 0 else 'fade'})")


if __name__ == "__main__":
    main()
