"""Calibration experiment: run named ict_2022 configs on a year and report edge + expectancy.

Discipline: calibrate on the in-sample year only, then validate the chosen config OOS. The metric
that matters is *edge* (does the filter raise reach-1R and separate MFE from MAE), not raw PnL.
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import Signal, TimeFrame
from src.data.alpaca import AlpacaProvider
from src.strategies.ict.ict_2022 import Ict2022

CONFIGS: dict[str, dict] = {
    "baseline": {},
    "bias_on": {"require_daily_bias": True},
    "fvg_entry": {"entry_require_fvg": True},
    "pd_align": {"require_daily_bias": True, "require_daily_pd_alignment": True},
    "confirm": {"entry_confirm": True},
    "disp_strong": {"displacement_atr_mult": 2.0},
    "bias+confirm": {"require_daily_bias": True, "entry_confirm": True},
    "bias+fvg": {"require_daily_bias": True, "entry_require_fvg": True},
    "bias+confirm+fvg": {"require_daily_bias": True, "entry_confirm": True, "entry_require_fvg": True},
}


def _bars(prov, sym, start, end):
    return prov.get_bars(sym, TimeFrame.M5, pd.Timestamp(start, tz="America/New_York"),
                         pd.Timestamp(end, tz="America/New_York"))


def run_config(sym, bars, params):
    captured: list[dict] = []

    class Cap(Ict2022):
        def on_bar(self, ctx):
            sig: Signal | None = super().on_bar(ctx)
            if sig and sig.side in ("long", "short") and sig.stop is not None:
                captured.append({"ts": ctx.now, "side": sig.side, "entry": ctx.price,
                                 "stop": sig.stop, "target": sig.target})
            return sig

    inst = InstrumentSpec(sym, Market("US", AssetClass.EQUITY, Product.INTRADAY))
    eng = BacktestEngine(cost_model("US", "equity"), inst, initial_equity=100_000.0, risk_pct=0.005)
    res = eng.run(Cap(params), bars, TimeFrame.M5)

    # edge: fraction of setups whose price reaches +1R favorable within 60 bars
    reach1r = 0
    for s in captured:
        d = 1 if s["side"] == "long" else -1
        risk = abs(s["entry"] - s["stop"]) or 1e9
        fut = bars[bars.index > s["ts"]].head(60)
        mfe = 0.0
        for _, b in fut.iterrows():
            fav = (b["high"] - s["entry"]) if d == 1 else (s["entry"] - b["low"])
            mfe = max(mfe, fav / risk)
        if mfe >= 1.0:
            reach1r += 1
    n = len(res.trades)
    wins = sum(1 for t in res.trades if t.net_pnl > 0)
    net = sum(t.net_pnl for t in res.trades)
    exp = net / n if n else 0.0
    r1 = reach1r / len(captured) * 100 if captured else 0.0
    return n, (wins / n * 100 if n else 0.0), net, exp, r1


def main() -> None:
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    start = sys.argv[2] if len(sys.argv) > 2 else "2023-01-01"
    end = sys.argv[3] if len(sys.argv) > 3 else "2023-12-31"
    prov = AlpacaProvider()
    bars = _bars(prov, sym, start, end)
    print(f"\n=== {sym} {start}..{end} (in-sample calibration) ===")
    print(f"{'config':20s} {'n':>4} {'win%':>6} {'net':>9} {'exp/t':>8} {'reach1R%':>9}")
    for name, params in CONFIGS.items():
        n, win, net, exp, r1 = run_config(sym, bars, params)
        print(f"{name:20s} {n:4d} {win:6.1f} {net:9.0f} {exp:8.1f} {r1:9.0f}")


if __name__ == "__main__":
    main()
