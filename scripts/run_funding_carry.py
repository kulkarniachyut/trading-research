"""Funding-rate carry strategy — net of real frictions (crypto brick #2).

Delta-neutral cash-and-carry: long spot + short perp ⇒ price-neutral; harvest the 8h funding that
longs pay shorts. Theory-fixed rule (pre-registered in docs/CRYPTO_100K_CAMPAIGN.md):
  - Hold the carry continuously; flatten when the rolling-7d (21-interval) mean funding turns < 0
    (avoids paying funding in a bear), re-enter when it turns > 0 again.
  - Round-trip fee charged on each enter→exit CYCLE (open 2 legs + close 2 legs).
  - Carry-only P&L: funding accrued each interval while in position. (Basis P&L over a full hold
    ≈ 0 on average since spot↔perp converge at settlement; its variance is a noted caveat, not
    modeled — this keeps the estimate to the deterministic carry term.)

Reports per-coin and equal-weight basket NET annualized return, Sharpe (delta-neutral ⇒ vol is
funding variability only, so Sharpe is high by construction — the honest metric is the NET APY and
the worst-year survival), max drawdown, and time-in-position (capital utilization).

Data: cached Binance funding (data/funding/*.parquet) from diag_funding_carry.py.

Usage: run_funding_carry.py [--fee-rt 0.0010] [--win 21]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from scripts.diag_funding_carry import fetch_funding

BASKET = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
          "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]  # BNB excluded (anomalous funding)
YEARS = [2021, 2022, 2023, 2024]


def _opt_f(flag: str, default: float) -> float:
    a = sys.argv[1:]
    return float(a[a.index(flag) + 1]) if flag in a else default


def _opt_i(flag: str, default: int) -> int:
    a = sys.argv[1:]
    return int(a[a.index(flag) + 1]) if flag in a else default


def carry_pnl(funding: pd.Series, fee_rt: float, win: int) -> pd.Series:
    """Per-interval NET carry P&L (fraction of notional). Long-spot/short-perp earns +funding.

    Regime: in-position while rolling-`win` mean funding ≥ 0; flatten (one fee leg) when it goes
    negative, re-enter (one fee leg) when it returns ≥ 0. Fee `fee_rt` is the full round trip,
    split half on entry / half on exit so a flatten+reenter costs exactly one round trip.
    """
    # causal: decision at interval i uses the rolling mean through i-1 (no peek at funding[i]).
    roll = funding.rolling(win, min_periods=win).mean().shift(1)
    pnl = pd.Series(0.0, index=funding.index)
    in_pos = False
    half = fee_rt / 2.0
    for i in range(len(funding)):
        r = roll.iloc[i]
        if pd.isna(r):
            continue
        want = r >= 0
        if want and not in_pos:          # enter
            pnl.iloc[i] -= half
            in_pos = True
        elif not want and in_pos:        # exit
            pnl.iloc[i] -= half
            in_pos = False
        if in_pos:                       # accrue funding this interval (short perp collects +funding)
            pnl.iloc[i] += float(funding.iloc[i])
    return pnl


def _stats(label: str, pnl: pd.Series) -> dict:
    """pnl = per-interval fractional P&L. 3 intervals/day."""
    if pnl.empty or pnl.abs().sum() == 0:
        print(f"  {label}: no data")
        return {}
    daily = pnl.resample("1D").sum()
    ann = daily.mean() * 365
    sharpe = daily.mean() / daily.std() * np.sqrt(365) if daily.std() else float("nan")
    curve = daily.cumsum()
    dd = (curve - curve.cummax()).min()
    inpos = (pnl != 0).mean()  # rough utilization proxy
    print(f"  {label:10s} net ann {ann*100:+6.1f}%  Sharpe {sharpe:+6.2f}  "
          f"maxDD {dd*100:5.1f}%  total {curve.iloc[-1]*100:+6.1f}%")
    return {"ann": ann, "sharpe": sharpe, "dd": dd, "daily": daily}


def main() -> None:
    fee_rt = _opt_f("--fee-rt", 0.0010)  # 0.10% round trip (taker, conservative-ish)
    win = _opt_i("--win", 21)            # 7 days × 3 intervals
    print(f"=== FUNDING CARRY  net basket  fee_rt={fee_rt*100:.2f}%  regime win={win} "
          f"(~{win//3}d)  [delta-neutral, carry-only] ===")

    pnls: dict[str, pd.Series] = {}
    for sym in BASKET:
        try:
            f = fetch_funding(sym)
            if f.empty:
                continue
            pnls[sym] = carry_pnl(f, fee_rt, win)
        except Exception as exc:  # noqa: BLE001
            print(f"  {sym}: {exc}")
    if not pnls:
        raise SystemExit("no funding data — run diag_funding_carry.py first")

    print("\n  per-coin (net, full 2021-2024):")
    pos_coins = 0
    for sym in BASKET:
        if sym in pnls:
            st = _stats(sym, pnls[sym])
            if st and st["ann"] > 0:
                pos_coins += 1

    # equal-weight basket: average per-interval P&L across coins
    df = pd.DataFrame(pnls).fillna(0.0)
    basket = df.mean(axis=1)
    print("\n  BASKET (equal-weight):")
    bstat = _stats("basket", basket)

    print("\n  basket net by year (the bear-survival test):")
    worst = 1e9
    for yr in YEARS:
        sub = basket[basket.index.year == yr]
        if sub.empty:
            continue
        a = sub.resample("1D").sum().mean() * 365
        worst = min(worst, a)
        print(f"    {yr}: net ann {a*100:+6.1f}%")

    # pre-registered gate check
    every_year_pos = worst > 0
    breadth_ok = pos_coins >= 7
    print(f"\n  GATE CHECK: coins net+ {pos_coins}/9 ({'PASS' if breadth_ok else 'FAIL'}); "
          f"worst-year {worst*100:+.1f}% ({'PASS' if every_year_pos else 'FAIL'}); "
          f"basket ann {bstat.get('ann', 0)*100:+.1f}% "
          f"({'PASS' if bstat.get('ann', 0) > 0 else 'FAIL'})")
    print("  CAVEAT: carry-only (no basis-noise/liquidation modeled); needs a perp venue to trade.")


if __name__ == "__main__":
    main()
