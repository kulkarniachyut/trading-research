"""``BacktestEngine`` — the event-driven simulator (the "truth machine").

It replays the base-timeframe bars one at a time and, at each bar:
  1. fills any order queued on the previous bar at THIS bar's open (next-bar-open fills),
  2. manages an open position against this bar's range (stop / target, stop-first if both hit),
  3. marks equity at the close,
  4. builds a look-ahead-safe ``MarketContext`` (completed bars only) and calls ``strategy.on_bar``,
  5. queues the resulting Signal to fill at the next bar's open.

Every fill passes through the cost model (spread + slippage move the fill price; commissions/taxes
are charged separately), so results are net of friction. Trades and the equity curve are collected
into a ``Result``. This is the same ``on_bar`` code path the live paper loop will drive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

from src.backtest.clock import MultiTFClock, _bar_duration
from src.backtest.context import BacktestContext
from src.backtest.costs import CostModel, FillContext, InstrumentSpec
from src.core.types import Account, Position, Result, Signal, TimeFrame, Trade
from src.indicators import classic
from src.strategies.base import BaseStrategy

NY_TZ = "America/New_York"


@dataclass
class _Open:
    """Internal bookkeeping for the single open position."""

    side: str                 # "long" / "short"
    qty: float
    entry_fill: float         # cost-adjusted entry price
    entry_ref: float          # frictionless reference (bar open) for gross pnl
    entry_ts: datetime
    entry_i: int
    entry_cash: float         # cash costs paid on entry
    stop: Optional[float]
    target: Optional[float]
    reason_in: str

    @property
    def dir(self) -> int:
        return 1 if self.side == "long" else -1


class BacktestEngine:
    def __init__(
        self,
        cost_model: CostModel,
        instrument: InstrumentSpec,
        initial_equity: float = 100_000.0,
        risk_pct: float = 0.005,
        max_leverage: float = 1.0,
        atr_period: int = 14,
        maker_cost_model: Optional[CostModel] = None,
    ) -> None:
        self.cost_model = cost_model
        self.instrument = instrument
        self.initial_equity = initial_equity
        self.risk_pct = risk_pct
        self.max_leverage = max_leverage
        self.atr_period = atr_period
        #: Costs for PASSIVE (resting-limit) fills: a maker pays no spread and no taker
        #: slippage but still owes per-contract/cash fees. Defaults to the taker model so
        #: limit entries are never *advantaged* unless the caller explicitly models it.
        self.maker_cost_model = maker_cost_model or cost_model

    # --- public ------------------------------------------------------------

    def run(self, strategy: BaseStrategy, base_bars: pd.DataFrame, base_tf: TimeFrame,
            reference_bars: Optional[pd.DataFrame] = None,
            regime_series=None, news_calendar=None) -> Result:
        symbol = self.instrument.symbol
        timeframes = strategy.required_timeframes or [base_tf]
        clock = MultiTFClock(base_bars, base_tf, timeframes)
        # Optional correlated reference (Phase C / SMT): its own clock on the same base_tf, served
        # causally against the same `now` — so the strategy sees only the reference's completed bars.
        ref_clock = MultiTFClock(reference_bars, base_tf, timeframes) if reference_bars is not None \
            and not reference_bars.empty else None
        # Optional Phase D side-channels: macro regime tag series + high-impact news calendar.
        ctx = BacktestContext(clock, symbol, ref_clock=ref_clock,
                              regime_series=regime_series, news_calendar=news_calendar)
        strategy.on_start(ctx)

        atr = classic.atr(base_bars, self.atr_period)  # for slippage; read at the prior bar

        realized = 0.0
        equity_times: list[datetime] = []
        equity_values: list[float] = []
        trades: list[Trade] = []
        open_pos: Optional[_Open] = None
        pending_entry: Optional[Signal] = None
        pending_ttl = 0          # bars a resting limit entry has left before it cancels
        pending_exit = False

        index = base_bars.index
        base_dur = _bar_duration(base_tf)
        for i in range(len(base_bars)):
            bar = base_bars.iloc[i]
            now = index[i] + base_dur  # close time of this bar
            slip_atr = float(atr.iloc[i - 1]) if i > 0 and not math.isnan(atr.iloc[i - 1]) else 0.0

            # 1. act on what was queued last bar: market entries at THIS bar's open; resting
            #    limit entries against THIS bar's range (gap-through at open, strict
            #    trade-through at the limit, touch ≠ fill, cancel when the TTL runs out).
            if open_pos is not None and pending_exit:
                trades.append(self._close(open_pos, bar["open"], now, i, "signal", slip_atr))
                realized += trades[-1].net_pnl
                open_pos, pending_exit = None, False
            elif open_pos is None and pending_entry is not None:
                equity = self.initial_equity + realized
                if pending_entry.limit is None:
                    open_pos = self._open(pending_entry, float(bar["open"]), i, now, equity,
                                          slip_atr, passive=False)
                    pending_entry = None
                else:
                    fill_px = self._limit_fill(pending_entry, bar)
                    if fill_px is not None:
                        open_pos = self._open(pending_entry, fill_px, i, now, equity,
                                              slip_atr, passive=True)
                        pending_entry = None
                    else:
                        pending_ttl -= 1
                        if pending_ttl <= 0:
                            pending_entry = None  # never pulled back — the signal expires

            # 2. manage the open position against this bar's range (intrabar stop/target).
            if open_pos is not None:
                hit = self._stop_or_target(open_pos, bar)
                if hit is not None:
                    level, reason = hit
                    trades.append(self._close(open_pos, level, now, i, reason, slip_atr))
                    realized += trades[-1].net_pnl
                    open_pos = None

            # 3. mark equity at the close.
            unreal = self._unrealized(open_pos, bar["close"]) if open_pos else 0.0
            equity = self.initial_equity + realized + unreal
            equity_times.append(now)
            equity_values.append(equity)

            # 4. strategy decision as of the close (completed bars only).
            position = self._position_view(open_pos, bar["close"], symbol)
            account = Account(cash=equity, equity=equity, buying_power=equity)
            ctx._update(now, float(bar["close"]), position, account)
            signal = strategy.on_bar(ctx)

            # 5. queue the order: market -> next-bar-open; limit -> rests for ttl_bars.
            #    A fresh entry signal replaces any still-resting limit.
            if signal is not None:
                if open_pos is None and signal.side in ("long", "short"):
                    pending_entry = signal
                    pending_ttl = max(1, int(signal.ttl_bars))
                elif open_pos is not None and signal.side == "flat":
                    pending_exit = True

        # End of data: mark any open position to the last close as a real (cost-bearing) exit.
        # Silently dropping it censors slow strategies — their multi-month winners are exactly
        # the trades still open at a span boundary (walk-forward folds chop on calendar years).
        if open_pos is not None and len(base_bars):
            last = base_bars.iloc[-1]
            trades.append(self._close(open_pos, float(last["close"]), index[-1] + base_dur,
                                      len(base_bars) - 1, "end_of_data", slip_atr))
            realized += trades[-1].net_pnl
            open_pos = None

        equity_curve = pd.Series(equity_values, index=pd.DatetimeIndex(equity_times), name="equity")
        return Result(
            strategy=strategy.name,
            symbol=symbol,
            params=dict(strategy.params),
            trades=trades,
            equity_curve=equity_curve,
            metrics={},
            period_start=index[0] if len(index) else None,
            period_end=index[-1] if len(index) else None,
        )

    # --- order execution ---------------------------------------------------

    def _open(self, sig: Signal, ref: float, i: int, now: datetime, equity: float, atr: float,
              *, passive: bool = False) -> Optional[_Open]:
        """Open at reference price ``ref`` (a market fill at the bar open, or a limit fill).
        Passive fills are costed by ``maker_cost_model`` (no taker spread/slippage)."""
        qty = self._size(equity, ref, sig.stop)
        if qty <= 0:
            return None
        side = sig.side
        fc = FillContext("buy" if side == "long" else "sell", qty, ref, self.instrument, atr=atr)
        res = (self.maker_cost_model if passive else self.cost_model).apply(fc)
        return _Open(
            side=side, qty=qty, entry_fill=res.fill_price, entry_ref=ref, entry_ts=now, entry_i=i,
            entry_cash=res.cash_cost, stop=sig.stop, target=sig.target, reason_in=sig.reason,
        )

    @staticmethod
    def _limit_fill(sig: Signal, bar: pd.Series) -> Optional[float]:
        """Price a resting limit fills at against one bar, or None.

        Conservative by construction: a gap through the limit fills at the (better) open;
        an intrabar *trade-through* (strictly beyond the limit) fills at the limit; a bar that
        merely touches the limit does NOT fill — queue position at the touch is unknowable.
        """
        lim = float(sig.limit)  # type: ignore[arg-type]
        o = float(bar["open"])
        if sig.side == "long":
            if o < lim:
                return o
            return lim if float(bar["low"]) < lim else None
        if o > lim:
            return o
        return lim if float(bar["high"]) > lim else None

    def _close(self, pos: _Open, ref_price: float, now: datetime, i: int, reason: str, atr: float) -> Trade:
        fc = FillContext("sell" if pos.side == "long" else "buy", pos.qty, ref_price, self.instrument, atr=atr)
        res = self.cost_model.apply(fc)
        exit_fill = res.fill_price

        mult = self.instrument.multiplier                                  # 1 for equities; point value for futures
        gross = (ref_price - pos.entry_ref) * pos.qty * pos.dir * mult      # frictionless
        net = (exit_fill - pos.entry_fill) * pos.qty * pos.dir * mult - pos.entry_cash - res.cash_cost
        costs = gross - net
        notional = pos.entry_fill * pos.qty * mult
        return Trade(
            symbol=self.instrument.symbol, side=pos.side, entry_ts=pos.entry_ts, exit_ts=now,
            entry_px=pos.entry_fill, exit_px=exit_fill, qty=pos.qty,
            gross_pnl=gross, costs=costs, net_pnl=net,
            return_pct=net / notional if notional else 0.0,
            bars_held=i - pos.entry_i, reason_in=pos.reason_in, reason_out=reason,
        )

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def _stop_or_target(pos: _Open, bar: pd.Series) -> Optional[tuple[float, str]]:
        """Exit level + reason if the bar hit the stop or target. Stop-first if both (pessimistic)."""
        high, low = float(bar["high"]), float(bar["low"])
        if pos.side == "long":
            hit_stop = pos.stop is not None and low <= pos.stop
            hit_tgt = pos.target is not None and high >= pos.target
        else:
            hit_stop = pos.stop is not None and high >= pos.stop
            hit_tgt = pos.target is not None and low <= pos.target
        if hit_stop:
            return pos.stop, "stop"
        if hit_tgt:
            return pos.target, "target"
        return None

    def _size(self, equity: float, entry: float, stop: Optional[float]) -> float:
        """Fixed-fractional sizing capped by gross notional exposure.

        Tiny structural stops can otherwise imply unrealistic leverage and make costs dominate the
        backtest. The full risk layer lands later; this local cap keeps v1 strategy tests honest.
        """
        risk_cash = equity * self.risk_pct
        if stop is None or abs(entry - stop) <= 0:
            return 0.0
        risk_qty = risk_cash / (abs(entry - stop) * self.instrument.multiplier)
        if self.max_leverage <= 0 or entry <= 0:
            return float(math.floor(risk_qty))
        max_notional = equity * self.max_leverage
        notional_qty = max_notional / (entry * self.instrument.multiplier)
        return float(math.floor(min(risk_qty, notional_qty)))

    def _unrealized(self, pos: _Open, close: float) -> float:
        return (close - pos.entry_fill) * pos.qty * pos.dir - pos.entry_cash

    def _position_view(self, pos: Optional[_Open], close: float, symbol: str) -> Position:
        if pos is None:
            return Position(symbol, qty=0.0, avg_px=0.0)
        signed_qty = pos.qty * pos.dir
        mv = signed_qty * close * self.instrument.multiplier
        return Position(symbol, qty=signed_qty, avg_px=pos.entry_fill, market_value=mv,
                        unrealized_pnl=self._unrealized(pos, close))
