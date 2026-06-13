"""Crypto cross-sectional momentum + BTC regime filter — crypto go-wide brick.

The strongest documented crypto edge family (Liu & Tsyvinski 2021, RFS: cross-sectional AND
time-series momentum in crypto are large and robust). Distinct from the failed 8-coin daily
TSMOM in two ways that matter:
  1. CROSS-SECTIONAL (relative-strength rotation into the top-K movers), not each-coin's-own-sign.
  2. BTC REGIME GATE — hold the basket only when BTC is above its own trend MA; go to CASH when
     BTC < MA. This is the practitioner fix for crypto's −80% bear drawdowns that make long-only
     buy&hold unsurvivable, and it is what a small aggressive account actually needs.

Long-only (spot — no perps/shorting), weekly rebalance (crypto trends faster than equities).

Honesty / no look-ahead:
- Signal at end of week w uses closes ≤ w (lookback return, skip the most recent `skip` weeks to
  avoid short-term reversal); the regime gate reads BTC's completed-bar MA at end of w.
- Returns are EARNED in week w+1 on information fully known at end of w.
- Real cost: per-side crypto cost charged on rebalance turnover (run BOTH taker and maker —
  the equity/crypto-IBS lesson is that friction, not signal, often decides crypto).

Data split (pre-registered, see docs/STEP4_EDGE_SEARCH_PLAN.md):
  Design/IS 2021-2023 (full bull→bear→recovery cycle); one-shot OOS 2024; 2025/26 SEALED.

Usage: run_xsec_crypto.py [START_YEAR END_YEAR] [--k 5] [--lookback 12] [--skip 1]
                          [--regime-ma 10] [--maker] [--no-regime]
  lookback/skip/regime-ma are in WEEKS.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.core.types import TimeFrame
from src.data.alpaca_crypto import AlpacaCryptoProvider
from src.validation import max_drawdown_r, monte_carlo

# 32 liquid Alpaca USD pairs, stablecoins (USDC/USDT/USDG/PAXG) excluded.
UNIVERSE = [
    "AAVEUSD", "ADAUSD", "ARBUSD", "AVAXUSD", "BATUSD", "BCHUSD", "BONKUSD", "BTCUSD",
    "CRVUSD", "DOGEUSD", "DOTUSD", "ETHUSD", "FILUSD", "GRTUSD", "HYPEUSD", "LDOUSD",
    "LINKUSD", "LTCUSD", "ONDOUSD", "PEPEUSD", "POLUSD", "RENDERUSD", "SHIBUSD", "SKYUSD",
    "SOLUSD", "SUSHIUSD", "TRUMPUSD", "UNIUSD", "WIFUSD", "XRPUSD", "XTZUSD", "YFIUSD",
]
# crypto round-trip friction: taker ~0.20%/side (Alpaca/retail CEX), maker ~0.10%/side.
TAKER_PER_SIDE = 0.0020
MAKER_PER_SIDE = 0.0010
ERAS = [(2021, 2021), (2022, 2022), (2023, 2023), (2024, 2024)]


def _opt(flag: str, default: int) -> int:
    a = sys.argv[1:]
    return int(a[a.index(flag) + 1]) if flag in a else default


def weekly_closes(y0: int, y1: int) -> pd.DataFrame:
    """Weekly (W-SUN) last close per coin, with a warmup year for the lookback."""
    prov = AlpacaCryptoProvider()
    start = pd.Timestamp(f"{y0 - 1}-01-01", tz="America/New_York")
    end = pd.Timestamp(f"{y1}-12-31", tz="America/New_York")
    cols = {}
    for s in UNIVERSE:
        try:
            d = prov.get_bars(s, TimeFrame.D1, start, end)
            if d is not None and len(d):
                cols[s] = d["close"].dropna()
        except Exception as exc:  # noqa: BLE001
            print(f"  {s}: fetch failed ({exc})")
    px = pd.DataFrame(cols)
    return px.resample("W-SUN").last()


def backtest(wk: pd.DataFrame, k: int, lookback: int, skip: int, regime_ma: int,
             cost_side: float, use_regime: bool, y0: int, y1: int) -> pd.Series:
    """Net weekly portfolio returns indexed by the week they were EARNED (w+1)."""
    rets = wk.pct_change()
    btc_ma = wk["BTCUSD"].rolling(regime_ma).mean() if "BTCUSD" in wk else None
    prev_holdings: set[str] = set()
    out: dict[pd.Timestamp, float] = {}
    weeks = wk.index
    for i in range(lookback + 1, len(weeks) - 1):
        past = wk.iloc[i - lookback]
        recent = wk.iloc[i - skip]
        mom = (recent / past - 1.0)
        ranked = mom.dropna().sort_values(ascending=False)
        if len(ranked) < k:
            prev_holdings = set()
            continue
        # regime gate: BTC below its MA at end of week i -> hold CASH next week
        risk_on = True
        if use_regime and btc_ma is not None:
            bm = btc_ma.iloc[i]
            risk_on = bool(pd.notna(bm) and wk["BTCUSD"].iloc[i] > bm)
        holdings = set(ranked.index[:k]) if risk_on else set()

        nxt = weeks[i + 1]
        if nxt.year < y0 or nxt.year > y1:
            prev_holdings = holdings
            continue
        gross = float(rets.loc[nxt, list(holdings)].mean()) if holdings else 0.0
        # turnover: names changed / (2*k) -> fraction of book traded; both buy & sell sides cost.
        changed = len(holdings ^ prev_holdings)
        turnover = changed / (2 * k) if (prev_holdings or holdings) else 0.0
        out[nxt] = gross - turnover * 2 * cost_side
        prev_holdings = holdings
    return pd.Series(out).sort_index()


def _stats(label: str, r: pd.Series) -> dict:
    if not len(r):
        print(f"  {label}: no data")
        return {}
    ann = (1 + r.mean()) ** 52 - 1
    sharpe = r.mean() / r.std() * np.sqrt(52) if r.std() else float("nan")
    dd = max_drawdown_r(list(r))
    inv = (r > 0).mean()  # weekly win rate among traded weeks
    print(f"  {label:20s} n={len(r):3d}wk  ann {ann * 100:+7.1f}%  Sharpe {sharpe:+.2f}  "
          f"wk-win {inv * 100:4.0f}%  maxDD~{dd * 100:5.0f}%")
    return {"ann": ann, "sharpe": sharpe, "dd": dd}


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2021, 2023)
    if y1 >= 2025:
        raise SystemExit("2025/26 stays sealed")
    k, lb, skip = _opt("--k", 5), _opt("--lookback", 12), _opt("--skip", 1)
    regime_ma = _opt("--regime-ma", 10)
    use_regime = "--no-regime" not in sys.argv
    maker = "--maker" in sys.argv
    cost_side = MAKER_PER_SIDE if maker else TAKER_PER_SIDE

    wk = weekly_closes(y0, y1)
    entry = "maker 0.10%/side" if maker else "taker 0.20%/side"
    gate = f"BTC>{regime_ma}wk-MA" if use_regime else "NO regime gate"
    print(f"=== XSEC-CRYPTO momentum  {y0}-{y1}  univ={len(wk.columns)}  top-{k}  "
          f"{lb}-{skip}wk rule  [{gate}]  [{entry}] ===")

    r = backtest(wk, k, lb, skip, regime_ma, cost_side, use_regime, y0, y1)
    # equal-weight buy&hold benchmark over the same window
    bh = wk.pct_change().mean(axis=1).dropna()
    bh = bh[(bh.index.year >= y0) & (bh.index.year <= y1)]

    m = _stats("momentum (net)", r)
    b = _stats("buy&hold (EW)", bh)
    print("  era split (momentum net):")
    for e0, e1 in ERAS:
        if e0 < y0 or e1 > y1:
            continue
        sub = r[(r.index.year >= e0) & (r.index.year <= e1)]
        if len(sub):
            _stats(f"  {e0}", sub)

    mc = monte_carlo(list(r), n_resamples=2000, seed=42)
    print(f"  MC (weekly bootstrap): total {mc.observed_total_r * 100:+.0f}%  "
          f"p5 {mc.p5_total_r * 100:+.0f}%  P(<=0) {mc.prob_total_r_le_0 * 100:.1f}%  -> "
          f"{'SURVIVES' if mc.survives else 'FAILS'}")

    # verdict helpers against the pre-registered gates
    if m and b:
        print(f"  GATE CHECK: Sharpe {m['sharpe']:+.2f} vs B&H {b['sharpe']:+.2f} "
              f"({'PASS' if m['sharpe'] > b['sharpe'] else 'FAIL'}); "
              f"maxDD {m['dd'] * 100:.0f}% vs B&H {b['dd'] * 100:.0f}% "
              f"({'PASS' if abs(m['dd']) < abs(b['dd']) * 0.7 else 'FAIL'}); "
              f"MC P(<=0) {mc.prob_total_r_le_0 * 100:.1f}% "
              f"({'PASS' if mc.prob_total_r_le_0 <= 0.10 else 'FAIL'})")


if __name__ == "__main__":
    main()
