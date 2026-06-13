"""Step 4, family 1 — ORB on index micro futures (design years 2017-2022 ONLY by default).

Engine + futures cost model (no shortcuts). Ablations are explicit flags so every run is a
recorded experiment, not a tuning loop. 2023/24 stay untouched for walk-forward OOS folds.

Usage: run_orb.py [YEAR ...] [--long-only] [--range-break] [--or-bars N] [--rr R] [--gc]
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass
from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.archive import HOLDOUT_START_YEAR
from src.data.databento_provider import DatabentoProvider
from src.strategies.momentum.orb import Orb

DESIGN_YEARS = ["2017", "2018", "2019", "2020", "2021", "2022"]

# databento continuous symbol -> micro (point value, tick) economics (matches run_futures.py).
FUT = [
    ("ES.c.0", 5.0, 0.25),   # MES
    ("NQ.c.0", 2.0, 0.25),   # MNQ
    ("RTY.c.0", 5.0, 0.10),  # M2K
    ("YM.c.0", 0.50, 1.0),   # MYM
]
GC = ("GC.c.0", 10.0, 0.10)  # MGC — non-index control, off by default


def _opt(args: list[str], flag: str, default: float) -> float:
    return float(args[args.index(flag) + 1]) if flag in args else default


def main() -> None:
    args = sys.argv[1:]
    years = [a for a in args if a.isdigit() and len(a) == 4] or DESIGN_YEARS
    if any(int(y) >= HOLDOUT_START_YEAR for y in years):
        raise SystemExit("refusing holdout years — final readout goes through run_phase_e style harness")
    params = {
        "long_only": "--long-only" in args,
        "mode": "range_break" if "--range-break" in args else "first_bar_dir",
        "or_bars": int(_opt(args, "--or-bars", 1)),
        "rr_target": _opt(args, "--rr", 10.0),
    }
    fut = FUT + [GC] if "--gc" in args else FUT

    prov = DatabentoProvider()
    uni = [UniverseItem(s, AssetClass.FUTURE, multiplier=m, tick_size=t) for s, m, t in fut]
    tag = (f"{params['mode']} or_bars={params['or_bars']} rr={params['rr_target']:g}"
           f"{' LONG-ONLY' if params['long_only'] else ''}")

    pooled: list = []
    print(f"=== ORB [{tag}]  risk 0.5%/trade, $100k sleeves, micro economics ===")
    for yr in years:
        res = run_portfolio(
            lambda: Orb(params), uni,
            pd.Timestamp(f"{yr}-01-01", tz="America/New_York"),
            pd.Timestamp(f"{yr}-12-31", tz="America/New_York"),
            provider=prov, base_tf=TimeFrame.M5,
        )
        trades = [t for r in res.results.values() for t in r.trades]
        pooled.extend(trades)
        per_sym = "  ".join(f"{s.split('.')[0]}:{net:+,.0f}" for s, n, _, net in res.per_symbol() if n)
        print(f"  {yr}: {res.trade_count:4d} tr ({res.trades_per_week:4.1f}/wk)  win {res.win_rate:4.1f}%  "
              f"net {res.total_net:+10,.0f}  exp {res.expectancy_r:+.3f}R   [{per_sym}]"
              f"{'  errs=' + str(res.errors) if res.errors else ''}", flush=True)

    if pooled:
        n = len(pooled)
        net = sum(t.net_pnl for t in pooled)
        gross = sum(t.gross_pnl for t in pooled)
        win = sum(1 for t in pooled if t.net_pnl > 0) / n * 100
        risk = 0.005 * 100_000
        eod = sum(1 for t in pooled if t.reason_out == "signal")
        st = sum(1 for t in pooled if t.reason_out == "stop")
        tg = sum(1 for t in pooled if t.reason_out == "target")
        print(f"  POOLED {years[0]}-{years[-1]}: {n} tr  win {win:.1f}%  net {net:+,.0f}  "
              f"exp {net / n / risk:+.3f}R (gross {gross / n / risk:+.3f}R, "
              f"cost {(gross - net) / n / risk:.3f}R/tr)  (eod {eod} / stop {st} / tgt {tg})")


if __name__ == "__main__":
    main()
