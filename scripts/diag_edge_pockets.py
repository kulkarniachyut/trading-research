"""Phase B, step 1 — WHERE is the gross edge, if anywhere?

Phase A proved the loss is in the signal (gross-negative), not cost. Before adding any filter,
find empirically which *conditions* carry positive gross expectancy. Capture every ict_2022 setup
with its features, replay forward for the realized **gross R-multiple** (edge, frictionless), and
slice by time-of-day window / side / daily-bias alignment / displacement strength — pooled across
years for sample size. Build the selective strategy around pockets that are positive AND consistent;
ignore one-off spikes (overfitting).
"""

from __future__ import annotations

import sys
from collections import defaultdict

import pandas as pd

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import Signal, TimeFrame
from src.data.alpaca import AlpacaProvider
from src.indicators import classic
from src.strategies.ict.ict_2022 import Ict2022, daily_bias

YEARS = ["2021", "2022", "2023", "2024"]


def _window(ts: pd.Timestamp) -> str:
    """Finest ICT time bucket for an entry timestamp (NY)."""
    hm = ts.hour * 60 + ts.minute
    if 9 * 60 + 50 <= hm < 10 * 60 + 10:
        return "macro_950"      # NY AM macro (subset of silver bullet)
    if 10 * 60 <= hm < 11 * 60:
        return "silver_1011"    # Silver Bullet 10–11 (excl. macro overlap above)
    if 9 * 60 + 30 <= hm < 11 * 60 + 30:
        return "am_kz_rest"     # rest of AM killzone
    if 13 * 60 + 30 <= hm < 15 * 60 + 30:
        return "pm_kz"          # PM killzone
    return "other"


def _strength_bucket(s: float) -> str:
    if s < 1.5:
        return "disp<1.5"
    if s < 2.0:
        return "disp1.5-2"
    if s < 3.0:
        return "disp2-3"
    return "disp3+"


class Capturing(Ict2022):
    def on_start(self, ctx):
        super().on_start(ctx)
        self.captured: list[dict] = []

    def on_bar(self, ctx):
        sig: Signal | None = super().on_bar(ctx)
        if sig and sig.side in ("long", "short") and sig.stop is not None and self._setup:
            disp = self._setup.displacement
            m5 = ctx.window(TimeFrame.M5, 30)
            atr = float(classic.atr(m5, 14).iloc[-1]) if len(m5) >= 15 else 0.0
            leg = abs(disp.leg_high - disp.leg_low) if disp else 0.0
            strength = leg / atr if atr > 0 else 0.0
            d1 = ctx.window(TimeFrame.D1, 60)
            bias = daily_bias(d1, length=5) if len(d1) >= 7 else 0
            direction = 1 if sig.side == "long" else -1
            align = "aligned" if bias == direction else "counter" if bias == -direction else "neutral"
            self.captured.append({
                "ts": ctx.now, "side": sig.side, "entry": ctx.price, "stop": sig.stop,
                "target": sig.target, "window": _window(ctx.now), "align": align,
                "strength": _strength_bucket(strength),
            })
        return sig


def gross_r(bars: pd.DataFrame, s: dict, horizon: int = 60) -> float | None:
    d = 1 if s["side"] == "long" else -1
    entry, stop, target = s["entry"], s["stop"], s["target"]
    risk = abs(entry - stop)
    if risk == 0:
        return None
    rr = abs(target - entry) / risk
    fut = bars[bars.index > s["ts"]].head(horizon)
    if fut.empty:
        return None
    for _, b in fut.iterrows():
        hit_stop = b["low"] <= stop if d == 1 else b["high"] >= stop
        hit_tgt = b["high"] >= target if d == 1 else b["low"] <= target
        if hit_stop:                 # stop-first on straddle (pessimistic)
            return -1.0
        if hit_tgt:
            return rr
    last = float(fut["close"].iloc[-1])      # neither hit in horizon → mark to last close
    return (last - entry) / risk * d


def _report(title: str, groups: dict[str, list[float]]) -> None:
    print(f"\n  {title}")
    for key in sorted(groups):
        rs = groups[key]
        n = len(rs)
        if n == 0:
            continue
        win = sum(1 for r in rs if r > 0) / n * 100
        exp = sum(rs) / n
        flag = "  <<<" if exp > 0.05 and n >= 15 else ""
        print(f"    {key:14s} n={n:4d}  win={win:4.0f}%  grossR/trade={exp:+.2f}{flag}")


def main() -> None:
    years = sys.argv[1:] or YEARS
    prov = AlpacaProvider()
    rows: list[dict] = []
    for sym in ("SPY", "QQQ"):
        for yr in years:
            bars = prov.get_bars(sym, TimeFrame.M5, pd.Timestamp(f"{yr}-01-01", tz="America/New_York"),
                                 pd.Timestamp(f"{yr}-12-31", tz="America/New_York"))
            inst = InstrumentSpec(sym, Market("US", AssetClass.EQUITY, Product.INTRADAY))
            eng = BacktestEngine(cost_model("US", "equity"), inst, initial_equity=100_000.0, risk_pct=0.005)
            strat = Capturing({})
            eng.run(strat, bars, TimeFrame.M5)
            for s in strat.captured:
                r = gross_r(bars, s)
                if r is not None:
                    s["r"] = r
                    rows.append(s)

    print(f"\n=== edge pockets: {len(rows)} setups, gross R-multiple (frictionless), "
          f"SPY+QQQ {years[0]}..{years[-1]} ===")
    overall = [s["r"] for s in rows]
    print(f"  overall: n={len(overall)} win={sum(1 for r in overall if r>0)/len(overall)*100:.0f}% "
          f"grossR/trade={sum(overall)/len(overall):+.2f}")
    for dim in ("window", "side", "align", "strength"):
        g: dict[str, list[float]] = defaultdict(list)
        for s in rows:
            g[s[dim]].append(s["r"])
        _report(f"by {dim}:", g)
    # the key cross-tab: window × bias alignment
    g2: dict[str, list[float]] = defaultdict(list)
    for s in rows:
        g2[f"{s['window']}|{s['align']}"].append(s["r"])
    _report("by window × alignment:", g2)


if __name__ == "__main__":
    main()
