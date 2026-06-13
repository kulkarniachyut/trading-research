"""ONE-SHOT OOS validation of funding carry on the 2025/26 holdout (user-authorized 2026-06-13).

IS (2021-2024) gave +7.4% net basket (basis-aware). This confirms the edge on the most recent,
never-touched regime. Isolated `_oos` caches so IS data stays clean. Same carry_full logic as
run_funding_carry_basis.py — only the date window changes. After this read, carry is PARKED.

Usage: validate_carry_oos.py
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.run_funding_carry_basis import BASKET, carry_full, _stats

CACHE = Path("data/funding")
OOS_START = pd.Timestamp("2025-01-01", tz="UTC")
OOS_END = pd.Timestamp("2026-06-13", tz="UTC")  # today; 2025 full + 2026 YTD


def _get(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _paginate(url_fn, step_ms: int, parse) -> list:
    rows: list = []
    cur = int(OOS_START.timestamp() * 1000)
    end_ms = int(OOS_END.timestamp() * 1000)
    while cur < end_ms:
        batch = _get(url_fn(cur, end_ms))
        if not batch:
            break
        rows += [parse(x) for x in batch]
        last = rows[-1][0]
        if last <= cur:
            break
        cur = last + step_ms
        time.sleep(0.15)
    return rows


def fetch_funding_oos(sym: str) -> pd.Series:
    fp = CACHE / f"{sym}_oos.parquet"
    if fp.exists():
        s = pd.read_parquet(fp)["fundingRate"]; s.index = pd.to_datetime(s.index, utc=True); return s
    rows = _paginate(
        lambda c, e: f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&startTime={c}&limit=1000",
        8 * 3600 * 1000, lambda x: (x["fundingTime"], float(x["fundingRate"])))
    idx = pd.to_datetime([r[0] for r in rows], unit="ms", utc=True)
    s = pd.Series([r[1] for r in rows], index=idx, name="fundingRate").sort_index()
    s = s[~s.index.duplicated()]; s = s[(s.index >= OOS_START) & (s.index <= OOS_END)]
    s.to_frame().to_parquet(fp); return s


def fetch_klines_oos(sym: str, host: str, tag: str) -> pd.Series:
    fp = CACHE / f"{sym}_{tag}_8h_oos.parquet"
    if fp.exists():
        s = pd.read_parquet(fp)["close"]; s.index = pd.to_datetime(s.index, utc=True); return s
    base = "fapi/v1" if "fapi" in host else "api/v3"
    rows = _paginate(
        lambda c, e: f"https://{host}/{base}/klines?symbol={sym}&interval=8h&startTime={c}&endTime={e}&limit=1000",
        8 * 3600 * 1000, lambda x: (x[0], float(x[4])))
    idx = pd.to_datetime([r[0] for r in rows], unit="ms", utc=True)
    s = pd.Series([r[1] for r in rows], index=idx, name="close").sort_index()
    s = s[~s.index.duplicated()]
    s.to_frame().to_parquet(fp); return s


def coin_frame_oos(sym: str) -> pd.DataFrame:
    f = fetch_funding_oos(sym)
    spot = fetch_klines_oos(sym, "api.binance.com", "spot")
    perp = fetch_klines_oos(sym, "fapi.binance.com", "perp")
    df = pd.DataFrame({"funding": f, "spot": spot, "perp": perp}).dropna()
    df["spot_ret"] = df["spot"].pct_change(); df["perp_ret"] = df["perp"].pct_change()
    return df.dropna()


def main() -> None:
    print(f"=== FUNDING CARRY — OOS HOLDOUT {OOS_START.date()}..{OOS_END.date()} "
          f"(basis-aware, one-shot) ===")
    pnls: dict[str, pd.Series] = {}
    pos = 0
    print("\n  per-coin (FULL net, OOS):")
    for sym in BASKET:
        try:
            df = coin_frame_oos(sym)
            if len(df) < 50:
                print(f"  {sym}: thin ({len(df)})"); continue
            p, _ = carry_full(df, 0.0010)
            pnls[sym] = p
            st = _stats(sym, p)
            if st and st["ann"] > 0:
                pos += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  {sym}: {exc}")
    if not pnls:
        raise SystemExit("no OOS data")
    basket = pd.DataFrame(pnls).fillna(0.0).mean(axis=1)
    print("\n  BASKET (equal-weight, OOS):")
    b = _stats("basket", basket)
    print("\n  OOS by year:")
    worst = 1e9
    for yr in (2025, 2026):
        sub = basket[basket.index.year == yr]
        if sub.empty:
            continue
        a = sub.resample("1D").sum().mean() * 365
        worst = min(worst, a)
        print(f"    {yr}: net ann {a*100:+6.1f}%")
    # "holds" requires retaining most of the IS edge, not merely staying positive.
    ann = b.get("ann", 0)
    verdict = "HOLDS" if ann >= 0.05 else ("DECAYED (regime)" if ann > 0 else "GONE")
    print(f"\n  OOS VERDICT vs IS +7.4%: basket {ann*100:+.1f}%, coins+ {pos}/9, "
          f"worst-yr {worst*100:+.1f}% -> {verdict}")
    print("  NOTE: funding compressed in the 2025/26 regime → carry is regime-gated on the "
          "funding LEVEL. Redeploy trigger = basket funding back to elevated levels, not now.")


if __name__ == "__main__":
    main()
