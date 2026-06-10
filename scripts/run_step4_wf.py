"""Step 4 — walk-forward + Monte-Carlo for the new families (IBS / TSMOM), theory-fixed params.

Wraps ``run_portfolio`` with a **warm-up aware** run_fn: each fold's span is fetched with extra
leading history (so a 200d MA / 252d lookback is warm on day one of the test span) but only trades
*entered inside* the span are counted. Without this, per-year folds start cold and the first ~10
months of each test year are silently untraded.

Discipline:
- Default folds dry-run INSIDE the design years (tests 2019-2022) — burned data, safe to iterate.
- ``--oos`` runs the one-shot read on 2023/2024 (anchored train = all prior years, informational
  only — params are theory-fixed, nothing is tuned). Do not iterate against it.
- 2025/26 stays sealed; this script refuses it entirely.

Usage: run_step4_wf.py --family ibs|tsmom [--oos]
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass
from src.backtest.portfolio import PortfolioResult, UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.databento_provider import DatabentoProvider
from src.strategies.meanrev.ibs import IbsRev
from src.strategies.momentum.tsmom import Tsmom
from src.validation import Fold, make_folds, monte_carlo, walk_forward

NY = "America/New_York"
INITIAL_EQUITY = 250_000.0
RISK_PCT = 0.01

INDEX_FUT = [
    ("ES.c.0", 5.0, 0.25),
    ("NQ.c.0", 2.0, 0.25),
    ("RTY.c.0", 5.0, 0.10),
    ("YM.c.0", 0.50, 1.0),
    ("GC.c.0", 10.0, 0.10),
]
FX_FUT = [
    ("6E.c.0", 12_500.0, 0.0001),
    ("6B.c.0", 6_250.0, 0.0001),
    ("6A.c.0", 10_000.0, 0.0001),
    ("6J.c.0", 1_250_000.0, 0.000001),
]

FAMILIES = {
    # family: (strategy factory, universe rows, calendar-day warm-up)
    "ibs": (IbsRev, INDEX_FUT, 320),               # 200 trading days ≈ 290 calendar + slack
    "tsmom": (Tsmom, INDEX_FUT + FX_FUT, 390),     # 252 trading days ≈ 365 calendar + slack
}


def main() -> None:
    args = sys.argv[1:]
    family = args[args.index("--family") + 1] if "--family" in args else "ibs"
    cls, fut, warmup_days = FAMILIES[family]
    oos = "--oos" in args

    if oos:
        # ONE continuous 2023-24 test span (train = design years, informational — nothing is
        # tuned). Why not per-year folds: fold pooling counts only fresh-entry trades, so P&L of
        # positions *carried into* a year is excluded — a live trader holds those. The TSMOM
        # dry-run swung -0.155R -> +0.141R purely on that attribution choice; a continuous span
        # with warm entry + end-of-data mark-to-market is the live-replicable estimand.
        folds = [Fold(label="train 2017-2022 → test 2023-2024",
                      train_start=pd.Timestamp("2017-01-01", tz=NY),
                      train_end=pd.Timestamp("2022-12-31", tz=NY),
                      test_start=pd.Timestamp("2023-01-01", tz=NY),
                      test_end=pd.Timestamp("2024-12-31", tz=NY))]
    else:
        folds = make_folds([2018, 2019, 2020, 2021, 2022], scheme="anchored")
    assert all(f.test_end.year < 2025 for f in folds), "holdout is sealed"

    prov = DatabentoProvider()
    uni = [UniverseItem(s, AssetClass.FUTURE, multiplier=m, tick_size=t) for s, m, t in fut]
    pad = pd.Timedelta(days=warmup_days)

    def run_with_warmup(factory, universe, start, end, **kw) -> PortfolioResult:
        res = run_portfolio(factory, universe, start - pad, end, **kw)
        for r in res.results.values():
            r.trades = [t for t in r.trades if pd.Timestamp(t.entry_ts) >= start]
        res.start = start  # so trades/week reflects the counted span
        return res

    wf = walk_forward(
        lambda p=None: cls(p or {}), uni, folds,
        run_fn=run_with_warmup, provider=prov, base_tf=TimeFrame.H1,
        risk_pct=RISK_PCT, initial_equity=INITIAL_EQUITY,
    )

    label = "OOS 2023/24 (one-shot)" if oos else "design-years dry-run"
    print(f"=== Step-4 walk-forward · {family} · {label} · theory-fixed defaults ===")
    for fr in wf.folds:
        errs = f"  errs={fr.test.errors}" if fr.test.errors else ""
        print(f"  {fr.fold.label}:  {fr.test_trade_count:4d} tr  "
              f"exp {fr.test_expectancy_r:+.3f}R  win {fr.test.win_rate:4.1f}%{errs}")
    n = wf.trade_count
    if not n:
        print("  no pooled trades")
        return
    by_year: dict[int, list] = {}
    for _, t in wf.tagged_test_trades:
        by_year.setdefault(pd.Timestamp(t.exit_ts).year, []).append(t)
    for yr in sorted(by_year):
        ts = by_year[yr]
        net_y = sum(t.net_pnl for t in ts)
        print(f"    exit-{yr}: {len(ts):4d} tr  net {net_y:+10,.0f}  "
              f"exp {net_y / len(ts) / (RISK_PCT * INITIAL_EQUITY):+.3f}R")
    print(f"  POOLED test: {n} tr  win {wf.win_rate:4.1f}%  net {wf.total_net:+,.0f}  "
          f"exp {wf.expectancy_r:+.3f}R  breadth+ {wf.breadth_positive * 100:.0f}%")
    for sym, n_s, win_s, net_s in wf.per_symbol():
        if n_s:
            print(f"    {sym:8s} {n_s:4d} tr  win {win_s:4.1f}%  net {net_s:+10,.0f}")
    mc = monte_carlo(wf.returns_r, n_resamples=2000, seed=42)
    print(f"  MC: total {mc.observed_total_r:+.1f}R  p5 {mc.p5_total_r:+.1f}R  "
          f"p5-exp {mc.p5_expectancy_r:+.4f}R  P(<=0) {mc.prob_total_r_le_0 * 100:.1f}%  "
          f"p95 maxDD {mc.p95_max_dd_r:.1f}R  -> {'SURVIVES' if mc.survives else 'FAILS'}")


if __name__ == "__main__":
    main()
