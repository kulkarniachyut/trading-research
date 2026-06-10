"""Alpaca paper broker — the thin, testable order layer for the two-system paper protocol.

Wraps ``alpaca-py``'s ``TradingClient`` (paper=True always — this module refuses live keys'
implications by construction: ``paper`` is not a parameter). Order types used by the protocol:

- ``limit_day``   — IBS entry: rest a limit at the signal close, expires at the close (ttl=1).
- ``stop_gtc``    — IBS disaster stop, placed once an entry fill is detected.
- ``market_open`` — TOM entry/exit and IBS exits: market-on-open (``opg``), matching the
                    backtest's next-bar-open fill convention.

Every call goes through ``OrderPlan`` first so scripts can build, display, and journal the
exact orders *before* anything is submitted — manual approval is the default in the loop
(CLAUDE.md hard rule), and unit tests assert on plans without any network.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from src.core.config import alpaca_credentials


@dataclass(frozen=True, slots=True)
class OrderPlan:
    """One intended order — built first, shown/journaled, then (maybe) submitted."""

    system: str            # "ibs" | "tom"
    action: str            # "limit_day" | "stop_gtc" | "market_open_buy" | "market_open_sell"
    symbol: str
    qty: int
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AlpacaPaperBroker:
    """Paper-only execution. Constructing it without paper keys raises."""

    def __init__(self) -> None:
        creds = alpaca_credentials()
        if creds is None:
            raise RuntimeError("Alpaca keys not found (.env ALPACA_API_KEY_ID/SECRET).")
        from alpaca.trading.client import TradingClient

        self._client = TradingClient(creds.api_key_id, creds.api_secret_key, paper=True)

    # --- account state -------------------------------------------------------

    def equity(self) -> float:
        return float(self._client.get_account().equity)

    def positions(self) -> dict[str, int]:
        """symbol -> signed share count of current open positions."""
        return {p.symbol: int(float(p.qty)) for p in self._client.get_all_positions()}

    def open_order_symbols(self) -> set[str]:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        orders = self._client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
        return {o.symbol for o in orders}

    def order_status(self, order_id: str) -> tuple[str, int, Optional[float]]:
        """(status, filled_qty, filled_avg_price) for one order — the reconcile primitive."""
        o = self._client.get_order_by_id(order_id)
        px = float(o.filled_avg_price) if o.filled_avg_price else None
        return str(o.status.value), int(float(o.filled_qty or 0)), px

    # --- submission ----------------------------------------------------------

    def submit(self, plan: OrderPlan) -> str:
        """Submit one OrderPlan; returns the broker order id."""
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import (
            LimitOrderRequest,
            MarketOrderRequest,
            StopOrderRequest,
        )

        if plan.action == "limit_day":
            req = LimitOrderRequest(symbol=plan.symbol, qty=plan.qty, side=OrderSide.BUY,
                                    time_in_force=TimeInForce.DAY,
                                    limit_price=round(plan.limit_price, 2))
        elif plan.action == "stop_gtc":
            req = StopOrderRequest(symbol=plan.symbol, qty=plan.qty, side=OrderSide.SELL,
                                   time_in_force=TimeInForce.GTC,
                                   stop_price=round(plan.stop_price, 2))
        elif plan.action in ("market_open_buy", "market_open_sell"):
            side = OrderSide.BUY if plan.action.endswith("buy") else OrderSide.SELL
            req = MarketOrderRequest(symbol=plan.symbol, qty=plan.qty, side=side,
                                     time_in_force=TimeInForce.OPG)
        else:
            raise ValueError(f"unknown action {plan.action!r}")
        order = self._client.submit_order(req)
        return str(order.id)
