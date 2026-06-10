"""TSMOM — time-series momentum on futures, daily decisions (Step 4, family 2).

The classic Moskowitz-Ooi-Pedersen (2012) effect: the sign of an instrument's own k-day return
predicts its next-period return, across asset classes, for ~a century of data. Theory-fixed
defaults (12-month lookback, sign rule); the lookback grid exists to check the edge varies
*smoothly* (a real effect), not to pick a winner.

Engine fit:
- Decisions on **completed D1 bars** (calendar-day rollup of the 23h session), but the strategy
  runs on an intraday base TF (H1 in the runner) so the engine's ATR-scaled slippage is priced on
  intraday ranges, not daily ones, and the disaster stop resolves intrabar. ``on_bar`` acts only
  when a new D1 bar has completed — at most one decision per day.
- The engine requires a stop to size (risk_pct / stop distance): we use a wide ATR *disaster* stop
  (``atr_stop`` × daily ATR). Sizing then scales ∝ 1/ATR — inverse-vol sizing, exactly the MOP
  construction. Position exits when the sign flips ("flat", refreshed next day in the new
  direction) or at the disaster stop; no profit target (trend pays in the tail).
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from src.core.types import MarketContext, Signal, TimeFrame
from src.indicators import classic
from src.strategies.base import BaseStrategy, register_strategy


@register_strategy("tsmom")
class Tsmom(BaseStrategy):
    """Sign-of-k-day-return trend following with inverse-vol sizing via an ATR disaster stop."""

    required_timeframes = [TimeFrame.D1]

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {
            "lookback": 252,    # ~12 months of sessions (the canonical MOP horizon)
            "atr_period": 20,
            "atr_stop": 3.0,    # disaster stop, in daily ATRs — wide on purpose
        }

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        return {"lookback": [63, 126, 252]}  # smooth-variation check, not a tuning menu

    def on_start(self, ctx: MarketContext) -> None:
        self._last_d1: Optional[pd.Timestamp] = None

    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        lookback = int(self.params["lookback"])
        atr_period = int(self.params["atr_period"])
        need = max(lookback, atr_period) + 1

        d1 = ctx.window(TimeFrame.D1, need)
        if d1.empty:
            return None
        label = d1.index[-1]
        if label == self._last_d1:
            return None  # no new completed day yet
        self._last_d1 = label
        if len(d1) < need:
            return None  # warm-up

        closes = d1["close"]
        ret = float(closes.iloc[-1]) / float(closes.iloc[-1 - lookback]) - 1.0
        direction = 1 if ret > 0 else -1 if ret < 0 else 0

        pos = ctx.position.qty
        if pos != 0:
            held = 1 if pos > 0 else -1
            if direction != held:
                return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="flat",
                              reason=f"tsmom_flip_{lookback}d")
            return None  # ride the trend; disaster stop is engine-managed

        if direction == 0:
            return None
        atr_d = float(classic.atr(d1, atr_period).iloc[-1])
        if not atr_d > 0:
            return None
        close = float(closes.iloc[-1])
        side = "long" if direction > 0 else "short"
        stop = close - self.params["atr_stop"] * atr_d * direction
        return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side=side, stop=stop,
                      reason=f"tsmom_{lookback}d")
