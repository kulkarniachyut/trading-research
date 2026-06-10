"""Daily paper loop — submits the two-system protocol to Alpaca PAPER (Step 6 bridge).

Run once per day AFTER the close (e.g. 16:15 ET). It:
  1. reconciles yesterday's pending limit entries against broker positions (fill -> record the
     lot + submit its GTC disaster stop; no fill -> the day order expired, forget it),
  2. plans today's orders (IBS limit entries / IBS exits / TOM window entries-exits) from
     fresh yfinance daily bars + the NYSE calendar,
  3. shows the plan and asks for approval (manual-approval ON by default — CLAUDE.md hard
     rule; pass ``--yes`` for unattended/scheduled runs),
  4. submits to Alpaca paper and appends everything to the JSONL journal
     (``data/paper_journal.jsonl`` — the live-evidence record the backtest gets judged against).

PAPER ONLY by construction (the broker class hard-codes paper=True).

Usage: paper_loop.py [--yes] [--dry-run] [--risk-pct 0.5]
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta

import pandas as pd
import pandas_market_calendars as mcal

from src.core.config import REPO_ROOT
from src.core.types import TimeFrame
from src.data.yfinance_provider import YFinanceProvider
from src.execution.alpaca_broker import AlpacaPaperBroker, OrderPlan
from src.execution.protocol import (
    IBS_ETFS,
    TOM_ETFS,
    Lot,
    plan_ibs,
    plan_tom,
)
from src.strategies.meanrev.turn_of_month import month_position

JOURNAL = REPO_ROOT / "data" / "paper_journal.jsonl"


def _journal_append(record: dict) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a") as fh:
        fh.write(json.dumps({"ts": datetime.now().isoformat(), **record}) + "\n")


def _journal_read() -> list[dict]:
    if not JOURNAL.exists():
        return []
    return [json.loads(line) for line in JOURNAL.read_text().splitlines() if line.strip()]


def _state() -> tuple[list[Lot], list[dict]]:
    """Replay the journal into (open lots, pending limit entries)."""
    lots: dict[tuple[str, str], Lot] = {}
    pending: dict[str, dict] = {}
    for rec in _journal_read():
        kind = rec.get("kind")
        if kind == "pending_entry":
            pending[rec["symbol"]] = rec
        elif kind == "pending_expired":
            pending.pop(rec["symbol"], None)
        elif kind == "lot_open":
            pending.pop(rec["symbol"], None)
            lots[(rec["system"], rec["symbol"])] = Lot(
                rec["system"], rec["symbol"], int(rec["qty"]), rec["entry_session"],
                rec.get("stop"))
        elif kind == "lot_close":
            lots.pop((rec["system"], rec["symbol"]), None)
    return list(lots.values()), list(pending.values())


def main() -> None:
    args = sys.argv[1:]
    auto = "--yes" in args
    dry = "--dry-run" in args
    risk_pct = (float(args[args.index("--risk-pct") + 1]) if "--risk-pct" in args else 0.5) / 100

    broker = AlpacaPaperBroker()
    equity = broker.equity()
    positions = broker.positions()
    lots, pending = _state()
    today = pd.Timestamp.now(tz="America/New_York").normalize().tz_localize(None)
    print(f"paper loop {today.date()} — equity ${equity:,.0f}, "
          f"{len(lots)} lots, {len(pending)} pending entries")

    # 1. reconcile yesterday's pending limit entries
    for rec in pending:
        sym, system = rec["symbol"], rec["system"]
        have = positions.get(sym, 0)
        lot_qty = sum(lo.qty for lo in lots if lo.symbol == sym)
        if have >= lot_qty + int(rec["qty"]):  # the limit filled
            _journal_append({"kind": "lot_open", "system": system, "symbol": sym,
                             "qty": rec["qty"], "entry_session": str(today.date()),
                             "stop": rec.get("stop")})
            lots.append(Lot(system, sym, int(rec["qty"]), str(today.date()), rec.get("stop")))
            if rec.get("stop") and not dry:
                oid = broker.submit(OrderPlan(system, "stop_gtc", sym, int(rec["qty"]),
                                              stop_price=float(rec["stop"]), note="disaster stop"))
                _journal_append({"kind": "stop_submitted", "symbol": sym, "order_id": oid})
            print(f"  filled: {system} {sym} x{rec['qty']} -> lot opened, stop placed")
        else:
            _journal_append({"kind": "pending_expired", "symbol": sym})
            print(f"  expired unfilled: {system} {sym} (no chase — by design)")

    # 2. plan today
    prov = YFinanceProvider()
    end = pd.Timestamp(datetime.now())
    start = end - timedelta(days=420)
    bars: dict[str, pd.DataFrame] = {}
    for sym in set(IBS_ETFS) | set(TOM_ETFS):
        try:
            d1 = prov.get_bars(sym, TimeFrame.D1, start, end)
            bars[sym] = d1.dropna(subset=["open", "high", "low", "close"]) if d1 is not None else None
        except Exception as exc:  # noqa: BLE001
            print(f"  {sym}: fetch failed ({exc})")

    plans = plan_ibs(bars, lots, {p["symbol"] for p in pending}, equity * risk_pct)

    sched = mcal.get_calendar("NYSE").schedule(start_date=today - timedelta(days=10),
                                               end_date=today + timedelta(days=40))
    sessions = pd.DatetimeIndex(sched.index)
    pos_map = month_position(sessions)
    future = [s for s in sessions if s > today]
    if future:
        next_session = pd.Timestamp(future[0]).normalize()
        closes = {s: float(b["close"].iloc[-1]) for s, b in bars.items()
                  if b is not None and len(b)}
        plans += plan_tom(pos_map[next_session], lots, closes, equity)

    if not plans:
        print("  no orders today")
        return
    print("\n  PLANNED ORDERS:")
    for p in plans:
        px = f" limit {p.limit_price:.2f}" if p.limit_price else ""
        st = f" stop {p.stop_price:.2f}" if p.stop_price else ""
        print(f"    [{p.system}] {p.action:17s} {p.symbol:5s} x{p.qty}{px}{st}  ({p.note})")

    if dry:
        print("  dry run — nothing submitted.")
        return
    if not auto and input("\n  submit to Alpaca PAPER? [y/N] ").strip().lower() != "y":
        print("  aborted — nothing submitted.")
        return

    # 3. submit + journal
    for p in plans:
        try:
            oid = broker.submit(p)
        except Exception as exc:  # noqa: BLE001
            print(f"    SUBMIT FAILED {p.symbol}: {exc}")
            _journal_append({"kind": "submit_error", **p.to_dict(), "error": str(exc)})
            continue
        if p.action == "limit_day":
            _journal_append({"kind": "pending_entry", "system": p.system, "symbol": p.symbol,
                             "qty": p.qty, "limit": p.limit_price, "stop": p.stop_price,
                             "order_id": oid})
        elif p.action == "market_open_buy":
            _journal_append({"kind": "lot_open", "system": p.system, "symbol": p.symbol,
                             "qty": p.qty, "entry_session": str(today.date()), "order_id": oid})
        elif p.action == "market_open_sell":
            _journal_append({"kind": "lot_close", "system": p.system, "symbol": p.symbol,
                             "qty": p.qty, "order_id": oid})
        print(f"    submitted {p.symbol} ({oid})")
    print(f"  journal: {JOURNAL}")


if __name__ == "__main__":
    main()
