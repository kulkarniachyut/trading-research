"""Engine limit-order entries — the passive-execution path (Step 4 friction work).

Fill rules under test (all conservative): gap-through fills at the open, strict intrabar
trade-through fills at the limit, a mere touch does NOT fill, the order cancels after
``ttl_bars``, and passive fills are costed by the maker model (no spread/slippage) while
exits stay taker.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import Signal, TimeFrame
from src.strategies.base import BaseStrategy

NY = "America/New_York"


class LimitOnce(BaseStrategy):
    """Emits exactly one resting-limit long on the first bar, then goes quiet."""

    name = "limit_once_test"
    required_timeframes = [TimeFrame.M5]

    def on_start(self, ctx) -> None:
        self._sent = False

    def on_bar(self, ctx) -> Optional[Signal]:
        if not self._sent:
            self._sent = True
            return Signal(timestamp=ctx.now, symbol="TEST", side=self.params["side"],
                          stop=self.params["stop"], limit=self.params["limit"],
                          ttl_bars=self.params.get("ttl", 3))
        return None


def _bars(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    idx = pd.date_range("2022-03-08 09:30", periods=len(rows), freq="5min", tz=NY)
    o, h, low, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": low, "close": c, "volume": 1e3}, index=idx)


def _run(rows, side="long", limit=99.0, stop=90.0, ttl=3, maker=True):
    inst = InstrumentSpec("TEST", Market("US", AssetClass.FUTURE, Product.FUTURES),
                          multiplier=5.0, tick_size=0.25)
    eng = BacktestEngine(
        cost_model("US", "future"), inst, initial_equity=100_000.0, max_leverage=10.0,
        maker_cost_model=cost_model("US", "future", half_spread_ticks=0.0,
                                    slippage_atr_mult=0.0) if maker else None,
    )
    strat = LimitOnce({"side": side, "limit": limit, "stop": stop, "ttl": ttl})
    return eng.run(strat, _bars(rows), TimeFrame.M5)


def test_trade_through_fills_at_limit() -> None:
    rows = [(100, 100.5, 99.8, 100.2),   # signal bar
            (100.1, 100.3, 98.7, 99.5),  # low 98.7 < 99 -> fills AT 99
            (99.5, 99.9, 99.2, 99.6)] + [(99.6, 99.9, 99.3, 99.5)] * 3
    res = _run(rows)
    assert len(res.trades) == 1
    assert res.trades[0].entry_px == 99.0  # maker: fill price IS the limit (no spread)


def test_gap_through_fills_at_better_open() -> None:
    rows = [(100, 100.5, 99.8, 100.2),
            (98.5, 99.2, 98.2, 99.0)] + [(99.0, 99.4, 98.8, 99.1)] * 4  # opens below 99
    res = _run(rows)
    assert len(res.trades) == 1
    assert res.trades[0].entry_px == 98.5  # the better gap open, not the limit


def test_touch_does_not_fill_and_ttl_cancels() -> None:
    rows = [(100, 100.5, 99.8, 100.2)] + \
           [(100.0, 100.4, 99.0, 100.1)] * 5  # low == 99 exactly: touch, never through
    res = _run(rows, ttl=3)
    assert res.trades == []


def test_unfilled_expires_after_ttl() -> None:
    rows = [(100, 100.5, 99.8, 100.2)] + \
           [(100.2, 100.6, 99.9, 100.3)] * 2 + \
           [(98.0, 98.5, 97.5, 98.2)] + [(98.2, 98.6, 97.9, 98.3)] * 2  # through, but ttl=2 already expired
    res = _run(rows, ttl=2)
    assert res.trades == []


def test_short_limit_symmetric() -> None:
    rows = [(100, 100.2, 99.8, 100.0),
            (100.1, 101.5, 100.0, 100.8)] + [(100.8, 101.0, 100.4, 100.6)] * 4  # high 101.5 > 101
    res = _run(rows, side="short", limit=101.0, stop=110.0)
    assert len(res.trades) == 1
    assert res.trades[0].side == "short"
    assert res.trades[0].entry_px == 101.0


def test_maker_model_charges_no_spread() -> None:
    rows = [(100, 100.5, 99.8, 100.2),
            (100.1, 100.3, 98.7, 99.5)] + [(99.6, 99.9, 99.3, 99.5)] * 4
    taker = _run(rows, maker=False)   # maker model defaults to the taker model
    maker = _run(rows, maker=True)
    assert len(taker.trades) == len(maker.trades) == 1
    # same fill logic, but the taker-costed entry is worse than the maker-costed one
    assert maker.trades[0].entry_px == 99.0
    assert taker.trades[0].entry_px > 99.0  # spread+slippage pushed the buy fill up
    assert maker.trades[0].net_pnl > taker.trades[0].net_pnl
