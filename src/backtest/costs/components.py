"""Reusable cost components. Mix and match per market in ``presets/``.

Generic (any market):   BpsSpread, TickSpread, AtrSlippage, ParticipationSlippage,
                        PerUnitCommission, PercentNotionalCommission, FundingRate, BorrowFee
Statutory (regulatory): PercentCharge (side-aware turnover %), FlatFee, GST, UsRegFees

Each is a small frozen dataclass implementing ``compute(ctx, prior) -> CostItem | None``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.backtest.costs.core import CostItem, CostKind, FillContext

# --- price-moving (spread / slippage) -------------------------------------


@dataclass(frozen=True, slots=True)
class BpsSpread:
    """Half the bid/ask spread, in basis points of price."""

    half_spread_bps: float
    name: str = "spread"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        return CostItem(self.name, CostKind.PRICE, self.half_spread_bps / 1e4 * ctx.price)


@dataclass(frozen=True, slots=True)
class TickSpread:
    """Spread expressed in ticks (futures). Uses the instrument's ``tick_size``."""

    ticks: float
    name: str = "spread"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        tick = ctx.instrument.tick_size or 0.0
        return CostItem(self.name, CostKind.PRICE, self.ticks * tick)


@dataclass(frozen=True, slots=True)
class AtrSlippage:
    """Volatility-scaled slippage: ``atr_mult * ATR``. ``stress`` is the ×N fragility knob."""

    atr_mult: float
    stress: float = 1.0
    name: str = "slippage"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        atr = ctx.atr or 0.0
        return CostItem(self.name, CostKind.PRICE, self.atr_mult * atr * self.stress)


@dataclass(frozen=True, slots=True)
class ParticipationSlippage:
    """Market-impact slippage scaled by order participation (qty / bar volume)."""

    impact_coef: float
    name: str = "impact"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        if not ctx.volume:
            return None
        participation = abs(ctx.qty) / ctx.volume
        return CostItem(self.name, CostKind.PRICE, self.impact_coef * ctx.price * participation)


# --- commissions -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PerUnitCommission:
    """Per-share / per-contract commission with an optional minimum (US-style)."""

    per_unit: float
    minimum: float = 0.0
    taxable: bool = False
    name: str = "commission"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        amount = max(self.minimum, abs(ctx.qty) * self.per_unit)
        return CostItem(self.name, CostKind.CASH, amount, self.taxable)


@dataclass(frozen=True, slots=True)
class PercentNotionalCommission:
    """Percent-of-notional commission with optional cap/minimum (crypto taker, India brokerage)."""

    pct: float
    minimum: float = 0.0
    cap: Optional[float] = None
    taxable: bool = False
    name: str = "commission"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        amount = self.pct * ctx.notional
        if self.cap is not None:
            amount = min(amount, self.cap)
        amount = max(amount, self.minimum)
        return CostItem(self.name, CostKind.CASH, amount, self.taxable)


# --- statutory / regulatory ------------------------------------------------


@dataclass(frozen=True, slots=True)
class PercentCharge:
    """Side-aware percent-of-turnover charge — the shape of most Indian statutory levies
    (STT, stamp duty, exchange txn, SEBI). Set only the side(s) that apply."""

    name: str
    buy_pct: float = 0.0
    sell_pct: float = 0.0
    taxable: bool = False

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        pct = self.buy_pct if ctx.side == "buy" else self.sell_pct
        return CostItem(self.name, CostKind.CASH, pct * ctx.notional, self.taxable)


@dataclass(frozen=True, slots=True)
class FlatFee:
    """A flat per-fill fee, optionally only on one side (e.g. India DP charge on delivery sells)."""

    amount: float
    side: Optional[str] = None       # "buy" / "sell" / None = both
    taxable: bool = False
    name: str = "fee"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        if self.side is not None and ctx.side != self.side:
            return None
        return CostItem(self.name, CostKind.CASH, self.amount, self.taxable)


@dataclass(frozen=True, slots=True)
class GST:
    """Goods & Services Tax (India): a percent of the *taxable* charges computed before it.
    Must be placed last in the component list."""

    rate: float = 0.18
    name: str = "gst"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        base = sum(it.amount for it in prior if it.taxable)
        return CostItem(self.name, CostKind.CASH, self.rate * base)


@dataclass(frozen=True, slots=True)
class UsRegFees:
    """US sell-side regulatory fees: FINRA TAF (per share, capped) + SEC Section 31 (per notional)."""

    taf_per_share: float = 0.000166
    taf_cap: float = 8.30
    sec_per_million: float = 0.0     # $0.00/MM from 2025-05-14
    name: str = "reg_fees"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        if ctx.side != "sell":
            return None
        taf = min(self.taf_cap, abs(ctx.qty) * self.taf_per_share)
        sec = self.sec_per_million / 1e6 * ctx.notional
        return CostItem(self.name, CostKind.CASH, taf + sec)


# --- carry (held positions) ------------------------------------------------


@dataclass(frozen=True, slots=True)
class FundingRate:
    """Crypto perpetual funding, prorated by holding time (charged in 8h periods)."""

    rate_per_8h: float
    name: str = "funding"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        if not ctx.holding_hours:
            return None
        return CostItem(self.name, CostKind.CASH, self.rate_per_8h * ctx.notional * (ctx.holding_hours / 8.0))


@dataclass(frozen=True, slots=True)
class BorrowFee:
    """Short-borrow fee, annualized rate prorated by holding time."""

    annual_rate: float
    name: str = "borrow"

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        if not ctx.holding_hours:
            return None
        return CostItem(self.name, CostKind.CASH, self.annual_rate * ctx.notional * (ctx.holding_hours / 24.0 / 365.0))
