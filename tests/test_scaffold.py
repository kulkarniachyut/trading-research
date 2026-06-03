"""Step 0 verification: contracts import, TimeFrame ordering works, and the strategy
registry can register / discover / instantiate a plug-in via the public API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.core.types import Account, MarketContext, Position, Signal, TimeFrame
from src.strategies.base import (
    STRATEGY_REGISTRY,
    BaseStrategy,
    get_strategy,
    list_strategies,
    register_strategy,
)


def test_timeframe_ordering_and_helpers():
    assert TimeFrame.M1 < TimeFrame.M5 < TimeFrame.H1 < TimeFrame.D1
    assert TimeFrame.M5.minutes == 5
    assert TimeFrame.M15.pandas_freq == "15min"


def test_signal_contract():
    sig = Signal(timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), symbol="SPY", side="long")
    assert sig.symbol == "SPY"
    assert sig.side == "long"
    assert sig.meta == {}  # default_factory gives a fresh dict


def test_position_side_inference():
    assert Position("SPY", qty=10, avg_px=100).side == "long"
    assert Position("SPY", qty=-10, avg_px=100).side == "short"
    assert Position("SPY", qty=0, avg_px=0).side == "flat"


def test_registry_register_discover_instantiate():
    @register_strategy("dummy_test_strategy")
    class _Dummy(BaseStrategy):
        required_timeframes = [TimeFrame.M5]

        @classmethod
        def default_params(cls):
            return {"threshold": 1.0}

        def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
            return None

    try:
        assert "dummy_test_strategy" in list_strategies()
        cls = get_strategy("dummy_test_strategy")
        assert cls.name == "dummy_test_strategy"

        # params merge: default + override
        inst = cls({"threshold": 2.0})
        assert inst.params["threshold"] == 2.0
        assert inst.on_bar(ctx=None) is None  # ABC implemented, callable
    finally:
        STRATEGY_REGISTRY.pop("dummy_test_strategy", None)


def test_duplicate_registration_rejected():
    @register_strategy("dup_test")
    class _A(BaseStrategy):
        def on_bar(self, ctx): return None

    try:
        try:
            @register_strategy("dup_test")
            class _B(BaseStrategy):
                def on_bar(self, ctx): return None
            assert False, "expected duplicate registration to raise"
        except ValueError:
            pass
    finally:
        STRATEGY_REGISTRY.pop("dup_test", None)


def test_account_contract():
    acct = Account(cash=100_000.0, equity=100_000.0, buying_power=200_000.0)
    assert acct.equity == 100_000.0
