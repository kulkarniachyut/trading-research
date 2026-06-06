"""Phase E driver — the definitive validation run (Step 2.7 · E, the verdict).

Wires the breadth universe + the fixed full-setup ``Ict2022`` model through the walk-forward OOS
folds and Monte-Carlo robustness test, then prints a one-screen verdict table. No tuning happens
here — the defaults already encode the full ICT setup; E *measures*.

Equities are the headline portfolio (B.5 verdict: crypto-in-NY-window is net-negative — wrong
session + %-notional cost); crypto is printed as a separate secondary sleeve, never masking the
equity read. Phase-D block filters stay OFF (decks + our backtest agree news is a catalyst).

GUARDRAIL (CLAUDE.md): 2025 + 2026 are the clean final holdout. This script REFUSES to touch them
unless ``--final`` is passed, and prints a loud banner when it does — so the holdout is spent once,
deliberately. Build + dry-run on the burned years (2021–2024) only.

Usage:
    uv run python -m scripts.run_phase_e                 # burned years 2021-2024 (default, safe)
    uv run python -m scripts.run_phase_e 2021 2022 2023 2024
    uv run python -m scripts.run_phase_e --equities-only
    uv run python -m scripts.run_phase_e --final 2021 2022 2023 2024 2025 2026   # spends the holdout
"""

from __future__ import annotations

import sys

from src.backtest.costs import AssetClass
from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.strategies.ict.ict_2022 import Ict2022
from src.validation import make_folds, monte_carlo, walk_forward

EQUITIES = [
    "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN",
    "META", "GOOGL", "TSLA", "AMD", "NFLX", "JPM", "XLE", "GLD",
]
CRYPTO = ["BTCUSD", "ETHUSD", "LTCUSD", "BCHUSD", "SOLUSD", "AVAXUSD", "LINKUSD", "DOGEUSD"]

BURNED_YEARS = [2021, 2022, 2023, 2024]
HOLDOUT_YEARS = {2025, 2026}


def make_ict(params: dict | None = None) -> Ict2022:
    """Factory: fresh full-setup state machine (optional param override for ablation folds)."""
    return Ict2022(params or {})


def _print_wf(title: str, wf) -> None:
    print(f"\n=== {title}: walk-forward OOS ===")
    print(f"  {'fold':36s} {'n':>5} {'win%':>6} {'exp R':>8} {'net $':>12}")
    for fr in wf.folds:
        t = fr.test
        print(f"  {fr.fold.label:36s} {t.trade_count:5d} {t.win_rate:6.0f} "
              f"{t.expectancy_r:+8.3f} {t.total_net:12,.0f}")
    print(f"  {'POOLED OOS':36s} {wf.trade_count:5d} {wf.win_rate:6.0f} "
          f"{wf.expectancy_r:+8.3f} {wf.total_net:12,.0f}")
    print(f"  per-symbol breadth (share of symbols net-positive): {wf.breadth_positive:.0%}")
    print("  per symbol (n / win% / net), pooled OOS:")
    for sym, n, win, net in wf.per_symbol():
        if n:
            print(f"    {sym:6s} {n:3d}  {win:3.0f}%  {net:9,.0f}")


def _print_mc(title: str, wf) -> None:
    returns = wf.returns_r
    if not returns:
        print(f"\n=== {title}: Monte-Carlo === (no trades — skipped)")
        return
    mc = monte_carlo(returns, n_resamples=2000, seed=0)
    print(f"\n=== {title}: Monte-Carlo ({mc.n_resamples} bootstraps, n={mc.n_trades}) ===")
    print(f"  observed total R   : {mc.observed_total_r:+.2f}   (max DD {mc.observed_max_dd_r:.2f} R)")
    print(f"  total R  p5 / mean / p95 : {mc.p5_total_r:+.2f} / {mc.mean_total_r:+.2f} / "
          f"{mc.p95_total_r:+.2f}")
    print(f"  p5 expectancy/trade      : {mc.p5_expectancy_r:+.4f} R")
    print(f"  max DD   median / p95    : {mc.median_max_dd_r:.2f} / {mc.p95_max_dd_r:.2f} R")
    print(f"  P(total R <= 0)          : {mc.prob_total_r_le_0:.1%}")
    verdict = "PASS (p5 >= breakeven)" if mc.survives else "FAIL (p5 < breakeven)"
    print(f"  MC verdict               : {verdict}")


def run_sleeve(title, universe, years, *, provider, crypto_provider=None) -> None:
    folds = make_folds(years, scheme="anchored")
    wf = walk_forward(make_ict, universe, folds, run_fn=run_portfolio,
                      provider=provider, crypto_provider=crypto_provider,
                      base_tf=TimeFrame.M5)
    bad = {f.test.start.year: f.test.errors for f in wf.folds if f.test.errors}
    if bad:
        print(f"  [{title}] per-symbol errors by test year: {bad}")
    _print_wf(title, wf)
    _print_mc(title, wf)


def main() -> None:
    args = [a for a in sys.argv[1:]]
    final = "--final" in args
    equities_only = "--equities-only" in args
    year_args = [int(a) for a in args if a.isdigit()]
    years = year_args or BURNED_YEARS

    peeked = HOLDOUT_YEARS & set(years)
    if peeked and not final:
        print(f"REFUSING: years {sorted(peeked)} are the reserved 2025/26 holdout (CLAUDE.md).")
        print("Build + dry-run on burned years 2021-2024 only. Pass --final to spend the holdout "
              "ONCE for the definitive readout.")
        sys.exit(2)
    if peeked and final:
        print("=" * 72)
        print(f"  SPENDING THE FINAL HOLDOUT {sorted(peeked)} — this is the one-shot Phase-E verdict.")
        print("  Record the result in CLAUDE.md Build status (Step 2.7 E) and HANDOFF.md.")
        print("=" * 72)

    try:
        from src.data.alpaca import AlpacaProvider
        provider = AlpacaProvider()
    except RuntimeError as exc:
        print(f"\nPRECONDITION NOT MET: {exc}")
        print("Phase E needs Alpaca keys. Put ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY in a `.env` "
              "at the workspace root (or config/secrets.yaml), then re-run.")
        sys.exit(1)

    print(f"Phase E · years {years} · anchored walk-forward · fixed full ICT-2022 setup")

    eq_universe = [UniverseItem(s) for s in EQUITIES]
    run_sleeve("EQUITIES (headline)", eq_universe, years, provider=provider)

    if not equities_only:
        try:
            from src.data.alpaca_crypto import AlpacaCryptoProvider
            crypto_provider = AlpacaCryptoProvider()
            cr_universe = [UniverseItem(s, AssetClass.CRYPTO) for s in CRYPTO]
            run_sleeve("CRYPTO (secondary)", cr_universe, years,
                       provider=provider, crypto_provider=crypto_provider)
        except RuntimeError as exc:
            print(f"\n(crypto sleeve skipped — {exc})")


if __name__ == "__main__":
    main()
