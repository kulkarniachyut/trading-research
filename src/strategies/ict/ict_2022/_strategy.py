"""State-machine implementation of the flagship ICT 2022 model.

v1 intentionally stays single-symbol because the current engine exposes one traded symbol. SMT,
partial exits, and news/event filters are follow-on stages after this baseline is measurable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.core.types import MarketContext, Signal, TimeFrame
from src.indicators import classic
from src.strategies.base import BaseStrategy, register_strategy
from src.strategies.common import in_killzone
from src.strategies.ict.ict_2022._model import (
    Displacement,
    Sweep,
    daily_bias_context,
    detect_displacement,
    detect_sweep,
    draw_on_liquidity,
    inducement_taken,
    ote_zone,
    structure_shift,
)
from src.strategies.ict.ict_2022._pd_arrays import breaker_level, inverse_fvgs


@dataclass(slots=True)
class _Setup:
    direction: int
    sweep: Sweep
    swept_at: int
    displacement: Optional[Displacement] = None


@register_strategy("ict_2022")
class Ict2022(BaseStrategy):
    """Liquidity sweep -> MSS/displacement -> OTE/FVG retrace entry."""

    required_timeframes = [TimeFrame.M5, TimeFrame.M15, TimeFrame.H1, TimeFrame.D1]

    @classmethod
    def default_params(cls) -> dict:
        return {
            "killzones": [("09:30", "11:30"), ("13:30", "15:30")],
            "require_daily_bias": True,
            "require_daily_pd_alignment": False,
            "require_inducement": False,
            "use_ifvg_confluence": False,
            "use_breaker_confluence": False,
            "daily_length": 5,
            "sweep_length": 5,
            "sweep_lookback": 3,
            "mss_length": 5,
            "displacement_atr_period": 14,
            "displacement_atr_mult": 1.5,
            "displacement_lookback": 4,
            "max_setup_bars": 16,
            "target_length": 5,
            "rr_fallback": 2.0,
            "stop_buffer_atr": 0.25,
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            "sweep_length": [3, 5, 8],
            "mss_length": [3, 5, 8],
            "displacement_atr_mult": [1.0, 1.5, 2.0],
            "rr_fallback": [1.5, 2.0, 3.0],
            "stop_buffer_atr": [0.0, 0.25, 0.5],
        }

    def on_start(self, ctx: MarketContext) -> None:
        self._reset()

    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        if ctx.position.side != "flat":
            self._state = "in_trade"
            return None
        if getattr(self, "_state", "idle") == "in_trade":
            self._reset()

        if not in_killzone(ctx.now, self.params["killzones"]):
            return None

        m5 = ctx.bars(TimeFrame.M5)
        if len(m5) < self._min_bars():
            return None

        if self._state == "idle":
            self._try_detect_sweep(ctx, m5)
        if self._state == "swept":
            self._try_confirm_mss(m5)
        if self._state == "armed":
            return self._try_entry(ctx, m5)
        return None

    # --- state transitions -------------------------------------------------

    def _reset(self) -> None:
        self._state = "idle"
        self._setup: Optional[_Setup] = None

    def _try_detect_sweep(self, ctx: MarketContext, m5: pd.DataFrame) -> None:
        sweep = detect_sweep(
            m5,
            length=self.params["sweep_length"],
            lookback=self.params["sweep_lookback"],
        )
        if sweep is None:
            return
        direction = 1 if sweep.side == "sellside" else -1
        if not self._daily_allows(ctx, direction):
            return
        if self.params["require_inducement"] and not inducement_taken(m5, direction):
            return
        self._setup = _Setup(direction=direction, sweep=sweep, swept_at=len(m5) - 1)
        self._state = "swept"

    def _try_confirm_mss(self, m5: pd.DataFrame) -> None:
        setup = self._setup
        if setup is None:
            self._reset()
            return
        if self._expired(m5):
            self._reset()
            return
        if not structure_shift(m5, setup.direction, length=self.params["mss_length"]):
            return
        disp = detect_displacement(
            m5,
            setup.direction,
            atr_period=self.params["displacement_atr_period"],
            atr_mult=self.params["displacement_atr_mult"],
            lookback=self.params["displacement_lookback"],
        )
        if disp is None:
            return
        setup.displacement = disp
        self._state = "armed"

    def _try_entry(self, ctx: MarketContext, m5: pd.DataFrame) -> Optional[Signal]:
        setup = self._setup
        if setup is None or setup.displacement is None:
            self._reset()
            return None
        if self._expired(m5):
            self._reset()
            return None

        direction = setup.direction
        price = ctx.price
        if not self._price_in_entry_model(price, setup.displacement, direction):
            return None
        if not self._pd_array_confluence(m5, direction, price):
            return None

        buf = self._atr_buffer(ctx, self.params["stop_buffer_atr"])
        if direction == 1:
            stop = setup.sweep.extreme - buf
            if stop >= price:
                return None
            target = self._target(m5, direction, price, stop)
            signal = Signal(
                ctx.now,
                ctx.position.symbol,
                "long",
                stop=stop,
                target=target,
                reason="ict_2022_long",
                meta=self._signal_meta(setup),
            )
        else:
            stop = setup.sweep.extreme + buf
            if stop <= price:
                return None
            target = self._target(m5, direction, price, stop)
            signal = Signal(
                ctx.now,
                ctx.position.symbol,
                "short",
                stop=stop,
                target=target,
                reason="ict_2022_short",
                meta=self._signal_meta(setup),
            )
        self._state = "in_trade"
        return signal

    # --- filters / signal pieces ------------------------------------------

    def _daily_allows(self, ctx: MarketContext, direction: int) -> bool:
        if not self.params["require_daily_bias"]:
            return True
        d1 = ctx.bars(TimeFrame.D1)
        if len(d1) < max(3, self.params["daily_length"] + 2):
            return False
        bias = daily_bias_context(d1, length=self.params["daily_length"], price=ctx.price)
        if bias.direction != direction:
            return False
        if not self.params["require_daily_pd_alignment"]:
            return True
        return (direction == 1 and bias.zone == "discount") or (
            direction == -1 and bias.zone == "premium"
        )

    def _price_in_entry_model(self, price: float, disp: Displacement, direction: int) -> bool:
        fvg_low = min(disp.fvg_top, disp.fvg_bottom)
        fvg_high = max(disp.fvg_top, disp.fvg_bottom)
        if direction == 1:
            ote_low, ote_high = ote_zone(disp.leg_low, disp.leg_high)
        else:
            ote_low, ote_high = ote_zone(disp.leg_high, disp.leg_low)
        return fvg_low <= price <= fvg_high and ote_low <= price <= ote_high

    def _pd_array_confluence(self, m5: pd.DataFrame, direction: int, price: float) -> bool:
        if self.params["use_ifvg_confluence"]:
            zones = [z for z in inverse_fvgs(m5) if z.direction == direction]
            if not any(z.bottom <= price <= z.top for z in zones):
                return False
        if self.params["use_breaker_confluence"]:
            breaker = breaker_level(m5, length=self.params["mss_length"])
            if breaker is None or breaker[0] != direction:
                return False
        return True

    def _target(self, m5: pd.DataFrame, direction: int, price: float, stop: float) -> float:
        target = draw_on_liquidity(m5, direction, price, length=self.params["target_length"])
        if direction == 1 and target is not None and target > price:
            return target
        if direction == -1 and target is not None and target < price:
            return target
        risk = abs(price - stop)
        return price + direction * self.params["rr_fallback"] * risk

    def _signal_meta(self, setup: _Setup) -> dict:
        disp = setup.displacement
        return {
            "model": "ict_2022",
            "state": "armed",
            "direction": setup.direction,
            "sweep_side": setup.sweep.side,
            "sweep_level": setup.sweep.level,
            "sweep_extreme": setup.sweep.extreme,
            "fvg_top": disp.fvg_top if disp else None,
            "fvg_bottom": disp.fvg_bottom if disp else None,
        }

    def _expired(self, m5: pd.DataFrame) -> bool:
        return self._setup is not None and len(m5) - self._setup.swept_at > self.params["max_setup_bars"]

    def _min_bars(self) -> int:
        return max(
            self.params["sweep_length"] * 2 + 3,
            self.params["mss_length"] * 2 + 3,
            self.params["displacement_atr_period"] + 3,
        )

    @staticmethod
    def _atr_buffer(ctx: MarketContext, mult: float) -> float:
        m5 = ctx.window(TimeFrame.M5, 30)
        if len(m5) < 15:
            return 0.0
        atr = classic.atr(m5, 14).iloc[-1]
        return float(atr) * mult if pd.notna(atr) else 0.0
