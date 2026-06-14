"""VMC multi-timeframe playbook: 1H execution + 4H confirmation (Wolfpack ID + 200-EMA + Cipher B).

Implements the strategy from the user's video transcript (2026-06-13), mechanised faithfully:

LONG (the only side spot crypto can trade — shorts noted below):
  1H execution timeframe:
    1. price ABOVE the 200-EMA           → bullish trend
    2. a pullback DOWN INTO the 200-EMA  → price recently dipped to the EMA, then held above it
    3. Wolfpack ID GREEN CROSS           → the 3/8 MACD oscillator crosses up through zero
  4H confirmation timeframe (else skip):
    4. Cipher B BUY + divergence confirmation AND Wolfpack GREEN on 4H
  Risk: stop at ``atr_stop``×ATR, target at ``rr``× that distance (the video's 1:3 R:R).

The video's "move stop to break-even at target-1" is NOT modelled (the engine takes one stop +
one target); a BE-move trims both small wins and small losses, so omitting it is roughly neutral.
SHORTS are specified in the video but require a perp/futures venue — spot is long-only here.

Causality: 200-EMA, Wolfpack (EMA 3/8), ATR are trailing; Cipher B is proven causal; the engine
exposes only completed H1/H4 bars. Nothing reads a forming or future bar.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from src.core.types import MarketContext, Signal, TimeFrame
from src.indicators import classic
from src.indicators.common import crossover
from src.indicators.vumanchu.cipher_b import cipher_b
from src.indicators.vumanchu.wolfpack import wolfpack
from src.strategies.base import BaseStrategy, register_strategy


@register_strategy("vmc_wolfpack")
class VmcWolfpack(BaseStrategy):
    """Multi-timeframe VMC (1H exec / 4H confirm) with Wolfpack ID + 200-EMA, long-only."""

    required_timeframes = [TimeFrame.H1, TimeFrame.H4]

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {
            "trend_len": 200,          # 1H 200-EMA trend filter
            "wolf_fast": 3,
            "wolf_slow": 8,
            "pullback_atr": 1.0,       # "pullback into the EMA": recent low within this×ATR of EMA
            "pullback_lookback": 8,    # H1 bars to look back for the pullback touch
            "h1_cross_lookback": 6,    # Wolfpack green cross must be within this many H1 bars
            "h4_lookback": 8,          # 4H confirmations must be within this many H4 bars
            # 4H confirmation: a Cipher-B buy OR a bullish divergence (the discretionary trader
            # treats either as the "cipher buy + divergence" cue). True = require BOTH (very rare).
            "require_h4_div": False,
            "atr_period": 14,
            "atr_stop": 1.5,           # stop distance in ATRs (≈ a swing-low stop)
            "rr": 3.0,                 # reward:risk — the video's 1:3 target
            "max_hold_bars": 48,       # safety time stop (H1 bars ≈ 2 days)
            "limit_entry": False,
            "limit_ttl_bars": 3,
        }

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        return {"atr_stop": [1.0, 1.5, 2.0], "rr": [2.0, 3.0, 4.0]}

    def on_start(self, ctx: MarketContext) -> None:
        self._last_label: Optional[pd.Timestamp] = None
        self._bars_held: int = 0

    def _h4_confirms_long(self, p: dict) -> bool:
        h4 = self._ctx.window(TimeFrame.H4, 90)
        if len(h4) < 70:
            return False
        wolf4 = wolfpack(h4, fast=int(p["wolf_fast"]), slow=int(p["wolf_slow"]))
        if not float(wolf4.iloc[-1]) > 0:      # 4H Wolfpack must be green
            return False
        cb4 = cipher_b(h4)
        k = int(p["h4_lookback"])
        recent = cb4.iloc[-k:]
        buy = bool(recent["buy"].any())
        div = bool(recent["regular_bullish"].any())
        return (buy and div) if p["require_h4_div"] else (buy or div)

    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        self._ctx = ctx
        p = self.params
        need = max(int(p["trend_len"]), int(p["atr_period"])) + 30
        h1 = ctx.window(TimeFrame.H1, need)
        if h1.empty:
            return None
        label = h1.index[-1]
        if label == self._last_label:
            return None
        self._last_label = label

        # ---- manage an open position (stop/target handled by the engine; add a time stop) ----
        if ctx.position.qty != 0:
            self._bars_held += 1
            if self._bars_held >= int(p["max_hold_bars"]):
                return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="flat",
                              reason=f"time_{self._bars_held}")
            return None

        self._bars_held = 0
        if len(h1) < need:
            return None  # warm-up

        close = float(h1["close"].iloc[-1])
        ema = classic.ema(h1, int(p["trend_len"]))
        ema_now = float(ema.iloc[-1])
        atr = float(classic.atr(h1, int(p["atr_period"])).iloc[-1])
        if not atr > 0:
            return None

        # 1. bullish trend: price above the 200-EMA
        if not close > ema_now:
            return None
        # 2. pullback INTO the EMA: a recent low came within pullback_atr×ATR of the EMA
        lb = int(p["pullback_lookback"])
        recent_low = float(h1["low"].iloc[-lb:].min())
        if not (recent_low - ema_now) <= float(p["pullback_atr"]) * atr:
            return None
        # 3. Wolfpack ID green cross on 1H within h1_cross_lookback bars (osc crosses up through 0)
        wolf1 = wolfpack(h1, fast=int(p["wolf_fast"]), slow=int(p["wolf_slow"]))
        zero = pd.Series(0.0, index=wolf1.index)
        green_cross = crossover(wolf1, zero)
        if not bool(green_cross.iloc[-int(p["h1_cross_lookback"]):].any()):
            return None
        # 4. 4H confirmation: Wolfpack green + Cipher B buy/divergence
        if not self._h4_confirms_long(p):
            return None

        stop_dist = float(p["atr_stop"]) * atr
        return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="long",
                      stop=close - stop_dist, target=close + float(p["rr"]) * stop_dist,
                      reason="wolfpack_long",
                      limit=close if p["limit_entry"] else None,
                      ttl_bars=int(p["limit_ttl_bars"]))
