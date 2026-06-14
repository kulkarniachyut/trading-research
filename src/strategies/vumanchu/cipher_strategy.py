"""VuManChu Cipher B — trend-gated long-only entries on intraday crypto (go-wide VMC brick).

Pre-registered in docs/STEP4_EDGE_SEARCH_PLAN.md before any run. The thesis, in one line: the
naked WaveTrend ``buy`` (a *mean-reversion* signal — WT cross-up in the oversold zone) failed on
daily crypto because daily crypto trends rather than reverts; the canonical retail VMC long adds
the two things that align it WITH the trend — a 200-EMA gate (buy dips only inside an uptrend) and
an intraday timeframe (H4/H1) we have never tested on crypto. This strategy is exactly that probe.

Everything it reads is causal: the ``buy``/``sell`` flags are WaveTrend crosses in zones (no
forward lookback), the trend gate is a trailing EMA, money flow is a trailing SMA. The
divergence/``gold_buy`` parts of Cipher B are deliberately NOT used — pivot confirmation needs
future bars (look-ahead), so they have no place in a tradable rule.

Engine fit mirrors IBS: decisions are made once per completed decision-timeframe bar (default H4),
deduped by bar label; the engine — not any shifting — guarantees only closed bars are visible.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from src.core.types import MarketContext, Signal, TimeFrame
from src.indicators import classic
from src.indicators.common import pivots
from src.indicators.common.crosses import crossover, crossunder
from src.indicators.vumanchu.cipher_b import cipher_b, money_flow
from src.indicators.vumanchu.wavetrend import wavetrend
from src.strategies.base import BaseStrategy, register_strategy


@register_strategy("vmc_cipher")
class VmcCipher(BaseStrategy):
    """Long-only trend-gated Cipher B for intraday crypto.

    ENTER long: Cipher B ``buy`` (WT1×WT2 cross with wt2 ≤ oversold) AND close > EMA(trend_len)
    AND money_flow > 0 (green). EXIT: Cipher B ``sell`` (WT cross in overbought) OR ``max_hold_bars``
    time stop OR the ``atr_stop``×ATR disaster stop (handled by the engine via the stop price).
    """

    # Set per-instance from the ``decision_tf`` param in __init__ (the engine reads this attribute
    # on the instance, simulator.py). Defaults cover both H4 (primary) and H1 (secondary read).
    required_timeframes = [TimeFrame.H4]

    def __init__(self, params: Optional[dict[str, Any]] = None) -> None:
        super().__init__(params)
        self._tf = TimeFrame(self.params["decision_tf"])
        self.required_timeframes = [self._tf]

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {
            "decision_tf": "4h",
            # Entry flag from cipher_b: "buy" (WT cross in oversold) or "gold_buy" (the classic
            # "yellow" setup — buy + a causal regular-bullish WT divergence + RSI<30; far rarer,
            # higher selectivity, aimed at the cost problem). Divergence is confirmed `right` bars
            # back, so gold_buy stays causal.
            "entry_signal": "buy",
            # Direction. Long-only by default (spot). Perps unlock the short side: the exact mirror
            # — sell signal (WT cross in overbought) + close < EMA (downtrend) + money_flow < 0 (red)
            # + at RESISTANCE (a confirmed swing high). Shorts target the bear regimes longs sit out.
            "allow_long": True,
            "allow_short": False,
            "trend_len": 200,        # EMA trend gate — only buy dips inside an uptrend
            "oversold": -53.0,       # Cipher B WaveTrend oversold zone (VMC default)
            "overbought": 53.0,
            "require_money_flow": True,  # money_flow > 0 (green) confirmation on entry
            # S/R confluence (the user's "sr"): only buy when price has pulled back to a known
            # SUPPORT level — a recently-confirmed swing low. Causal: pivots confirm `right` bars
            # back. "At support" = close within sr_atr_dist×ATR ABOVE a support in the last
            # sr_lookback bars. Off by default so the base behaviour is unchanged.
            "require_support": False,
            "sr_pivot_lr": 5,        # swing-pivot left/right for support detection
            "sr_lookback": 120,      # how many recent bars of support levels to consider
            "sr_atr_dist": 1.0,      # close must sit within this many ATR of a support level
            "max_hold_bars": 24,     # time stop in decision-TF bars (~4 days on H4)
            "atr_period": 14,
            "atr_stop": 3.0,         # wide disaster stop; the signal/time exit does the work
            # Passive entry: rest a buy limit at the signal bar's close (maker fill) instead of
            # taking the next bar's open. Mirrors the IBS lesson that maker entry is load-bearing
            # under crypto fees. Unfilled-on-no-pullback is part of the measurement.
            "limit_entry": False,
            "limit_ttl_bars": 6,
        }

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        # Ablation only (smooth-vs-spiky check), never curve-fit for a verdict.
        return {"oversold": [-60.0, -53.0, -45.0], "max_hold_bars": [12, 24, 48]}

    def on_start(self, ctx: MarketContext) -> None:
        self._last_label: Optional[pd.Timestamp] = None
        self._bars_held: int = 0

    def _signal_row(self, cb_win: pd.DataFrame) -> Any:
        """Last completed bar's Cipher B values (``buy``/``sell``/``money_flow``/``wt2``).

        Fast path: the base buy/sell signal only needs WaveTrend + money_flow. The full cipher_b
        also computes stochRSI/RSI and divergences (double pivot scans) — expensive per bar and
        only needed for ``gold_buy``. The fast-path values are byte-identical to cipher_b's.
        """
        p = self.params
        if p["entry_signal"] == "gold_buy":
            return cipher_b(cb_win, oversold=float(p["oversold"]),
                            overbought=float(p["overbought"])).iloc[-1]
        wt = wavetrend(cb_win)
        wt1, wt2 = wt["wt1"], wt["wt2"]
        return {
            "buy": bool(crossover(wt1, wt2).iloc[-1] and wt2.iloc[-1] <= float(p["oversold"])),
            "sell": bool(crossunder(wt1, wt2).iloc[-1] and wt2.iloc[-1] >= float(p["overbought"])),
            "money_flow": float(money_flow(cb_win).iloc[-1]),
            "wt2": float(wt2.iloc[-1]),
        }

    def _near_level(self, win: pd.DataFrame, close: float, atr: float, *, support: bool) -> bool:
        """True if price sits within ``sr_atr_dist``×ATR on the trade side of a recent swing level.

        ``support``: price just ABOVE a confirmed swing low (long entry); else just BELOW a
        confirmed swing high (short entry). Pivots confirm ``sr_pivot_lr`` bars back, so causal.
        """
        p = self.params
        lr = int(p["sr_pivot_lr"])
        col, high = ("low", False) if support else ("high", True)
        piv = pivots(win[col], left=lr, right=lr, high=high)["value"]
        levels = piv.iloc[-int(p["sr_lookback"]):].dropna().to_numpy()
        tol = float(p["sr_atr_dist"]) * atr
        return any(0.0 <= (close - lvl if support else lvl - close) <= tol for lvl in levels)

    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        p = self.params
        # cipher_b composes WaveTrend (EMAs ~channel/average len) + money flow (SMA mfi_period=60);
        # the binding warm-up is the trend EMA. Give it generous headroom for stable EMA seeding.
        need = max(int(p["trend_len"]), 60, int(p["atr_period"])) + 50
        win = ctx.window(self._tf, need)
        if win.empty:
            return None
        label = win.index[-1]
        if label == self._last_label:
            return None  # no new completed decision bar
        self._last_label = label

        # cipher_b only needs ~recent bars for a stable last-row value; cap its input window so the
        # per-bar recompute stays cheap on long intraday series (150 ≫ any cipher_b lookback). The
        # EMA200 gate + S/R pivots read the full ``win`` separately.
        cb_win = win.iloc[-150:] if len(win) > 150 else win
        last = self._signal_row(cb_win)

        # ---- manage an open position (side-aware: a long exits on the sell signal, vice versa) ----
        if ctx.position.qty != 0:
            self._bars_held += 1
            is_long = ctx.position.qty > 0
            opposite = bool(last["sell"]) if is_long else bool(last["buy"])
            if opposite or self._bars_held >= int(p["max_hold_bars"]):
                reason = ("vmc_sell" if is_long else "vmc_buy") if opposite else f"time_{self._bars_held}"
                return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="flat",
                              reason=reason)
            return None

        # ---- flat: look for an entry --------------------------------------------------
        self._bars_held = 0
        if len(win) < need:
            return None  # warm-up

        close = float(win["close"].iloc[-1])
        atr = float(classic.atr(win, int(p["atr_period"])).iloc[-1])
        if not atr > 0:
            return None
        trend_len = int(p["trend_len"])
        ema = float(classic.ema(win, trend_len).iloc[-1]) if trend_len > 1 else None
        stop_d = float(p["atr_stop"]) * atr

        # LONG: buy signal + uptrend + green money flow + at support (price just ABOVE a swing low)
        if p["allow_long"] and bool(last[p["entry_signal"]]):
            ok = (ema is None or close > ema)
            if ok and p["require_money_flow"] and not float(last["money_flow"]) > 0:
                ok = False
            if ok and p["require_support"]:
                ok = self._near_level(win, close, atr, support=True)
            if ok:
                return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="long",
                              stop=close - stop_d, reason=f"vmc_buy_wt{last['wt2']:.0f}",
                              limit=close if p["limit_entry"] else None,
                              ttl_bars=int(p["limit_ttl_bars"]))

        # SHORT (mirror): sell signal + downtrend + red money flow + at resistance (just BELOW a swing high)
        if p["allow_short"] and bool(last["sell"]):
            ok = (ema is None or close < ema)
            if ok and p["require_money_flow"] and not float(last["money_flow"]) < 0:
                ok = False
            if ok and p["require_support"]:
                ok = self._near_level(win, close, atr, support=False)
            if ok:
                return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="short",
                              stop=close + stop_d, reason=f"vmc_sell_wt{last['wt2']:.0f}",
                              limit=close if p["limit_entry"] else None,
                              ttl_bars=int(p["limit_ttl_bars"]))
        return None
