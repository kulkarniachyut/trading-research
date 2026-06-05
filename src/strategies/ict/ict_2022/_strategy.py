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
from src.strategies.ict.ict_2022._smt import smt_divergence


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
            # Phase B: edge-pocket diagnostics (scripts/diag_edge_pockets.py) showed gross edge is
            # concentrated in trades that *enter* in the **Silver Bullet hour (10–11 ET)** (+0.22R)
            # while the broad killzone is noise. The setup may *form* earlier in the AM, so the
            # formation window (`killzones`) is broad and only the *entry* is gated to the Silver
            # Bullet via `entry_killzones`. (Gating the whole machine to 10–11 over-restricts —
            # the sweep/MSS can't form in time — which is why a single window starves it.)
            "killzones": [("09:30", "11:00")],
            "entry_killzones": [("10:00", "11:00")],   # trigger only here; None = same as killzones
            # Daily bias gating did NOT help (aligned trades were gross-negative); leave off.
            "require_daily_bias": False,
            "require_daily_pd_alignment": False,
            "require_inducement": False,
            "require_smt": False,          # Phase C: confirm the sweep with SMT divergence vs a correlated ref
            "smt_lookback": 12,
            "entry_require_fvg": False,    # OTE entry by default; FVG overlap = optional confluence
            "entry_confirm": False,        # require a confirmation close in-trade-direction (no knife-catch)
            "use_ifvg_confluence": False,
            "use_breaker_confluence": False,
            "daily_length": 5,
            "sweep_length": 5,
            "sweep_lookback": 3,
            "mss_length": 3,               # MSS is a *micro* structure break, not a major swing
            "displacement_atr_period": 14,
            # A real displacement is a *clearly* above-average impulse; 1.2 ATR admits noise. 1.5
            # is theory-led (authentic institutional move) and roughly halves the bleed in testing
            # — though no displacement threshold produces robust post-cost edge on its own.
            "displacement_atr_mult": 1.5,
            # Phase B: the displacement *leg* must be a real impulse — leg span ≥ N×ATR. The disp3+
            # bucket carried the gross edge (+0.12R) while weaker legs bled. Floor on leg/ATR.
            "min_disp_strength": 2.5,
            "displacement_lookback": 4,
            "max_setup_bars": 20,
            "target_length": 5,
            "rr_fallback": 2.0,
            "target_rr": None,             # if set, cap/force the target at this RR (exit mgmt test)
            "min_rr": 1.0,                 # ignore liquidity draws closer than 1R; use RR fallback
            "stop_buffer_atr": 0.25,
            "m5_window": 250,              # only the recent structure matters -> keeps it O(n)
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            "sweep_length": [3, 5, 8],
            "mss_length": [2, 3, 5],
            "displacement_atr_mult": [1.5, 1.8, 2.0],
            "min_disp_strength": [0.0, 2.0, 2.5, 3.0],
            "rr_fallback": [1.5, 2.0, 3.0],
            "target_rr": [None, 1.0, 1.5, 2.0],
            "stop_buffer_atr": [0.0, 0.25, 0.5],
            "killzones": [[("10:00", "11:00")], [("09:50", "11:00")],
                          [("09:30", "11:30"), ("13:30", "15:30")]],
            "entry_confirm": [False, True],
            "require_smt": [False, True],
        }

    def on_start(self, ctx: MarketContext) -> None:
        self._step = 0
        self._reset()

    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        # monotonic bar counter — survives windowing (len(m5) is capped, so setup ages
        # must be measured against an absolute clock, not the window length).
        self._step = getattr(self, "_step", 0) + 1

        if ctx.position.side != "flat":
            self._state = "in_trade"
            return None
        if getattr(self, "_state", "idle") == "in_trade":
            self._reset()

        if not in_killzone(ctx.now, self.params["killzones"]):
            return None

        m5 = ctx.window(TimeFrame.M5, self.params["m5_window"])
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
        if self.params["require_smt"] and not smt_divergence(
            m5, ctx.ref(TimeFrame.M5), direction, lookback=self.params["smt_lookback"]
        ):
            return
        self._setup = _Setup(direction=direction, sweep=sweep, swept_at=self._step)
        self._state = "swept"

    def _try_confirm_mss(self, m5: pd.DataFrame) -> None:
        setup = self._setup
        if setup is None:
            self._reset()
            return
        if self._expired():
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
        if not self._disp_strong_enough(m5, disp):
            return
        setup.displacement = disp
        self._state = "armed"

    def _disp_strong_enough(self, m5: pd.DataFrame, disp: Displacement) -> bool:
        """Require the displacement leg to span at least ``min_disp_strength`` × ATR — a genuine
        impulse, not a drift. (Phase B: the strong-displacement bucket carried the gross edge.)"""
        floor = self.params["min_disp_strength"]
        if not floor:
            return True
        atr = classic.atr(m5, self.params["displacement_atr_period"]).iloc[-1]
        if not pd.notna(atr) or atr <= 0:
            return True
        return abs(disp.leg_high - disp.leg_low) / float(atr) >= floor

    def _try_entry(self, ctx: MarketContext, m5: pd.DataFrame) -> Optional[Signal]:
        setup = self._setup
        if setup is None or setup.displacement is None:
            self._reset()
            return None
        if self._expired():
            self._reset()
            return None

        # trigger only inside the (narrow) entry window; stay armed and wait otherwise.
        ekz = self.params["entry_killzones"]
        if ekz and not in_killzone(ctx.now, ekz):
            return None

        direction = setup.direction
        price = ctx.price
        if not self._price_in_entry_model(price, setup.displacement, direction):
            return None
        if self.params["entry_confirm"] and not self._entry_confirmed(m5, direction):
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
        d1 = ctx.window(TimeFrame.D1, self.params["daily_length"] * 2 + 20)
        if len(d1) < max(3, self.params["daily_length"] + 2):
            return True  # not enough HTF history to form an opinion -> don't veto
        bias = daily_bias_context(d1, length=self.params["daily_length"], price=ctx.price)
        # A bias filter *vetoes* clearly counter-trend trades; a neutral (0) bias has no opinion
        # and must not block (requiring active confirmation starves the strategy — see diagnostics).
        if bias.direction != 0 and bias.direction != direction:
            return False
        if not self.params["require_daily_pd_alignment"] or bias.direction == 0:
            return True
        return (direction == 1 and bias.zone == "discount") or (
            direction == -1 and bias.zone == "premium"
        )

    def _price_in_entry_model(self, price: float, disp: Displacement, direction: int) -> bool:
        # OTE (62–79% retrace of the displacement leg) is the structural entry. FVG overlap is
        # confluence: required only when entry_require_fvg is set, otherwise it just narrows it.
        if direction == 1:
            ote_low, ote_high = ote_zone(disp.leg_low, disp.leg_high)
        else:
            ote_low, ote_high = ote_zone(disp.leg_high, disp.leg_low)
        if not (ote_low <= price <= ote_high):
            return False
        if self.params["entry_require_fvg"]:
            fvg_low = min(disp.fvg_top, disp.fvg_bottom)
            fvg_high = max(disp.fvg_top, disp.fvg_bottom)
            return fvg_low <= price <= fvg_high
        return True

    def _entry_confirmed(self, m5: pd.DataFrame, direction: int) -> bool:
        """Reject first-touch knife-catching: the latest completed bar must close in the trade
        direction and in the favorable half of its range (a rejection of the OTE tap)."""
        bar = m5.iloc[-1]
        rng = bar["high"] - bar["low"]
        if rng <= 0:
            return False
        close_pos = (bar["close"] - bar["low"]) / rng  # 0 at low … 1 at high
        if direction == 1:
            return bar["close"] > bar["open"] and close_pos >= 0.5
        return bar["close"] < bar["open"] and close_pos <= 0.5

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
        risk = abs(price - stop)
        # a fixed RR target overrides liquidity logic — used to test exit management, since price
        # reaches ~1R far more often than the ~2.3R a liquidity draw implies (see MFE diagnostics).
        cap = self.params.get("target_rr")
        if cap:
            level = price + direction * cap * risk
        target = draw_on_liquidity(m5, direction, price, length=self.params["target_length"])
        # take the real liquidity draw only if it pays at least min_rr; a too-close pool would
        # book a sub-1R winner that costs eat — fall back to a clean RR target instead.
        if target is not None and risk > 0:
            rr = (target - price) / risk if direction == 1 else (price - target) / risk
            if rr >= self.params["min_rr"]:
                level_liq = target
                if cap:  # cap the draw at target_rr so we don't over-reach
                    level_liq = (min(level, target) if direction == 1 else max(level, target))
                return level_liq
        return level if cap else price + direction * self.params["rr_fallback"] * risk

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

    def _expired(self) -> bool:
        return (
            self._setup is not None
            and self._step - self._setup.swept_at > self.params["max_setup_bars"]
        )

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
