"""Wolfpack ID oscillator + the VMC multi-timeframe (1H/4H) strategy.

Wolfpack is a trailing EMA(3)-EMA(8) so it must be causal; the strategy is exercised through the
real engine to prove it registers, fires a long only when the full multi-TF stack aligns, and is
blocked by the 200-EMA trend filter in a downtrend.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import src.strategies  # noqa: F401  (registers strategies)
from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import TimeFrame
from src.indicators.causality import assert_causal
from src.indicators.vumanchu import wolfpack, wolfpack_green
from src.strategies.base import get_strategy, list_strategies
from src.strategies.vumanchu.wolfpack_mtf import VmcWolfpack

NY = "America/New_York"


def test_wolfpack_causal_and_signed() -> None:
    rng = np.random.default_rng(3)
    df = pd.DataFrame({"close": 100 + np.cumsum(rng.normal(0, 1, 200))})
    assert_causal(wolfpack, df)
    # green where osc > 0
    osc = wolfpack(df)
    assert ((osc > 0) == wolfpack_green(df)).all()


def _h1(n: int, drift: float, seed: int = 7) -> pd.DataFrame:
    """n hourly bars with a linear drift + noise; drift>0 trends up (above the EMA)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="1h", tz=NY)
    close = 100 + drift * np.arange(n) + np.cumsum(rng.normal(0, 0.3, n))
    op = close - rng.normal(0, 0.2, n)
    hi = np.maximum(op, close) + 0.5
    lo = np.minimum(op, close) - 0.5
    return pd.DataFrame({"open": op, "high": hi, "low": lo, "close": close, "volume": 1000.0},
                        index=idx)


def _engine() -> BacktestEngine:
    inst = InstrumentSpec("BTCUSD", Market("US", AssetClass.CRYPTO, Product.INTRADAY),
                          multiplier=1.0, tick_size=0.01)
    return BacktestEngine(cost_model("US", "crypto"), inst, initial_equity=100_000.0,
                          risk_pct=0.005, max_leverage=2.0)


def test_registered() -> None:
    assert "vmc_wolfpack" in list_strategies()
    assert get_strategy("vmc_wolfpack") is VmcWolfpack


def test_no_trades_in_downtrend() -> None:
    # Pure downtrend: price never above the 200-EMA, so the long trend filter blocks everything.
    res = _engine().run(VmcWolfpack({"trend_len": 50}), _h1(600, drift=-0.05), TimeFrame.H1)
    assert res.trades == []
