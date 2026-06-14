"""Diagnostic: crypto perpetual funding-rate carry profile (pure measurement, no strategy yet).

The highest-prior crypto-native edge (research scan 2026-06-13): cash-and-carry / delta-neutral
funding harvest. Long spot + short perp ⇒ price cancels, you collect the funding rate that longs
pay shorts. Structurally positive in crypto (retail is chronically long-levered), but
REGIME-DEPENDENT — fat in bull/euphoria, thin or negative in bear. This diagnostic measures the
raw carry profile across the full 2021-2024 cycle so a strategy can be designed on base rates,
not the current snapshot.

Data: Binance USDⓈ-M funding history (free public API, 8h cadence, no key). Cached to Parquet so
re-runs are free and offline. Binance is the data proxy; a US user would execute on a reachable
perp venue (e.g. Hyperliquid) whose funding tracks closely.

NO trading simulated here — this reports per-coin and basket carry, % time positive, the
asymmetry between positive/negative funding, and the year-by-year regime profile. The strategy
brick (collect-when-positive, fee-aware) is designed AFTER, against these numbers.

Usage: diag_funding_carry.py [--refresh]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path("data/funding")
# liquid perps spanning majors + high-funding alts; USDT-margined Binance symbols.
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
           "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]
START = pd.Timestamp("2021-01-01", tz="UTC")
END = pd.Timestamp("2024-12-31", tz="UTC")  # 2025/26 NOT pulled (sealed-holdout discipline)


def _get(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fetch_funding(symbol: str, refresh: bool = False) -> pd.Series:
    """Full 8h funding-rate series for a symbol, paginated forward, Parquet-cached."""
    CACHE.mkdir(parents=True, exist_ok=True)
    fp = CACHE / f"{symbol}.parquet"
    if fp.exists() and not refresh:
        s = pd.read_parquet(fp)["fundingRate"]
        s.index = pd.to_datetime(s.index, utc=True)
        return s
    rows: list[tuple[int, float]] = []
    cur = int(START.timestamp() * 1000)
    end_ms = int(END.timestamp() * 1000)
    while cur < end_ms:
        url = (f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}"
               f"&startTime={cur}&limit=1000")
        batch = _get(url)
        if not batch:
            break
        for x in batch:
            rows.append((x["fundingTime"], float(x["fundingRate"])))
        last = batch[-1]["fundingTime"]
        if last <= cur:
            break
        cur = last + 1
        time.sleep(0.15)  # be polite to the public endpoint
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows], unit="ms", utc=True)
    s = pd.Series([r[1] for r in rows], index=idx, name="fundingRate").sort_index()
    s = s[~s.index.duplicated()]
    s = s[(s.index >= START) & (s.index <= END)]
    s.to_frame().to_parquet(fp)
    return s


def profile(symbol: str, s: pd.Series) -> dict:
    if s.empty:
        print(f"  {symbol}: no data")
        return {}
    n = len(s)
    pos = (s > 0).mean()
    # annualized carry IF you collected funding every interval (3 intervals/day)
    ann_always = s.mean() * 3 * 365
    # annualized carry IF you only collect when funding > 0 (flatten otherwise)
    ann_pos_only = s.clip(lower=0).mean() * 3 * 365
    # the asymmetry that makes "collect-when-positive" work:
    mean_pos = s[s > 0].mean() if (s > 0).any() else 0.0
    mean_neg = s[s < 0].mean() if (s < 0).any() else 0.0
    print(f"  {symbol:9s} n={n:5d}  pos {pos*100:4.0f}%  "
          f"ann(always) {ann_always*100:+6.1f}%  ann(pos-only) {ann_pos_only*100:+6.1f}%  "
          f"mean+ {mean_pos*100:+.4f}%  mean- {mean_neg*100:+.4f}%")
    return {"s": s, "ann_always": ann_always, "ann_pos_only": ann_pos_only, "pos": pos}


def main() -> None:
    refresh = "--refresh" in sys.argv
    print(f"=== FUNDING CARRY DIAGNOSTIC  {START.date()}..{END.date()}  "
          f"(Binance USDⓈ-M, 8h) ===")
    series: dict[str, pd.Series] = {}
    for sym in SYMBOLS:
        try:
            s = fetch_funding(sym, refresh)
            p = profile(sym, s)
            if p:
                series[sym] = p["s"]
        except Exception as exc:  # noqa: BLE001
            print(f"  {sym}: fetch failed ({exc})")

    if not series:
        print("no data")
        return

    # year-by-year regime profile (pos-only collection, equal-weight basket)
    print("\n  year regime (equal-weight basket, collect-when-positive annualized):")
    df = pd.DataFrame({k: v for k, v in series.items()})
    for yr in [2021, 2022, 2023, 2024]:
        sub = df[df.index.year == yr]
        if sub.empty:
            continue
        # per-coin pos-only mean, then average across coins, then annualize
        ann = sub.clip(lower=0).mean().mean() * 3 * 365
        always = sub.mean().mean() * 3 * 365
        print(f"    {yr}: ann(pos-only) {ann*100:+6.1f}%   ann(always-on) {always*100:+6.1f}%")

    # basket carry "equity curve" under naive pos-only collection (gross of fees), for Sharpe/DD.
    # daily basket carry = mean across coins of (clip>=0 funding) summed per day.
    daily = df.clip(lower=0).resample("1D").sum().mean(axis=1)
    daily = daily[daily.index.year.isin([2021, 2022, 2023, 2024])]
    sharpe = daily.mean() / daily.std() * np.sqrt(365) if daily.std() else float("nan")
    curve = daily.cumsum()
    dd = (curve - curve.cummax()).min()
    print(f"\n  GROSS basket (pos-only, no fees): ann {daily.mean()*365*100:+.1f}%  "
          f"Sharpe {sharpe:+.2f}  maxDD {dd*100:.1f}% (additive)")
    print("  NOTE: gross of fees/basis. Fees on continuous delta-neutral carry are small "
          "(amortized over long holds), but flatten/re-enter churn when funding flips sign is "
          "the real cost — the strategy brick prices that. This is base-rate measurement only.")


if __name__ == "__main__":
    main()
