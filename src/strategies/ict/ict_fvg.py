"""``ict_fvg`` — ICT/SMC multi-timeframe strategy (the first ICT bucket member).

The setup, in plain terms:
- **Bias (H1):** trend from the H1 EMA — price above a rising EMA = long bias (and vice-versa).
- **Zone (M15):** a recent **fair value gap** (FVG) aligned with the bias, taken from the SMC
  indicators (computed causally on the completed-bar window the engine provides).
- **Entry (M5/now):** price has **retraced back into** that FVG → enter in the bias direction.
- **Stop:** just beyond the far side of the FVG (ATR-buffered). **Target:** ``rr`` × risk.

v1 keeps the entry simple (retrace-into-FVG); a liquidity-sweep precondition is a planned tunable.
All knobs live in ``default_params`` / ``param_space`` so Step-3 walk-forward can optimize them.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from src.core.types import MarketContext, Signal, TimeFrame
from src.indicators import classic, smc
from src.strategies.base import BaseStrategy, register_strategy
from src.strategies.common import in_killzone


@register_strategy("ict_fvg")
class IctFvg(BaseStrategy):
    required_timeframes = [TimeFrame.M5, TimeFrame.M15, TimeFrame.H1]

    @classmethod
    def default_params(cls) -> dict:
        return {
            "bias_ema_len": 50,        # H1 EMA for trend bias
            "fvg_lookback": 80,        # M15 bars scanned for an FVG
            "rr": 2.0,                 # reward:risk
            "stop_buffer_atr": 0.25,   # stop padding beyond the FVG, in M5 ATRs
            "killzones": None,         # e.g. [("09:30", "11:30")] NY; None = all session
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            "bias_ema_len": [20, 50, 100],
            "rr": [1.5, 2.0, 3.0],
            "stop_buffer_atr": [0.0, 0.25, 0.5],
        }

    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        if ctx.position.side != "flat":
            return None
        p = self.params
        if not in_killzone(ctx.now, p["killzones"]):
            return None

        direction = self._bias(ctx, p["bias_ema_len"])
        if direction == 0:
            return None

        m15 = ctx.window(TimeFrame.M15, p["fvg_lookback"])
        if len(m15) < 5:
            return None
        zone = self._entry_zone(smc.fvg(m15), direction, ctx.price)
        if zone is None:
            return None
        top, bottom = zone

        price = ctx.price
        buf = self._atr_buffer(ctx, p["stop_buffer_atr"])
        symbol = ctx.position.symbol
        if direction == 1:
            stop = bottom - buf
            if stop >= price:
                return None
            target = price + p["rr"] * (price - stop)
            return Signal(ctx.now, symbol, "long", stop=stop, target=target, reason="fvg_long")
        stop = top + buf
        if stop <= price:
            return None
        target = price - p["rr"] * (stop - price)
        return Signal(ctx.now, symbol, "short", stop=stop, target=target, reason="fvg_short")

    # --- pieces ------------------------------------------------------------

    @staticmethod
    def _bias(ctx: MarketContext, ema_len: int) -> int:
        """+1 long / -1 short / 0 none, from H1 EMA level + slope."""
        h1 = ctx.window(TimeFrame.H1, ema_len + 5)
        if len(h1) < ema_len + 2:
            return 0
        ema = classic.ema(h1, ema_len)
        if pd.isna(ema.iloc[-1]) or pd.isna(ema.iloc[-2]):
            return 0
        close = h1["close"].iloc[-1]
        if close > ema.iloc[-1] and ema.iloc[-1] >= ema.iloc[-2]:
            return 1
        if close < ema.iloc[-1] and ema.iloc[-1] <= ema.iloc[-2]:
            return -1
        return 0

    @staticmethod
    def _entry_zone(fvg: pd.DataFrame, direction: int, price: float) -> Optional[tuple[float, float]]:
        """Most recent bias-aligned FVG (excluding the just-formed last bar) whose range currently
        contains ``price`` — i.e. price has retraced into it. Returns (top, bottom) or None."""
        formed = fvg.iloc[:-1]
        hits = formed[formed["fvg"] == direction]
        for ts in reversed(hits.index):
            top = max(hits.at[ts, "fvg_top"], hits.at[ts, "fvg_bottom"])
            bottom = min(hits.at[ts, "fvg_top"], hits.at[ts, "fvg_bottom"])
            if bottom <= price <= top:
                return top, bottom
        return None

    @staticmethod
    def _atr_buffer(ctx: MarketContext, mult: float) -> float:
        m5 = ctx.window(TimeFrame.M5, 30)
        if len(m5) < 15:
            return 0.0
        atr = classic.atr(m5, 14).iloc[-1]
        return float(atr) * mult if pd.notna(atr) else 0.0
