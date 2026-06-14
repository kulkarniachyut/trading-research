"""Funding carry — FULL delta-neutral P&L incl. spot-perp basis (the rigor pass).

run_funding_carry.py modeled carry-only (funding − fees). This prices the REAL position:
long spot + short perp, marked every 8h with actual Binance prices, so the spot-perp basis P&L
(the main caveat) becomes a hard number rather than an assumption. For a user trading this for
real on Binance with a 2-3x cap and a prior of losing money on perps, this is the make-or-break.

Per 8h interval while in position (notional = 1 unit per leg):
  pnl_t = funding[t]                       (short perp collects funding when funding>0)
        + (spot_ret[t] - perp_ret[t])      (long-spot gain minus short-perp loss = -Δbasis)
Entry/exit: half the round-trip fee on each transition (flatten when causal rolling-7d funding<0).

Also reports the LIQUIDATION-SAFETY view at leverage L: the worst adverse 8h perp move while
short, vs the maintenance buffer — so we can state the max safe L (user cap 2-3x).

Data: Binance funding + 8h spot (api) + 8h perp (fapi) klines, all cached to data/funding/.
2025/26 NOT pulled (holdout discipline). Usage: run_funding_carry_basis.py [--fee-rt 0.0010]
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
BASKET = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
          "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]
START = pd.Timestamp("2021-01-01", tz="UTC")
END = pd.Timestamp("2024-12-31", tz="UTC")
YEARS = [2021, 2022, 2023, 2024]


def _get(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fetch_klines(symbol: str, host: str, tag: str) -> pd.Series:
    """8h close series, paginated, Parquet-cached. host: api.binance.com (spot) / fapi.binance.com (perp)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    fp = CACHE / f"{symbol}_{tag}_8h.parquet"
    if fp.exists():
        s = pd.read_parquet(fp)["close"]
        s.index = pd.to_datetime(s.index, utc=True)
        return s
    base = "fapi/v1" if "fapi" in host else "api/v3"
    rows: list[tuple[int, float]] = []
    cur = int(START.timestamp() * 1000)
    end_ms = int(END.timestamp() * 1000)
    while cur < end_ms:
        url = (f"https://{host}/{base}/klines?symbol={symbol}&interval=8h"
               f"&startTime={cur}&endTime={end_ms}&limit=1000")
        batch = _get(url)
        if not batch:
            break
        for x in batch:
            rows.append((x[0], float(x[4])))
        last = batch[-1][0]
        if last <= cur:
            break
        cur = last + 8 * 3600 * 1000
        time.sleep(0.15)
    if not rows:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([r[0] for r in rows], unit="ms", utc=True)
    s = pd.Series([r[1] for r in rows], index=idx, name="close").sort_index()
    s = s[~s.index.duplicated()]
    s.to_frame().to_parquet(fp)
    return s


def coin_frame(symbol: str) -> pd.DataFrame:
    from scripts.diag_funding_carry import fetch_funding
    f = fetch_funding(symbol)
    spot = fetch_klines(symbol, "api.binance.com", "spot")
    perp = fetch_klines(symbol, "fapi.binance.com", "perp")
    df = pd.DataFrame({"funding": f, "spot": spot, "perp": perp}).dropna()
    df["spot_ret"] = df["spot"].pct_change()
    df["perp_ret"] = df["perp"].pct_change()
    return df.dropna()


def carry_full(df: pd.DataFrame, fee_rt: float, win: int = 21) -> tuple[pd.Series, pd.Series]:
    """Return (net per-interval pnl, perp_adverse_move_while_short). Causal regime gate."""
    roll = df["funding"].rolling(win, min_periods=win).mean().shift(1)
    pnl = pd.Series(0.0, index=df.index)
    adverse = pd.Series(0.0, index=df.index)  # short-perp loss leg (for liquidation sizing)
    in_pos = False
    half = fee_rt / 2.0
    for i in range(len(df)):
        r = roll.iloc[i]
        if pd.isna(r):
            continue
        want = bool(r >= 0)
        if want and not in_pos:
            pnl.iloc[i] -= half
            in_pos = True
        elif not want and in_pos:
            pnl.iloc[i] -= half
            in_pos = False
        if in_pos:
            pnl.iloc[i] += float(df["funding"].iloc[i]) + float(df["spot_ret"].iloc[i] - df["perp_ret"].iloc[i])
            adverse.iloc[i] = float(df["perp_ret"].iloc[i])  # +ve perp move = loss on the short leg
    return pnl, adverse


def _stats(label: str, pnl: pd.Series) -> dict:
    daily = pnl.resample("1D").sum()
    if daily.std() == 0 or daily.empty:
        print(f"  {label}: flat")
        return {}
    ann = daily.mean() * 365
    sharpe = daily.mean() / daily.std() * np.sqrt(365)
    curve = daily.cumsum()
    dd = (curve - curve.cummax()).min()
    print(f"  {label:10s} net ann {ann*100:+6.1f}%  Sharpe {sharpe:+6.2f}  "
          f"maxDD {dd*100:6.2f}%  total {curve.iloc[-1]*100:+6.1f}%")
    return {"ann": ann, "sharpe": sharpe, "dd": dd, "daily": daily}


def main() -> None:
    a = sys.argv[1:]
    fee_rt = float(a[a.index("--fee-rt") + 1]) if "--fee-rt" in a else 0.0010
    print(f"=== FUNDING CARRY (FULL, incl basis)  fee_rt={fee_rt*100:.2f}%  "
          f"[long spot + short perp, real 8h prices] ===")
    pnls: dict[str, pd.Series] = {}
    adverse_all: list[float] = []
    print("\n  per-coin (FULL net = funding + basis − fees):")
    pos = 0
    for sym in BASKET:
        try:
            df = coin_frame(sym)
            if len(df) < 100:
                print(f"  {sym}: thin ({len(df)})")
                continue
            p, adv = carry_full(df, fee_rt)
            pnls[sym] = p
            adverse_all += [v for v in adv if v != 0]
            st = _stats(sym, p)
            if st and st["ann"] > 0:
                pos += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  {sym}: {exc}")
    if not pnls:
        raise SystemExit("no data")

    df_all = pd.DataFrame(pnls).fillna(0.0)
    basket = df_all.mean(axis=1)
    print("\n  BASKET (equal-weight, FULL net):")
    b = _stats("basket", basket)
    print("\n  basket net by year:")
    worst = 1e9
    for yr in YEARS:
        sub = basket[basket.index.year == yr]
        if sub.empty:
            continue
        ann = sub.resample("1D").sum().mean() * 365
        worst = min(worst, ann)
        print(f"    {yr}: net ann {ann*100:+6.1f}%")

    # liquidation safety: worst adverse 8h perp move while short (the short leg's loss before the
    # long-spot leg offsets it — both legs move together, so net is tiny; this bounds the GROSS
    # margin swing the short leg sees intra-interval).
    adv = np.array(adverse_all)
    if len(adv):
        p999 = np.percentile(adv, 99.9) * 100
        worst_move = adv.max() * 100
        print(f"\n  LIQUIDATION VIEW: short-perp adverse 8h move  p99.9 {p999:+.1f}%  "
              f"worst {worst_move:+.1f}%")
        # at leverage L, an isolated short-perp leg liquidates ~when adverse move ~ 1/L (minus MM).
        # delta-neutral: long spot offsets, so account-level risk is ~basis move, not price move.
        for L in (2, 3):
            print(f"    L={L}x: isolated short-leg liquidation buffer ~{100/L:.0f}% move; "
                  f"worst single-bar adverse was {worst_move:+.1f}% → "
                  f"{'SAFE if margined cross/delta-neutral' if worst_move < 100/L else 'RISK if isolated'}")

    print(f"\n  GATE: coins net+ {pos}/9; worst-year {worst*100:+.1f}%; basket {b.get('ann',0)*100:+.1f}%")
    print("  vs carry-only (+14.9%): basis P&L impact is the difference above.")


if __name__ == "__main__":
    main()
