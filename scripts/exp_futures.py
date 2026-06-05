"""Phase A.2 — does futures economics flip ict_2022's marginal edge?

ict_2022 is scale-invariant (OTE fibs, ATR-relative thresholds, price-ratio logic), so rescaling
the SPY/QQQ RTH proxy into index-point space (×proxy_factor) fires the *identical* trades — only the
cost structure changes: equity (bps spread + per-share, $0 commission) vs futures micro (tick spread
+ flat per-contract CME fee, $2/$5 point value). Sizing both to the same $ risk makes gross P&L
identical, so any net difference is *purely* the cost model. This is the clean test of the
"higher-R / lower-relative-cost futures clear the cost hurdle" hypothesis.
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.instruments import micro_future
from src.backtest.simulator import BacktestEngine
from src.core.types import TimeFrame
from src.data.alpaca import AlpacaProvider
from src.strategies.ict.ict_2022 import Ict2022

PAIRS = [("SPY", "MES"), ("QQQ", "MNQ")]
YEARS = ["2021", "2022", "2023", "2024"]
RISK_PCT = 0.005
# SAME leverage cap on both sides → identical notional cap → identical positions and gross P&L,
# so the only thing that can differ between equity and futures is the cost model. (A looser futures
# cap would let it size up on tight-stop losers — a sizing artifact, not a cost effect.)
MAX_LEV = 4.0


def _bars(prov, sym, start, end):
    return prov.get_bars(sym, TimeFrame.M5, pd.Timestamp(start, tz="America/New_York"),
                         pd.Timestamp(end, tz="America/New_York"))


def _summary(res):
    trades = res.trades
    n = len(trades)
    if not n:
        return (0, 0.0, 0.0, 0.0, 0.0)
    wins = sum(1 for t in trades if t.net_pnl > 0)
    net = sum(t.net_pnl for t in trades)
    gross = sum(t.gross_pnl for t in trades)
    costs = sum(t.costs for t in trades)
    return (n, wins / n * 100, net, costs, gross)


def run_equity(sym, bars):
    inst = InstrumentSpec(sym, Market("US", AssetClass.EQUITY, Product.INTRADAY))
    eng = BacktestEngine(cost_model("US", "equity"), inst, initial_equity=100_000.0,
                         risk_pct=RISK_PCT, max_leverage=MAX_LEV)
    return eng.run(Ict2022({}), bars, TimeFrame.M5)


def run_futures(fut_sym, bars):
    mf = micro_future(fut_sym)
    scaled = bars.copy()
    for col in ("open", "high", "low", "close"):
        scaled[col] = scaled[col] * mf.proxy_factor          # ETF price → index points
    eng = BacktestEngine(cost_model("US", "future"), mf.instrument(), initial_equity=100_000.0,
                         risk_pct=RISK_PCT, max_leverage=MAX_LEV)
    return eng.run(Ict2022({}), scaled, TimeFrame.M5)


def main() -> None:
    years = sys.argv[1:] or YEARS
    prov = AlpacaProvider()
    print(f"\n=== ict_2022: equity vs futures-proxy economics (risk {RISK_PCT:.1%}/trade, "
          f"matched {MAX_LEV:.0f}x lev → identical positions) ===")
    print(f"{'pair':10s} {'year':5s} {'n':>4} {'gross':>8} {'eq_cost':>8} {'fut_cost':>8} "
          f"{'eq_net':>8} {'fut_net':>8} {'Δnet':>7}")
    totals = {"eq": 0.0, "fut": 0.0, "ec": 0.0, "fc": 0.0}
    for etf, fut in PAIRS:
        for yr in years:
            bars = _bars(prov, etf, f"{yr}-01-01", f"{yr}-12-31")
            eq = _summary(run_equity(etf, bars))
            ft = _summary(run_futures(fut, bars))
            totals["eq"] += eq[2]
            totals["fut"] += ft[2]
            totals["ec"] += eq[3]
            totals["fc"] += ft[3]
            print(f"{etf}->{fut:5s} {yr:5s} {eq[0]:4d} {eq[4]:8.0f} {eq[3]:8.0f} {ft[3]:8.0f} "
                  f"{eq[2]:8.0f} {ft[2]:8.0f} {ft[2]-eq[2]:7.0f}")
    print(f"\nTOTAL  equity_cost {totals['ec']:.0f}  futures_cost {totals['fc']:.0f}  "
          f"(cost saved {totals['ec']-totals['fc']:+.0f})")
    print(f"       equity_net {totals['eq']:.0f}   futures_net {totals['fut']:.0f}   "
          f"Δ {totals['fut']-totals['eq']:+.0f}")


if __name__ == "__main__":
    main()
