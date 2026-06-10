"""Daily IBS-ETF signal sheet — manual paper-trading companion (Step 4 → Step 6 bridge).

Run AFTER the close (or before the next open). For each ETF in the validated universe it
computes the frozen IBS rule (0.2/0.8/MA200/5d/3-ATR — the exact backtested params, zero knobs)
on yfinance daily bars and prints:
  - ENTER rows: rest a LIMIT BUY at today's close for tomorrow (cancel end of day — the
    backtest's ttl=1 day), stop level, and a position size for your account/risk.
  - EXIT guidance for held positions: exit when IBS >= 0.8 or on the 5th day, whichever first.

This is the paper protocol that matches the backtest: passive limit at the signal close
(maker fill), no chasing — if price never pulls back, the signal expires unfilled, which is
part of the measured edge, not a miss. Journal fills/exits manually (Step 6 automates later).

Usage: signals_ibs_etf.py [--equity 15000] [--risk-pct 0.5]
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

import pandas as pd

from src.core.types import TimeFrame
from src.data.yfinance_provider import YFinanceProvider
from src.indicators import classic
from src.strategies.meanrev.ibs import ibs

ETFS = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI",
        "XLU", "XLB", "EFA", "EEM", "GLD"]

BUY_BELOW, EXIT_ABOVE, TREND_MA, MAX_HOLD, ATR_P, ATR_STOP = 0.2, 0.8, 200, 5, 20, 3.0


def _opt(flag: str, default: float) -> float:
    args = sys.argv[1:]
    return float(args[args.index(flag) + 1]) if flag in args else default


def main() -> None:
    equity = _opt("--equity", 15_000.0)
    risk_pct = _opt("--risk-pct", 0.5) / 100.0
    risk_cash = equity * risk_pct

    prov = YFinanceProvider()
    end = pd.Timestamp(datetime.now())
    start = end - timedelta(days=420)  # ~290 sessions — MA200 + slack

    print(f"IBS-ETF daily signals — frozen rule buy<{BUY_BELOW} exit>{EXIT_ABOVE} MA{TREND_MA} "
          f"hold<={MAX_HOLD}d stop {ATR_STOP}xATR{ATR_P}")
    print(f"account ${equity:,.0f}  risk/trade ${risk_cash:,.0f} ({risk_pct * 100:.2f}%)\n")
    rows = []
    for sym in ETFS:
        try:
            d1 = prov.get_bars(sym, TimeFrame.D1, start, end)
        except Exception as exc:  # noqa: BLE001 — one bad fetch shouldn't kill the sheet
            print(f"  {sym:5s} fetch failed: {exc}")
            continue
        if d1 is not None:
            d1 = d1.dropna(subset=["open", "high", "low", "close"])  # forming/partial rows
        if d1 is None or len(d1) < TREND_MA + 1:
            print(f"  {sym:5s} insufficient history ({0 if d1 is None else len(d1)} bars)")
            continue
        today = d1.iloc[-1]
        cur_ibs = ibs(today)
        close = float(today["close"])
        ma = float(d1["close"].rolling(TREND_MA).mean().iloc[-1])
        atr = float(classic.atr(d1, ATR_P).iloc[-1])
        ts = d1.index[-1].date()
        if cur_ibs <= BUY_BELOW and close > ma and atr > 0:
            stop = close - ATR_STOP * atr
            qty = int(risk_cash / (close - stop))
            rows.append((sym, ts, cur_ibs, close, stop, qty))
        status = "ENTER" if (cur_ibs <= BUY_BELOW and close > ma) else \
                 ("below MA" if close <= ma else "")
        print(f"  {sym:5s} {ts}  close {close:8.2f}  IBS {cur_ibs:4.2f}  MA{TREND_MA} "
              f"{ma:8.2f}  ATR {atr:6.2f}  {status}")

    if rows:
        print("\n>>> ENTRY ORDERS for the next session (limit, day-only, cancel at close):")
        for sym, ts, i, close, stop, qty in rows:
            print(f"    BUY {qty:4d} {sym:5s} LIMIT {close:.2f}   stop {stop:.2f}   "
                  f"(signal {ts}, IBS {i:.2f})")
        print("    If a limit does not fill by the close: cancel. Do NOT chase — unfilled")
        print("    signals are part of the backtested edge, not misses.")
    else:
        print("\n>>> no entries today")
    print(">>> EXITS for held positions: sell when day closes with IBS >= "
          f"{EXIT_ABOVE}, or at the close of day {MAX_HOLD}, or at your stop — whichever first.")

    _tom_status()


def _tom_status() -> None:
    """Turn-of-month window state (validated candidate #2 — see STEP4_EDGE_SEARCH_PLAN.md):
    long SPY/QQQ/DIA/IWM from the open of the 4th-to-last session of the month through the
    open of the 4th session of the next month. Market orders are fine (~12 round trips/yr)."""
    import pandas_market_calendars as mcal

    from src.strategies.meanrev.turn_of_month import month_position

    today = pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None)
    sched = mcal.get_calendar("NYSE").schedule(
        start_date=today - timedelta(days=45), end_date=today + timedelta(days=45))
    sessions = pd.DatetimeIndex(sched.index)
    pos = month_position(sessions)
    future = [s for s in sessions if s >= today]
    if not future:
        return
    cur = pd.Timestamp(future[0]).normalize()
    day_no, days_left = pos[cur]
    in_window = days_left <= 4 or day_no <= 3
    print("\n>>> TURN-OF-MONTH (SPY/QQQ/DIA/IWM, equal risk):")
    if in_window:
        exits = [s for s in future if pos[pd.Timestamp(s).normalize()][0] == 4
                 and s.month != cur.month or (pos[pd.Timestamp(s).normalize()][0] == 4
                                              and day_no <= 3 and s.month == cur.month)]
        nxt_exit = min(exits).date() if exits else "4th session of next month"
        print(f"    WINDOW ACTIVE (session {day_no}, {days_left} left in month). "
              f"Hold/enter; exit at the OPEN of {nxt_exit}.")
    else:
        entries = [s for s in future if pos[pd.Timestamp(s).normalize()][1] == 4]
        nxt = min(entries).date() if entries else "?"
        print(f"    window closed — next entry: buy at the OPEN of {nxt} "
              f"(4th-to-last session), exit at the open of the 4th session of the next month.")


if __name__ == "__main__":
    main()
