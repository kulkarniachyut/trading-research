"""Step 4, family 2 — the TSMOM strategy.

Synthetic H1 sessions with a controlled daily trend must produce: a long once the k-day return
turns positive (after warm-up), at most one decision per completed day, a flip to flat (then
short) when the trend reverses, and a disaster-stop exit on a crash. Runs through the real
engine + futures cost model at H1 base with D1 decisions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import src.strategies  # noqa: F401  (imports buckets -> registers strategies)
from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import TimeFrame
from src.strategies.base import get_strategy, list_strategies
from src.strategies.momentum.tsmom import Tsmom

NY = "America/New_York"

PARAMS = {"lookback": 5, "atr_period": 3, "atr_stop": 3.0}  # tiny windows for fast tests


def _h1_days(start: str, day_closes: list[float], intraday_range: float = 0.5) -> pd.DataFrame:
    """6 H1 bars per 'day' (09:00-15:00 openings), drifting linearly to each day's close."""
    frames = []
    day0 = pd.Timestamp(start, tz=NY).normalize()
    prev = day_closes[0]
    for d, target in enumerate(day_closes):
        idx = pd.date_range(day0 + pd.Timedelta(days=d, hours=9), periods=6, freq="1h", tz=NY)
        path = np.linspace(prev, target, 7)
        o, c = path[:-1], path[1:]
        h = np.maximum(o, c) + intraday_range / 2
        lo = np.minimum(o, c) - intraday_range / 2
        frames.append(pd.DataFrame(
            {"open": o, "high": h, "low": lo, "close": c, "volume": 1000.0}, index=idx))
        prev = target
    return pd.concat(frames)


def _engine() -> BacktestEngine:
    inst = InstrumentSpec("ES.c.0", Market("US", AssetClass.FUTURE, Product.FUTURES),
                          multiplier=5.0, tick_size=0.25)
    return BacktestEngine(cost_model("US", "future"), inst,
                          initial_equity=100_000.0, risk_pct=0.005, max_leverage=10.0)


def _run(bars: pd.DataFrame, params: dict | None = None):
    return _engine().run(Tsmom({**PARAMS, **(params or {})}), bars, TimeFrame.H1)


def test_registered() -> None:
    assert "tsmom" in list_strategies()
    assert get_strategy("tsmom") is Tsmom


def test_long_in_uptrend_then_flat_on_reversal() -> None:
    # 8 up days (warm-up is lookback+1=6 days), a hard 8-day downtrend, then a crash-up day
    # (the engine only records CLOSED trades — the final spike stops the short out).
    closes = [100 + 2 * d for d in range(8)] + [114 - 4 * d for d in range(1, 9)] + [130.0]
    res = _run(_h1_days("2022-03-07", closes))
    sides = [t.side for t in res.trades]
    assert "long" in sides, f"expected a long trade, got {res.trades}"
    first = res.trades[sides.index("long")]
    # exited via flip ("signal") or via the disaster stop on the hard reversal
    assert first.reason_out in ("signal", "stop")
    # and the reversal eventually produces a short
    assert "short" in sides[sides.index("long"):]


def test_one_decision_per_day() -> None:
    closes = [100 + 2 * d for d in range(10)]
    bars = _h1_days("2022-03-07", closes)
    res = _run(bars)
    # a monotone uptrend can only ever produce one entry — never one per H1 bar
    assert len(res.trades) <= 1
    if res.trades:
        assert res.trades[0].side == "long"


def test_warmup_produces_no_trades() -> None:
    closes = [100 + d for d in range(4)]  # fewer days than lookback+1
    res = _run(_h1_days("2022-03-07", closes))
    assert res.trades == []


def test_disaster_stop_on_crash() -> None:
    # steady uptrend, then a single-day crash far beyond 3 ATRs
    closes = [100 + 2 * d for d in range(9)] + [80.0]
    res = _run(_h1_days("2022-03-07", closes))
    assert len(res.trades) >= 1
    assert res.trades[0].side == "long"
    assert res.trades[0].reason_out == "stop"
