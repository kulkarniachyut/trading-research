"""Phase C — SMT divergence primitive + the causal ctx.ref() wiring through the engine."""

from __future__ import annotations

import pandas as pd

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import MarketContext, TimeFrame
from src.strategies.base import BaseStrategy
from src.strategies.ict.ict_2022 import smt_divergence

NY = "America/New_York"


def _frame(lows, highs):
    idx = pd.date_range("2024-03-12 09:30", periods=len(lows), freq="5min", tz=NY)
    return pd.DataFrame({"open": lows, "high": highs, "low": lows, "close": highs}, index=idx)


def test_bullish_smt_when_primary_lower_low_reference_holds():
    # lookback=4: prior=bars0-3, recent=bars4-7
    primary = _frame([10, 10, 10, 10, 9, 9, 9, 8], [11] * 8)   # recent low 8 < prior low 10
    held = _frame([10, 10, 10, 10, 11, 11, 11, 11], [12] * 8)  # ref recent low 11 >= 10 → held
    confirms = _frame([10, 10, 10, 10, 9, 9, 9, 8], [11] * 8)  # ref also lower low → no divergence
    assert smt_divergence(primary, held, direction=1, lookback=4) is True
    assert smt_divergence(primary, confirms, direction=1, lookback=4) is False


def test_bearish_smt_when_primary_higher_high_reference_holds():
    primary = _frame([9] * 8, [10, 10, 10, 10, 11, 11, 11, 12])   # recent high 12 > prior high 10
    held = _frame([8] * 8, [10, 10, 10, 10, 9, 9, 9, 9])          # ref recent high 9 <= 10 → held
    assert smt_divergence(primary, held, direction=-1, lookback=4) is True
    assert smt_divergence(primary, primary, direction=-1, lookback=4) is False  # self confirms


def test_smt_empty_or_short_is_false():
    assert smt_divergence(pd.DataFrame(), _frame([1] * 8, [2] * 8), 1, 4) is False
    assert smt_divergence(_frame([1] * 4, [2] * 4), _frame([1] * 4, [2] * 4), 1, 4) is False  # too short


def test_engine_ctx_ref_is_causal():
    idx = pd.date_range("2024-03-12 09:30", periods=8, freq="5min", tz=NY)
    bars = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1.0}, index=idx)
    ref = bars.copy()
    seen: list[tuple] = []

    class Peek(BaseStrategy):
        required_timeframes = [TimeFrame.M5]

        def on_bar(self, ctx: MarketContext):
            rb = ctx.ref(TimeFrame.M5)
            if len(rb):
                seen.append((ctx.now, rb.index[-1]))
            return None

    eng = BacktestEngine(cost_model("US", "equity"),
                         InstrumentSpec("X", Market("US", AssetClass.EQUITY, Product.INTRADAY)))
    eng.run(Peek(), bars, TimeFrame.M5, reference_bars=ref)

    assert seen, "reference bars should be visible via ctx.ref"
    # causal: every visible reference bar closed at/before now (its open + 5m <= now).
    for now, ref_last_open in seen:
        assert ref_last_open + pd.Timedelta(minutes=5) <= now


def test_no_reference_returns_empty():
    idx = pd.date_range("2024-03-12 09:30", periods=4, freq="5min", tz=NY)
    bars = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1.0}, index=idx)
    got = {}

    class Peek(BaseStrategy):
        required_timeframes = [TimeFrame.M5]

        def on_bar(self, ctx):
            got["empty"] = ctx.ref(TimeFrame.M5).empty
            return None

    eng = BacktestEngine(cost_model("US", "equity"),
                         InstrumentSpec("X", Market("US", AssetClass.EQUITY, Product.INTRADAY)))
    eng.run(Peek(), bars, TimeFrame.M5)   # no reference_bars
    assert got["empty"] is True
