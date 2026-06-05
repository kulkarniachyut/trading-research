"""Why do trades stop out? Measure max-favorable / max-adverse excursion (in R) per setup.

Wraps Ict2022 to capture every emitted signal (entry, stop, target), then walks the M5 bars
forward to the resolution and records how far price ran in our favor before the outcome. If MFE is
routinely >1R, the target is too far (exit problem); if MFE is usually <0.5R, the entry is premature
(entry problem).
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import Signal, TimeFrame
from src.data.alpaca import AlpacaProvider
from src.strategies.ict.ict_2022 import Ict2022

_CAPTURED: list[dict] = []


class CapturingIct2022(Ict2022):
    def on_bar(self, ctx):
        sig: Signal | None = super().on_bar(ctx)
        if sig is not None and sig.side in ("long", "short") and sig.stop is not None:
            _CAPTURED.append(
                {
                    "ts": ctx.now,
                    "side": sig.side,
                    "entry": ctx.price,
                    "stop": sig.stop,
                    "target": sig.target,
                }
            )
        return sig


def mfe_mae(bars: pd.DataFrame, sig: dict, horizon: int = 60) -> dict:
    """Replay up to `horizon` bars after entry; return excursions in R and the resolution."""
    direction = 1 if sig["side"] == "long" else -1
    entry, stop, target = sig["entry"], sig["stop"], sig["target"]
    risk = abs(entry - stop)
    fut = bars[bars.index > sig["ts"]].head(horizon)
    if fut.empty or risk == 0:
        return {}
    mfe = mae = 0.0
    outcome = "open"
    for _, b in fut.iterrows():
        fav = (b["high"] - entry) if direction == 1 else (entry - b["low"])
        adv = (entry - b["low"]) if direction == 1 else (b["high"] - entry)
        mfe = max(mfe, fav / risk)
        mae = max(mae, adv / risk)
        hit_stop = b["low"] <= stop if direction == 1 else b["high"] >= stop
        hit_tgt = b["high"] >= target if direction == 1 else b["low"] <= target
        if hit_stop and hit_tgt:
            outcome = "stop"  # pessimistic, matches engine
            break
        if hit_stop:
            outcome = "stop"
            break
        if hit_tgt:
            outcome = "target"
            break
    rr = abs(target - entry) / risk
    return {"side": sig["side"], "mfe": mfe, "mae": mae, "rr_target": rr, "outcome": outcome}


def main() -> None:
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    start = sys.argv[2] if len(sys.argv) > 2 else "2023-01-01"
    end = sys.argv[3] if len(sys.argv) > 3 else "2023-12-31"
    prov = AlpacaProvider()
    bars = prov.get_bars(sym, TimeFrame.M5, pd.Timestamp(start, tz="America/New_York"),
                         pd.Timestamp(end, tz="America/New_York"))
    inst = InstrumentSpec(sym, Market("US", AssetClass.EQUITY, Product.INTRADAY))
    eng = BacktestEngine(cost_model("US", "equity"), inst, initial_equity=100_000.0, risk_pct=0.005)
    _CAPTURED.clear()
    eng.run(CapturingIct2022({}), bars, TimeFrame.M5)

    rows = [mfe_mae(bars, s) for s in _CAPTURED]
    rows = [r for r in rows if r]
    n = len(rows)
    print(f"\n{sym} {start}..{end}: {n} setups")
    if not n:
        return
    avg_rr = sum(r["rr_target"] for r in rows) / n
    print(f"  avg target RR set : {avg_rr:.2f}")
    for side in ("long", "short", "all"):
        grp = rows if side == "all" else [r for r in rows if r["side"] == side]
        if not grp:
            continue
        g = len(grp)
        avg_mfe = sum(r["mfe"] for r in grp) / g
        avg_mae = sum(r["mae"] for r in grp) / g
        reached_1r = sum(1 for r in grp if r["mfe"] >= 1.0) / g * 100
        reached_2r = sum(1 for r in grp if r["mfe"] >= 2.0) / g * 100
        wins = sum(1 for r in grp if r["outcome"] == "target") / g * 100
        print(
            f"  {side:5s} n={g:3d}  avgMFE={avg_mfe:.2f}R avgMAE={avg_mae:.2f}R  "
            f"reach1R={reached_1r:3.0f}% reach2R={reached_2r:3.0f}%  win={wins:3.0f}%"
        )


if __name__ == "__main__":
    main()
