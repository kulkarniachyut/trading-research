"""Phase A — US index-futures cost model + contract specs + multiplier P&L.

The point that matters for the ICT-on-futures hypothesis: futures P&L and cost scale by the
contract *point value* (not 1 share), and the per-contract fee is tiny relative to the dollar
move — so cost is a much smaller fraction of R than retail equity 5m. These tests pin the math.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.costs import FillContext, cost_model
from src.backtest.costs.presets.us import us_futures
from src.backtest.instruments import futures_instrument, micro_future
from src.backtest.simulator import BacktestEngine
from src.core.types import MarketContext, Signal, TimeFrame
from src.strategies.base import BaseStrategy

NY = "America/New_York"


# --- contract specs --------------------------------------------------------

def test_micro_specs_point_and_tick_values():
    mnq = micro_future("MNQ")
    assert mnq.multiplier == 2.0 and mnq.tick_size == 0.25
    assert mnq.tick_value == pytest.approx(0.50)        # $2/pt × 0.25
    mes = micro_future("MES")
    assert mes.tick_value == pytest.approx(1.25)        # $5/pt × 0.25
    assert futures_instrument("MNQ").multiplier == 2.0
    with pytest.raises(KeyError):
        micro_future("ZZZ")


# --- futures cost math -----------------------------------------------------

def test_futures_round_turn_cost_is_per_contract_and_small():
    m = us_futures()                                    # 0.5-tick spread, 0.05·ATR slip, $0.37 fee
    inst = futures_instrument("MNQ")                    # mult 2, tick 0.25
    # buy + sell 1 contract at NDX≈20000, ATR 5 pts
    buy = m.apply(FillContext("buy", 1, 20_000.0, inst, atr=5.0))
    sell = m.apply(FillContext("sell", 1, 20_000.0, inst, atr=5.0))
    # spread: 0.5 tick × 0.25 = 0.125 pt × $2 = $0.25/side ; slippage 0.05×5=0.25 pt × $2 = $0.50/side
    assert buy.breakdown["spread"] == pytest.approx(0.25)
    assert buy.breakdown["slippage"] == pytest.approx(0.50)
    assert buy.breakdown["exchange_fee"] == pytest.approx(0.37)
    assert "commission" not in buy.breakdown            # $0 broker commission → dropped
    round_turn = buy.cost + sell.cost
    assert round_turn == pytest.approx(2 * (0.25 + 0.50 + 0.37))   # ~$2.24 per contract round-turn


def test_registry_dispatches_futures():
    assert cost_model("US", "future") is not None
    inst = futures_instrument("MES")
    r = cost_model("US", "future").apply(FillContext("buy", 3, 5_700.0, inst, atr=2.0))
    assert r.breakdown["exchange_fee"] == pytest.approx(3 * 0.37)  # per contract × 3


# --- multiplier flows through backtest P&L ---------------------------------

def _bars(rows, date="2024-03-12"):
    idx = pd.date_range(f"{date} 09:30", periods=len(rows), freq="5min", tz=NY)
    o, h, low, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": low, "close": c, "volume": 1000.0}, index=idx)


class BuyOnce(BaseStrategy):
    required_timeframes = [TimeFrame.M5]

    def __init__(self):
        super().__init__()
        self._fired = False

    def on_bar(self, ctx: MarketContext):
        if not self._fired and ctx.position.side == "flat":
            self._fired = True
            return Signal(ctx.now, "MNQ", "long", stop=ctx.price - 50, target=ctx.price + 100)
        return None


def test_backtest_pnl_scales_by_point_value():
    # entry ~20000, target +100 pts. With MNQ mult $2/pt, a 100-pt move = $200/contract gross.
    data = _bars([
        (20000, 20010, 19990, 20000),
        (20000, 20010, 19990, 20000),   # entry at this open
        (20050, 20120, 20040, 20110),   # target 20100 hit
        (20110, 20120, 20100, 20110),
    ])
    eng = BacktestEngine(
        us_futures(slippage_atr_mult=0.0, half_spread_ticks=0.0),  # isolate gross from costs
        futures_instrument("MNQ"), initial_equity=100_000.0, risk_pct=0.01, max_leverage=50.0,
    )
    res = eng.run(BuyOnce(), data, TimeFrame.M5)
    assert len(res.trades) == 1
    t = res.trades[0]
    # gross = (20100 - 20000) pts × qty × $2/pt  → exactly 200 per contract
    assert t.gross_pnl == pytest.approx(100 * t.qty * 2.0)
    assert t.reason_out == "target"
    assert t.costs == pytest.approx(2 * t.qty * 0.37)  # only the per-contract fee remains
