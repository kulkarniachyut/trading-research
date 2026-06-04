"""Checkpoint 2.6a — the ICT/SMC strategy `ict_fvg`.

A constructed multi-timeframe setup (long bias + a bullish FVG that price retraced into) must yield
a long Signal with a sensible stop/target; the strategy must also register in its bucket and run
through the real engine without error.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import src.strategies  # noqa: F401  (imports buckets -> registers strategies)
from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import Account, MarketContext, Position, TimeFrame
from src.strategies.base import get_strategy, list_strategies
from src.strategies.ict.ict_fvg import IctFvg

NY = "America/New_York"


class FakeCtx(MarketContext):
    """A hand-fed MarketContext: predefined per-TF frames, price, and position."""

    def __init__(self, now, price, frames, position):
        self._now, self._price, self._frames, self._position = now, price, frames, position

    @property
    def now(self):
        return self._now

    def bars(self, tf):
        return self._frames[tf]

    def last(self, tf):
        return self._frames[tf].iloc[-1]

    def window(self, tf, n):
        return self._frames[tf].tail(n)

    @property
    def price(self):
        return self._price

    @property
    def position(self):
        return self._position

    @property
    def account(self):
        return Account(100_000.0, 100_000.0, 100_000.0)


def _bars(rows, freq="15min", start="2024-03-12 09:30"):
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz=NY)
    o, h, low, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": low, "close": c, "volume": 1000.0}, index=idx)


def _rising_h1(n=8, step=1.0):
    rows = [(100 + i * step, 100.3 + i * step, 99.7 + i * step, 100 + i * step) for i in range(n)]
    return _bars(rows, freq="1h", start="2024-03-12 09:00")


def _m15_with_bullish_fvg():
    # bars 5(A)/6(B)/7(C): low[C]=101 > high[A]=100.3 -> bullish FVG ~[100.3, 101]; then retrace in.
    rows = [(100, 100.3, 99.7, 100)] * 6
    rows += [
        (100.5, 103.0, 100.4, 102.8),   # B: displacement up
        (103.0, 104.0, 101.0, 103.5),   # C: gap leaves [100.3, 101]
        (102.0, 102.5, 100.7, 101.0),   # retrace begins
        (101.0, 101.2, 100.5, 100.8),   # current price 100.8 sits inside the gap
    ]
    return _bars(rows)


def test_registered_in_ict_bucket():
    assert "ict_fvg" in list_strategies()
    assert get_strategy("ict_fvg") is IctFvg


def test_emits_long_on_bias_aligned_fvg_retrace():
    frames = {
        TimeFrame.H1: _rising_h1(),
        TimeFrame.M15: _m15_with_bullish_fvg(),
        TimeFrame.M5: _bars([(100.8, 100.9, 100.7, 100.8)] * 5, freq="5min"),  # <15 -> buffer 0
    }
    ctx = FakeCtx(
        now=pd.Timestamp("2024-03-12 14:00", tz=NY),
        price=100.8,
        frames=frames,
        position=Position("SPY", qty=0.0, avg_px=0.0),
    )
    strat = IctFvg({"bias_ema_len": 3, "fvg_lookback": 80, "rr": 2.0, "stop_buffer_atr": 0.0})
    sig = strat.on_bar(ctx)

    assert sig is not None and sig.side == "long"
    assert sig.stop < ctx.price < sig.target
    assert (sig.target - ctx.price) == pytest.approx(2.0 * (ctx.price - sig.stop))
    assert sig.reason == "fvg_long"


def test_no_signal_when_already_in_position():
    frames = {
        TimeFrame.H1: _rising_h1(),
        TimeFrame.M15: _m15_with_bullish_fvg(),
        TimeFrame.M5: _bars([(100.8, 100.9, 100.7, 100.8)] * 5, freq="5min"),
    }
    ctx = FakeCtx(pd.Timestamp("2024-03-12 14:00", tz=NY), 100.8, frames,
                  Position("SPY", qty=100.0, avg_px=100.0))  # already long
    assert IctFvg({"bias_ema_len": 3}).on_bar(ctx) is None


def test_runs_through_engine_without_error():
    # ~3 sessions of synthetic 5m bars; just assert it runs and returns a Result.
    rng = np.random.default_rng(0)
    frames = []
    for d in ("2024-03-11", "2024-03-12", "2024-03-13"):
        idx = pd.date_range(f"{d} 09:30", f"{d} 15:55", freq="5min", tz=NY)
        close = 100 + np.cumsum(rng.normal(0.02, 0.3, len(idx)))
        frames.append(pd.DataFrame({
            "open": close, "high": close + 0.3, "low": close - 0.3, "close": close, "volume": 2000.0,
        }, index=idx))
    base = pd.concat(frames)

    inst = InstrumentSpec("SPY", Market("US", AssetClass.EQUITY, Product.INTRADAY))
    eng = BacktestEngine(cost_model("US", "equity"), inst, risk_pct=0.005)
    res = eng.run(IctFvg({"bias_ema_len": 5, "fvg_lookback": 40}), base, TimeFrame.M5)
    assert res.strategy == "ict_fvg"
    assert len(res.equity_curve) == len(base)
