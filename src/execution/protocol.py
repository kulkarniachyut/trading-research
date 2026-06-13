"""The two-system paper protocol — pure order-planning logic (no network, no broker).

Turns (journal state, fresh daily bars, account equity) into ``OrderPlan``s for the validated
configurations (see docs/STEP4_EDGE_SEARCH_PLAN.md — parameters FROZEN, zero knobs here):

- IBS-limit entries: limit buy at the signal close, day-only (backtest ttl=1), 3-ATR stop
  placed once the fill is confirmed, exits market-on-open on IBS>=0.8 / 5th session held.
- Turn-of-month: market-on-open buys at the 4th-to-last session, sells at the 4th session.

State lives in a JSONL journal (one dict per line) owned by ``scripts/paper_loop.py``; this
module only computes. Both systems may hold the same symbol — lots are system-tagged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.execution.alpaca_broker import OrderPlan
from src.indicators import classic
from src.strategies.meanrev.ibs import ibs

IBS_ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
            "XLU", "XLB", "EFA", "EEM", "GLD"]
TOM_ETFS = ["SPY", "QQQ", "DIA", "IWM"]

BUY_BELOW, EXIT_ABOVE, TREND_MA, MAX_HOLD, ATR_P, ATR_STOP = 0.2, 0.8, 200, 5, 20, 3.0
TOM_ENTER_LEFT, TOM_EXIT_DAY = 4, 4  # fill-day conventions (signal day ±1, as backtested)


@dataclass
class Lot:
    """One held position owned by a system."""

    system: str
    symbol: str
    qty: int
    entry_session: str               # YYYY-MM-DD of the fill session
    stop: Optional[float] = None
    extra: dict = field(default_factory=dict)


def sessions_held(bars: pd.DataFrame, entry_session: str) -> int:
    """Completed sessions from entry through the latest bar (entry day = 1)."""
    days = bars.index.normalize().unique()
    entry = pd.Timestamp(entry_session).tz_localize(days.tz) if days.tz else pd.Timestamp(entry_session)
    return int((days >= entry.normalize()).sum())


def plan_ibs(bars_by_symbol: dict[str, pd.DataFrame], lots: list[Lot],
             pending_symbols: set[str], risk_cash: float) -> list[OrderPlan]:
    """IBS entries for fresh signals + exits for held lots, from completed daily bars."""
    plans: list[OrderPlan] = []
    held = {lot.symbol for lot in lots if lot.system == "ibs"}

    for lot in (lo for lo in lots if lo.system == "ibs"):
        d1 = bars_by_symbol.get(lot.symbol)
        if d1 is None or d1.empty:
            continue
        cur_ibs = ibs(d1.iloc[-1])
        held_n = sessions_held(d1, lot.entry_session)
        if cur_ibs >= EXIT_ABOVE or held_n >= MAX_HOLD:
            plans.append(OrderPlan("ibs", "market_open_sell", lot.symbol, lot.qty,
                                   note=f"exit ibs={cur_ibs:.2f} held={held_n}d"))

    for sym in IBS_ETFS:
        if sym in held or sym in pending_symbols:
            continue
        d1 = bars_by_symbol.get(sym)
        if d1 is None or len(d1) < TREND_MA + 1:
            continue
        today = d1.iloc[-1]
        cur_ibs = ibs(today)
        close = float(today["close"])
        ma = float(d1["close"].rolling(TREND_MA).mean().iloc[-1])
        atr = float(classic.atr(d1, ATR_P).iloc[-1])
        if cur_ibs <= BUY_BELOW and close > ma and atr > 0:
            stop = close - ATR_STOP * atr
            qty = int(risk_cash / (close - stop))
            if qty > 0:
                plans.append(OrderPlan("ibs", "limit_day", sym, qty, limit_price=close,
                                       stop_price=stop, note=f"entry ibs={cur_ibs:.2f}"))
    return plans


def plan_tom(month_pos: tuple[int, int], lots: list[Lot],
             closes: dict[str, float], equity: float) -> list[OrderPlan]:
    """TOM entries/exits given (trading day #, days left) of the NEXT session (the fill day).

    Sizing: equal notional = equity/8 per ETF (half the account across 4 names, levered
    nothing) — calendar exit does the risk work; there is no stop in the backtested spec.
    """
    day_no, days_left = month_pos
    plans: list[OrderPlan] = []
    held = {lot.symbol for lot in lots if lot.system == "tom"}
    if days_left == TOM_ENTER_LEFT:
        for sym in TOM_ETFS:
            if sym in held or sym not in closes or closes[sym] <= 0:
                continue
            qty = int(equity / 8.0 / closes[sym])
            if qty > 0:
                plans.append(OrderPlan("tom", "market_open_buy", sym, qty,
                                       note=f"tom enter (D-{days_left})"))
    elif day_no == TOM_EXIT_DAY:
        for lot in (lo for lo in lots if lo.system == "tom"):
            plans.append(OrderPlan("tom", "market_open_sell", lot.symbol, lot.qty,
                                   note=f"tom exit (day {day_no})"))
    return plans
