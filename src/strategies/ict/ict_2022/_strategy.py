"""State-machine implementation of the flagship ICT 2022 model.

The **trigger engine** is unchanged from v1: ``sweep → MSS/displacement → OTE/FVG retrace entry``.
The redesign (post-68-deck read-through) wraps that trigger in the **narrative layers** the model
requires — the pieces whose absence left v1 at breakeven (see ``research/ICT_2022_MENTAL_MAP.html``):

  • TIME  (``_time``)  — a **macro-time gate** on entries (00:00/08:30/09:30/10:00/13:30) and a
    **premium/discount read vs the daily anchor**. ICT's thesis is TIME × PRICE; v1 had only price.
  • BIAS  (``_bias``)  — **Daily Rebalance Theory**: bias = the *draw on liquidity* (last-3-day FVG /
    PDH-PDL / purge-&-revert), not a persistent break of structure. Trade only *with* the draw.
  • REGIME (``_bias``/Phase-D) — stand aside on **consolidation days** (post-outside-day) and at lunch;
    cap trades/day. News stays a *catalyst* (Phase-D showed filtering on it hurt).
  • CONFLUENCE (``_smt``/``_pd_arrays``) — timed, biased **SMT**; the **FVG-in-the-right-half-of-the-
    displacement-leg** quality filter; IFVG/breaker confluence.

Every layer is an **independent toggle**. The defaults encode the *full* ICT setup (so Phase E
validates the model as ICT teaches it, not a curve-fit subset); each gate can be turned off to ablate
its contribution on the reserved 2025/26 holdout. Single-symbol per instance (the engine traded
symbol); breadth/SMT come from the portfolio runner + ``ctx.ref``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.core.types import MarketContext, Signal, TimeFrame
from src.indicators import classic
from src.strategies.base import BaseStrategy, register_strategy
from src.strategies.common import NY_TZ, in_killzone
from src.strategies.ict.ict_2022._bias import DailyDraw, daily_rebalance, is_consolidation_day
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
from src.strategies.ict.ict_2022._time import (
    DEFAULT_MACRO_WINDOWS,
    anchor_allows,
    at_macro_time,
    session_anchor,
)

# NY lunch — no new setups (Ep5). Kept as a constant so the gate reads clearly.
_LUNCH = [("12:00", "13:00")]


@dataclass(slots=True)
class _Setup:
    direction: int
    sweep: Sweep
    swept_at: int
    swept_ts: object = None          # ctx.now at the sweep (the manipulation's macro-time stamp)
    daily_draw: Optional[DailyDraw] = None
    displacement: Optional[Displacement] = None


@register_strategy("ict_2022")
class Ict2022(BaseStrategy):
    """Daily-narrative-gated liquidity sweep → MSS/displacement → OTE/FVG entry."""

    required_timeframes = [TimeFrame.M5, TimeFrame.M15, TimeFrame.H1, TimeFrame.D1]

    @classmethod
    def default_params(cls) -> dict:
        return {
            # --- formation / entry timing ----------------------------------
            # `killzones` = broad *formation* window (the sweep/MSS may build across the AM/PM).
            # Entry *timing* is gated separately: by `macro_windows` when `macro_time_gate` is on
            # (ICT's TIME×PRICE — entries only at the macro times), else by `entry_killzones`.
            "killzones": [("09:30", "11:30"), ("13:30", "15:30")],
            "entry_killzones": None,                 # used only when macro_time_gate is False
            "macro_time_gate": True,                 # Tier 1: gate entries to the macro windows
            "macro_windows": DEFAULT_MACRO_WINDOWS,
            # --- Tier 1: narrative gates -----------------------------------
            "require_rebalance_bias": True,          # trade only with the Daily Rebalance draw
            # Anchor premium/discount is a *narrative conviction* read (the "heavy discount" A+ zone),
            # NOT a hard veto: ICT's super-bullish days trade above the anchor (Ep19/Ep22), and the OTE
            # entry already enforces discount/premium *of the displacement leg*. So this defaults OFF
            # (a faithful default) and stays an opt-in Phase-E ablation toggle.
            "require_anchor_pd": False,              # buys in discount / sells in premium of the anchor
            "target_rebalance_draw": True,           # consider the daily draw as a target candidate
            "rebalance_lookback": 3,                 # the "last 3 days" of Daily Rebalance Theory
            # --- Tier 2: regime / session discipline -----------------------
            "skip_consolidation_day": True,          # stand aside the day after an outside day (Ep32)
            "no_trade_lunch": True,                  # no new setups 12:00–13:00 (Ep5)
            "max_trades_per_day": 4,                 # ICT's ~4/day (2 AM, 2 PM); 0/None = unlimited
            # --- Tier 3: confluence ----------------------------------------
            "require_fvg_in_disp_half": True,        # FVG must sit in the favorable half of the leg (Ep29)
            "require_smt": False,                    # timed, biased SMT vs ctx.ref (needs a reference)
            "smt_lookback": 12,
            "use_ifvg_confluence": False,
            "use_breaker_confluence": False,
            # --- legacy bias toggle (superseded by require_rebalance_bias) --
            "require_daily_bias": False,             # persistent-BOS bias (the old, weaker read)
            "require_daily_pd_alignment": False,
            "require_inducement": False,
            # --- Phase-D macro filters (catalyst, not filter → default off) -
            "block_risk_off": False,
            "block_news_day": False,
            # --- entry model ----------------------------------------------
            "entry_require_fvg": False,              # OTE entry by default; FVG overlap = confluence
            "entry_confirm": False,                  # require an in-direction confirmation close
            # --- side selection (exp-014): stock shorts are drift-doomed (87% stop-out). Long-bias on
            #     drifting instruments, two-sided on futures/FX. Default both → no behaviour change.
            "long_only": False,                      # take only sellside-sweep → long setups
            "short_only": False,                     # take only buyside-sweep → short setups
            # --- trigger tuning (theory-led; not fit to the test set) ------
            "daily_length": 5,
            "sweep_length": 5,
            "sweep_lookback": 3,
            "mss_length": 3,
            "displacement_atr_period": 14,
            "displacement_atr_mult": 1.5,
            "min_disp_strength": 2.5,
            "displacement_lookback": 4,
            "max_setup_bars": 20,
            "target_length": 5,
            "rr_fallback": 2.0,
            "target_rr": None,
            "min_rr": 1.0,
            "stop_buffer_atr": 0.25,
            "m5_window": 250,
        }

    @classmethod
    def param_space(cls) -> dict:
        return {
            # ablations for Phase E: each narrative gate on/off, plus the trigger knobs.
            "macro_time_gate": [False, True],
            "require_rebalance_bias": [False, True],
            "require_anchor_pd": [False, True],
            "skip_consolidation_day": [False, True],
            "require_fvg_in_disp_half": [False, True],
            "require_smt": [False, True],
            "sweep_length": [3, 5, 8],
            "mss_length": [2, 3, 5],
            "displacement_atr_mult": [1.5, 1.8, 2.0],
            "min_disp_strength": [0.0, 2.0, 2.5, 3.0],
            "rr_fallback": [1.5, 2.0, 3.0],
            "stop_buffer_atr": [0.0, 0.25, 0.5],
        }

    def on_start(self, ctx: MarketContext) -> None:
        self._step = 0
        self._day = None
        self._day_trades = 0
        self._reset()

    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        # monotonic bar counter — survives windowing (len(m5) is capped, so setup ages
        # must be measured against an absolute clock, not the window length).
        self._step = getattr(self, "_step", 0) + 1
        self._roll_day(ctx)

        if ctx.position.side != "flat":
            self._state = "in_trade"
            return None
        if getattr(self, "_state", "idle") == "in_trade":
            self._reset()

        if not in_killzone(ctx.now, self.params["killzones"]):
            return None
        if self.params["no_trade_lunch"] and in_killzone(ctx.now, _LUNCH):
            return None
        if self._day_trade_limit_hit():
            return None

        # Phase-D macro filters (default off — news is a catalyst, not a filter).
        if self.params["block_risk_off"] and ctx.regime() == "risk_off":
            return None
        if self.params["block_news_day"] and ctx.is_news_day():
            return None

        # Tier 2 regime: stand aside on a consolidation day (post-outside-day) for the expansion model.
        if self.params["skip_consolidation_day"] and self._is_consolidation_day(ctx):
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

    # --- per-day bookkeeping ------------------------------------------------

    def _roll_day(self, ctx: MarketContext) -> None:
        day = pd.Timestamp(ctx.now).tz_convert(NY_TZ).normalize()
        if day != getattr(self, "_day", None):
            self._day = day
            self._day_trades = 0

    def _day_trade_limit_hit(self) -> bool:
        cap = self.params["max_trades_per_day"]
        return bool(cap) and self._day_trades >= cap

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

        # Side selection (exp-014): skip the disallowed direction outright.
        if self.params["long_only"] and direction == -1:
            return
        if self.params["short_only"] and direction == 1:
            return

        draw = self._daily_draw(ctx)
        if not self._bias_allows(direction, draw):
            return
        if not self._daily_allows(ctx, direction):       # legacy persistent-BOS gate (default off)
            return
        if self.params["require_inducement"] and not inducement_taken(m5, direction):
            return
        # Timed, biased SMT (Ep35): only meaningful at a macro time and in the bias direction.
        if self.params["require_smt"]:
            if not at_macro_time(ctx.now, self.params["macro_windows"]):
                return
            if not smt_divergence(
                m5, ctx.ref(TimeFrame.M5), direction, lookback=self.params["smt_lookback"]
            ):
                return

        self._setup = _Setup(direction=direction, sweep=sweep, swept_at=self._step, daily_draw=draw)
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
        if not self._fvg_in_displacement_half(disp, setup.direction):
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

    def _fvg_in_displacement_half(self, disp: Displacement, direction: int) -> bool:
        """Ep29 quality filter: the FVG must sit in the **favorable half** of the displacement leg —
        the upper half for longs, the lower half for shorts. (A gap that formed against the leg's
        thrust is low quality.) Off ⇒ always True."""
        if not self.params["require_fvg_in_disp_half"]:
            return True
        span = disp.leg_high - disp.leg_low
        if span <= 0:
            return True
        mid = disp.leg_low + 0.5 * span
        fvg_mid = (disp.fvg_top + disp.fvg_bottom) / 2.0
        return fvg_mid >= mid if direction == 1 else fvg_mid <= mid

    def _try_entry(self, ctx: MarketContext, m5: pd.DataFrame) -> Optional[Signal]:
        setup = self._setup
        if setup is None or setup.displacement is None:
            self._reset()
            return None
        if self._expired():
            self._reset()
            return None
        if not self._entry_time_allows(ctx):
            return None

        direction = setup.direction
        price = ctx.price
        if self.params["require_anchor_pd"] and not anchor_allows(price, session_anchor(m5), direction):
            return None
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
            side = "long"
        else:
            stop = setup.sweep.extreme + buf
            if stop <= price:
                return None
            side = "short"
        target = self._target(m5, setup, direction, price, stop)
        signal = Signal(
            ctx.now,
            ctx.position.symbol,
            side,
            stop=stop,
            target=target,
            reason=f"ict_2022_{side}",
            meta=self._signal_meta(setup),
        )
        self._day_trades += 1
        self._state = "in_trade"
        return signal

    # --- filters / signal pieces ------------------------------------------

    def _entry_time_allows(self, ctx: MarketContext) -> bool:
        """Entry timing gate. With ``macro_time_gate`` (the redesign default) entries fire only in
        the macro windows (TIME×PRICE); otherwise fall back to the ``entry_killzones`` window."""
        if self.params["macro_time_gate"]:
            return at_macro_time(ctx.now, self.params["macro_windows"])
        ekz = self.params["entry_killzones"]
        return in_killzone(ctx.now, ekz) if ekz else True

    def _daily_draw(self, ctx: MarketContext) -> Optional[DailyDraw]:
        d1 = ctx.window(TimeFrame.D1, self.params["daily_length"] * 2 + 20)
        if len(d1) < 4:
            return DailyDraw(0, None, "none")
        return daily_rebalance(d1, ctx.price, lookback=self.params["rebalance_lookback"])

    def _bias_allows(self, direction: int, draw: Optional[DailyDraw]) -> bool:
        """Daily-Rebalance bias gate: trade only *with* the draw. A neutral (0) draw means "no
        confident bias" — stand aside when the gate is required (Ep19's "no bias ⇒ gambling")."""
        if not self.params["require_rebalance_bias"]:
            return True
        if draw is None or draw.direction == 0:
            return False
        return draw.direction == direction

    def _is_consolidation_day(self, ctx: MarketContext) -> bool:
        d1 = ctx.window(TimeFrame.D1, self.params["daily_length"] * 2 + 20)
        return is_consolidation_day(d1)

    def _daily_allows(self, ctx: MarketContext, direction: int) -> bool:
        """Legacy persistent-BOS bias veto (default off; superseded by the Daily Rebalance gate).
        Kept so Phase E can A/B the old read against the new one."""
        if not self.params["require_daily_bias"]:
            return True
        d1 = ctx.window(TimeFrame.D1, self.params["daily_length"] * 2 + 20)
        if len(d1) < max(3, self.params["daily_length"] + 2):
            return True
        bias = daily_bias_context(d1, length=self.params["daily_length"], price=ctx.price)
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

    def _target(self, m5: pd.DataFrame, setup: _Setup, direction: int, price: float, stop: float) -> float:
        """Target the **nearest opposite pool that pays at least ``min_rr``**, choosing between the
        intraday liquidity draw and (when ``target_rebalance_draw``) the Daily-Rebalance draw — so we
        aim at a real level without over-reaching. Falls back to a clean RR target otherwise."""
        risk = abs(price - stop)
        cap = self.params.get("target_rr")
        capped = price + direction * cap * risk if cap else None

        candidates: list[float] = []
        intraday = draw_on_liquidity(m5, direction, price, length=self.params["target_length"])
        if intraday is not None:
            candidates.append(intraday)
        if self.params["target_rebalance_draw"] and setup.daily_draw and setup.daily_draw.draw is not None:
            candidates.append(setup.daily_draw.draw)

        # keep only pools beyond price in the trade direction that clear min_rr
        valid = []
        for lvl in candidates:
            if risk <= 0:
                break
            beyond = lvl > price if direction == 1 else lvl < price
            rr = (lvl - price) / risk if direction == 1 else (price - lvl) / risk
            if beyond and rr >= self.params["min_rr"]:
                valid.append(lvl)
        if valid:
            level = min(valid) if direction == 1 else max(valid)   # nearest qualifying pool
            if capped is not None:  # don't over-reach past the RR cap
                level = min(level, capped) if direction == 1 else max(level, capped)
            return level
        return capped if capped is not None else price + direction * self.params["rr_fallback"] * risk

    def _signal_meta(self, setup: _Setup) -> dict:
        disp = setup.displacement
        draw = setup.daily_draw
        return {
            "model": "ict_2022",
            "state": "armed",
            "direction": setup.direction,
            "sweep_side": setup.sweep.side,
            "sweep_level": setup.sweep.level,
            "sweep_extreme": setup.sweep.extreme,
            "fvg_top": disp.fvg_top if disp else None,
            "fvg_bottom": disp.fvg_bottom if disp else None,
            "draw_basis": draw.basis if draw else None,
            "draw_level": draw.draw if draw else None,
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
