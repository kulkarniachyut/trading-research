"""Phase B.5 — the multi-symbol portfolio runner aggregates per-symbol backtests correctly,
isolates strategy state across symbols, and survives a bad symbol without aborting the sweep.
"""

from __future__ import annotations

import pandas as pd

from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import MarketContext, Signal, TimeFrame
from src.strategies.base import BaseStrategy

NY = "America/New_York"


def _bars(rows, date="2024-03-12"):
    idx = pd.date_range(f"{date} 09:30", periods=len(rows), freq="5min", tz=NY)
    o, h, low, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": low, "close": c, "volume": 1000.0}, index=idx)


class _Provider:
    """Returns a long-trade-then-target series for A, a stop-out for B, raises for C."""

    def __init__(self):
        self.calls: list[str] = []

    def get_bars(self, symbol, timeframe, start, end):
        self.calls.append(symbol)
        if symbol == "C":
            raise RuntimeError("boom")
        if symbol == "A":   # rises into target
            return _bars([(100, 100.5, 99.5, 100), (100, 100.8, 100, 100.5),
                          (101, 101.5, 100.5, 101), (101.5, 103, 101, 102.5), (102, 102.5, 101.8, 102)])
        return _bars([(100, 100.5, 99.5, 100), (100, 100.2, 99.8, 100),     # B: falls into stop
                      (99.8, 99.9, 98, 98.5), (98.5, 98.8, 97.5, 98), (98, 98.2, 97.8, 98)])


class BuyOnce(BaseStrategy):
    required_timeframes = [TimeFrame.M5]

    def __init__(self):
        super().__init__()
        self._fired = False

    def on_bar(self, ctx: MarketContext):
        if not self._fired and ctx.position.side == "flat":
            self._fired = True
            return Signal(ctx.now, ctx.position.symbol, "long", stop=ctx.price - 2, target=ctx.price + 2)
        return None


def test_portfolio_aggregates_and_isolates_and_survives_errors():
    universe = [UniverseItem("A"), UniverseItem("B"), UniverseItem("C")]
    res = run_portfolio(BuyOnce, universe, "2024-03-11", "2024-03-18",
                        provider=_Provider(), initial_equity=100_000.0, risk_pct=0.005)

    # A and B each produced one trade; C failed and was skipped (not fatal).
    assert set(res.results) == {"A", "B"}
    assert res.errors["C"].startswith("RuntimeError")
    assert res.trade_count == 2

    a, b = res.results["A"].trades[0], res.results["B"].trades[0]
    assert a.reason_out == "target" and a.net_pnl > 0
    assert b.reason_out == "stop" and b.net_pnl < 0

    # per-symbol isolation: a fresh BuyOnce fired on BOTH symbols (state didn't carry over).
    assert {sym for sym, _ in res.tagged_trades} == {"A", "B"}
    # aggregate stats
    assert res.win_rate == 50.0
    assert res.trades_per_week > 0
    assert res.per_symbol()[0][0] == "A"          # best net first


def test_empty_bars_recorded_as_error_not_crash():
    class Empty:
        def get_bars(self, *a, **k):
            return pd.DataFrame()

    res = run_portfolio(BuyOnce, [UniverseItem("X")], "2024-01-01", "2024-02-01", provider=Empty())
    assert res.trade_count == 0
    assert res.errors["X"] == "no bars"
