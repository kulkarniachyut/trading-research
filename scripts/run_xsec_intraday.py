"""Intraday CROSS-SECTIONAL (relative-strength) long-short — market-neutral, regime-robust.

The one construction not yet tested, aimed at the problem that killed everything else: REGIME
DEPENDENCE. Per-coin directional edges (momentum, reversion, carry) all died when the bull/vol/
funding regime turned. A market-neutral cross-sectional book (long strongest coins, short weakest,
equal $) CANCELS the market/regime by construction and harvests DISPERSION between coins — which
crypto has in abundance. It should work in bull, bear, or dead regimes alike if the effect is real.

Each bar t (1h): signal = trailing k-bar return per coin; rank cross-sectionally; long the top-K,
short the bottom-K (equal weight, dollar-neutral); hold H bars; net of maker cost on turnover.
Test BOTH cross-sectional momentum (long winners) and reversion (long losers — crypto may revert
in relative space even while trending in absolute). OOS split: DESIGN 2023-24, OOS 2025-26.

Usage: run_xsec_intraday.py [--tf 1h] [--k 2] [--lookback 6] [--hold 3] [--revert] [--cost-bp 4]
  (cost ~4bp RT covers 2 legs maker; long-short trades 2x notional so cost is per-leg-aware.)
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from scripts.diag_crypto_intraday import BASKET, fetch_klines


def _opt(flag, d, cast=float):
    a = sys.argv[1:]
    return cast(a[a.index(flag) + 1]) if flag in a else d


def main() -> None:
    tf = _opt("--tf", "1h", str)
    k = _opt("--k", 2, int); lb = _opt("--lookback", 6, int); hold = _opt("--hold", 3, int)
    revert = "--revert" in sys.argv; cost_bp = _opt("--cost-bp", 4.0)
    mode = "REVERSION (long losers)" if revert else "MOMENTUM (long winners)"
    print(f"=== INTRADAY XSEC {mode}  tf={tf} k={k} lookback={lb}b hold={hold}b RT={cost_bp}bp "
          f"dollar-neutral ===")

    cols = {}
    for s in BASKET:
        try:
            cols[s] = fetch_klines(s, tf)
        except Exception as exc:  # noqa: BLE001
            print(f"  {s}: {exc}")
    px = pd.DataFrame(cols).dropna(how="all").ffill()
    px = px.dropna(axis=1, thresh=int(len(px) * 0.5))  # keep coins with decent history
    rets = px.pct_change()
    signal = px.pct_change(lb)                       # trailing lookback return
    # forward hold-bar return earned starting next bar (causal): enter at t+1, exit t+1+hold
    fwd = px.shift(-1 - hold) / px.shift(-1) - 1.0

    out = {}
    n = len(px)
    prev_long, prev_short = set(), set()
    pnl_series = []
    for i in range(lb + 1, n - hold - 2, hold):      # rebalance every `hold` bars (no overlap)
        sig = signal.iloc[i].dropna()
        if len(sig) < 2 * k:
            continue
        ranked = sig.sort_values(ascending=False)
        longs = list(ranked.index[:k]); shorts = list(ranked.index[-k:])
        if revert:
            longs, shorts = shorts, longs            # long losers / short winners
        f = fwd.iloc[i]
        gross = f[longs].mean() - f[shorts].mean()   # dollar-neutral L/S
        # turnover cost: names rotated in/out, both legs, maker per side
        turn = len((set(longs) ^ prev_long) | (set(shorts) ^ prev_short)) / (2 * k)
        cost = turn * (cost_bp / 1e4)
        ts = px.index[i + 1]
        pnl_series.append((ts, gross - cost))
        prev_long, prev_short = set(longs), set(shorts)

    if not pnl_series:
        raise SystemExit("no trades")
    s = pd.Series({t: v for t, v in pnl_series}).sort_index()
    bars_per_yr = {"1h": 8760, "15m": 35040}.get(tf, 8760)
    reb_per_yr = bars_per_yr / hold
    for label, mask in [("DESIGN 2023-24", s.index.year <= 2024), ("OOS 2025-26", s.index.year >= 2025)]:
        sub = s[mask]
        if not len(sub):
            continue
        ann = sub.mean() * reb_per_yr
        sharpe = sub.mean() / sub.std() * np.sqrt(reb_per_yr) if sub.std() else 0
        print(f"  {label:14s} n={len(sub):5d}  mean/reb {sub.mean()*1e4:+6.1f}bp  "
              f"ann~{ann*100:+6.1f}%  Sharpe~{sharpe:+.2f}  win {(sub>0).mean()*100:4.1f}%")


if __name__ == "__main__":
    main()
