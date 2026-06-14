"""VMC multi-timeframe (1H exec / 4H confirm) Wolfpack strategy on crypto — from the user's video.

`vmc_wolfpack`: 1H 200-EMA trend + pullback-into-EMA + Wolfpack green cross, confirmed by a 4H
Cipher-B buy/divergence + 4H Wolfpack green; 1:3 R:R (stop+target). Long-only (spot can't short;
the video's short side needs a perp venue). Base H1 (the clock resamples to H4 for confirmation).

8-coin universe, 2021-2024 (2025/26 sealed). Runs taker by default; --limit for maker entry.
Usage: run_vmc_wolfpack.py [START_YEAR END_YEAR] [--limit]
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass
from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.alpaca_crypto import AlpacaCryptoProvider
from src.strategies.vumanchu.wolfpack_mtf import VmcWolfpack
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
    params = {"limit_entry": True, "limit_ttl_bars": 3} if limit else {}

    prov = AlpacaCryptoProvider()
    uni = [UniverseItem(c, AssetClass.CRYPTO) for c in COINS]
    res = run_portfolio(
        lambda: VmcWolfpack(params), uni,
        pd.Timestamp(f"{y0}-01-01", tz="America/New_York"),
        pd.Timestamp(f"{y1}-12-31", tz="America/New_York"),
        provider=prov, crypto_provider=prov, base_tf=TimeFrame.H1,
        initial_equity=EQUITY, risk_pct=RISK, max_leverage=2.0, passive_maker=limit,
    )
    risk = RISK * EQUITY
    trades = [t for r in res.results.values() for t in r.trades]
    entry = "LIMIT@close (maker)" if limit else "market@open (taker)"
    print(f"=== VMC-WOLFPACK [{entry}] 1H/4H  {y0}-{y1}  {len(res.results)}/{len(COINS)} coins "
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
