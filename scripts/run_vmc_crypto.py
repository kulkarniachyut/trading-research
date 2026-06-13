"""VMC Cipher B (trend-gated) on intraday crypto — the go-wide VuManChu brick.

Pre-registered in docs/STEP4_EDGE_SEARCH_PLAN.md before this run. Tests whether the WaveTrend
mean-reversion `buy`, GATED by a 200-EMA trend filter and traded INTRADAY (H4/H1) — the way crypto
traders actually use VMC — clears a post-cost edge where naked daily IBS could not (daily crypto
trends, so an unfiltered reversion signal had no gross edge there).

Runs taker (market@open, 0.10%/side) and maker (resting limit@signal-close, ~0.04% maker, no
spread/slippage). Universe = the 8 liquid coins; 2021-2024 only (2025/26 stays sealed).

Usage: run_vmc_crypto.py [START_YEAR END_YEAR] [--limit] [--tf 4h|1h]
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass
from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.alpaca_crypto import AlpacaCryptoProvider
from src.strategies.vumanchu.cipher_strategy import VmcCipher
from src.validation import monte_carlo

COINS = ["BTCUSD", "ETHUSD", "LTCUSD", "BCHUSD", "SOLUSD", "AVAXUSD", "LINKUSD", "DOGEUSD"]
EQUITY = 100_000.0
RISK = 0.005
ERAS = [(2021, 2021), (2022, 2022), (2023, 2023), (2024, 2024)]


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2021, 2024)
    if y1 >= 2025:
        raise SystemExit("2025/26 stays sealed")
    limit = "--limit" in sys.argv
    tf = sys.argv[sys.argv.index("--tf") + 1] if "--tf" in sys.argv else "4h"
    # Alpaca crypto fetches H1 (its coarsest sub-daily granularity); the clock resamples H1 -> the
    # decision TF (e.g. H4), so the decision bar is always built from real H1 data, no look-ahead.
    base_tf = TimeFrame.H1
    params = {"decision_tf": tf}
    if "--gold" in sys.argv:
        # Canonical gold_buy REVERSAL setup: buy + causal bullish divergence + RSI<30. This is a
        # reversal signal, so the trend-continuation gates (200-EMA, money-flow-green) are dropped
        # — they structurally contradict a deep-oversold entry (proven: gated gold_buy = 0 trades).
        params |= {"entry_signal": "gold_buy", "trend_len": 1, "require_money_flow": False}
    if limit:
        params |= {"limit_entry": True, "limit_ttl_bars": 6}

    prov = AlpacaCryptoProvider()
    uni = [UniverseItem(c, AssetClass.CRYPTO) for c in COINS]
    res = run_portfolio(
        lambda: VmcCipher(params), uni,
        pd.Timestamp(f"{y0}-01-01", tz="America/New_York"),
        pd.Timestamp(f"{y1}-12-31", tz="America/New_York"),
        provider=prov, crypto_provider=prov, base_tf=base_tf,
        initial_equity=EQUITY, risk_pct=RISK, max_leverage=2.0, passive_maker=limit,
    )
    risk = RISK * EQUITY
    trades = [t for r in res.results.values() for t in r.trades]
    entry = "LIMIT@close (maker)" if limit else "market@open (taker)"
    print(f"=== VMC-CRYPTO [{entry}] tf={tf}  {y0}-{y1}  {len(res.results)}/{len(COINS)} coins "
          f"(R=${risk:,.0f}) ===")
    if res.errors:
        print(f"  errors: {res.errors}")
    if not trades:
        print("  no trades")
        return

    for e0, e1 in ERAS:
        ts = [t for t in trades if e0 <= pd.Timestamp(t.exit_ts).year <= e1]
        if ts:
            net = sum(t.net_pnl for t in ts)
            print(f"  {e0}: {len(ts):4d} tr  win {sum(1 for t in ts if t.net_pnl > 0) / len(ts) * 100:4.1f}%  "
                  f"net {net:+10,.0f}  exp {net / len(ts) / risk:+.3f}R")

    n = len(trades)
    net = sum(t.net_pnl for t in trades)
    gross = sum(t.gross_pnl for t in trades)
    pos = sum(1 for _, ns, _, nt in res.per_symbol() if ns and nt > 0)
    tot = sum(1 for _, ns, _, _ in res.per_symbol() if ns)
    print(f"  POOLED: {n} tr  win {sum(1 for t in trades if t.net_pnl > 0) / n * 100:.1f}%  "
          f"net {net:+,.0f}  exp {net / n / risk:+.3f}R (gross {gross / n / risk:+.3f}R, "
          f"cost {(gross - net) / n / risk:.3f}R/tr)")
    print(f"  breadth+: {pos}/{tot}")
    for sym, ns, win, nt in res.per_symbol():
        if ns:
            print(f"    {sym:8s} {ns:4d} tr  win {win:4.1f}%  net {nt:+10,.0f}  exp {nt / ns / risk:+.3f}R")
    mc = monte_carlo([t.net_pnl / risk for t in trades], n_resamples=2000, seed=42)
    print(f"  MC: total {mc.observed_total_r:+.1f}R  p5 {mc.p5_total_r:+.1f}R  "
          f"P(<=0) {mc.prob_total_r_le_0 * 100:.1f}%  -> {'SURVIVES' if mc.survives else 'FAILS'}")


if __name__ == "__main__":
    main()
