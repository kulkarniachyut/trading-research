"""Options data provider contract — and a frank note on the data reality.

⚠️ THE CORE CHALLENGE OF OPTIONS BACKTESTING IS DATA, NOT CODE.
Equity bar history is free and clean (yfinance/Alpaca). Historical *options* data — full chains
with bid/ask/IV/greeks at each past timestamp — is **expensive and hard to get clean**:
- yfinance exposes only the CURRENT chain (`Ticker.option_chain`) — NO history. Good for live
  signal generation and paper trading; useless for backtesting a multi-year edge.
- Real historical chains (with the bid/ask we MUST have, since spread is the dominant cost) come
  from paid vendors: ORATS, CBOE DataShop, IVolatility, Polygon options, Databento OPRA. Plan to
  pay, or restrict the research to what can be reconstructed.
- A pragmatic free-ish path: reconstruct option prices from the UNDERLYING's historical bars +
  a volatility assumption via Black-Scholes (`options.pricing`). This is fine for *vol-risk-
  premium / theta* style studies if you (a) use a realistic IV (e.g. VIX-implied or an IV proxy),
  and (b) add a punitive synthetic spread. It is NOT fine for anything that depends on the smile,
  skew, or precise quotes — those need real chains.

So: this module ships the CONTRACT (`OptionsDataProvider`) + a live `YFinanceOptionsProvider`
(for paper/live signals) + a `SyntheticChainProvider` (BS-reconstructed, for disciplined research
on the underlying's history). Wire a paid vendor behind the same contract when ready.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Optional

from options.contracts import OptionContract, OptionQuote, Right


class OptionsDataProvider(ABC):
    """The single contract every options data source implements (mirrors `src/data/base.py`).

    A backtest/strategy asks for the chain of one underlying *as of* a timestamp and never sees
    a future quote — the no-look-ahead rule applies to options exactly as to bars.
    """

    @abstractmethod
    def get_chain(self, underlying: str, asof: datetime,
                  expiries: Optional[list[date]] = None) -> list[OptionQuote]:
        """All option quotes for ``underlying`` as of ``asof`` (optionally filtered to ``expiries``).
        Implementations MUST NOT return any quote dated after ``asof``."""

    @abstractmethod
    def expirations(self, underlying: str, asof: datetime) -> list[date]:
        """Listed expiries for ``underlying`` known as of ``asof``."""


class YFinanceOptionsProvider(OptionsDataProvider):
    """LIVE chain only (yfinance has no options history). Use for paper/live signal generation,
    NOT for backtesting. ``asof`` must be ~now; a historical ``asof`` raises to prevent silent
    look-ahead/garbage."""

    def expirations(self, underlying: str, asof: datetime) -> list[date]:
        self._guard_live(asof)
        import yfinance as yf

        return [date.fromisoformat(s) for s in yf.Ticker(underlying).options]

    def get_chain(self, underlying: str, asof: datetime,
                  expiries: Optional[list[date]] = None) -> list[OptionQuote]:
        self._guard_live(asof)
        import yfinance as yf

        tk = yf.Ticker(underlying)
        spot = float(tk.history(period="1d")["Close"].iloc[-1])
        want = expiries or [date.fromisoformat(s) for s in tk.options]
        out: list[OptionQuote] = []
        for exp in want:
            ch = tk.option_chain(exp.isoformat())
            for frame, right in ((ch.calls, Right.CALL), (ch.puts, Right.PUT)):
                for _, row in frame.iterrows():
                    c = OptionContract(underlying, exp, float(row["strike"]), right)
                    out.append(OptionQuote(
                        contract=c, asof=asof,
                        bid=float(row.get("bid", 0.0) or 0.0),
                        ask=float(row.get("ask", 0.0) or 0.0),
                        last=float(row.get("lastPrice", 0.0) or 0.0) or None,
                        iv=float(row["impliedVolatility"]) if row.get("impliedVolatility") else None,
                        open_interest=int(row.get("openInterest", 0) or 0),
                        volume=int(row.get("volume", 0) or 0),
                        underlying_price=spot,
                    ))
        return out

    @staticmethod
    def _guard_live(asof: datetime) -> None:
        if (datetime.now() - asof).days > 2:
            raise ValueError(
                "YFinanceOptionsProvider serves only the LIVE chain — a historical asof would "
                "silently return today's quotes (look-ahead). Use a vendor or SyntheticChainProvider."
            )


class SyntheticChainProvider(OptionsDataProvider):
    """Reconstructs an options chain from the underlying's historical bars + a volatility input,
    via Black-Scholes. The DISCIPLINED free path for vol/theta research — but it bakes in your IV
    assumption and a *synthetic* spread, so it cannot study skew/smile. Skeleton: wire an
    underlying-bar provider + an IV series (e.g. VIX/realized-vol proxy), then build quotes with
    ``options.pricing.bs_price`` and a punitive ``synthetic_spread_pct``.

    TODO(scaffold): implement get_chain by (1) fetching the underlying close at ``asof`` from the
    repo's existing DataProvider, (2) reading the IV input for ``asof``, (3) generating a strike
    ladder around spot, (4) pricing each via bs_price, (5) wrapping in an OptionQuote with
    bid/ask = mid ∓ (synthetic_spread_pct/2)*mid. Keep it causal (no future bars).
    """

    def __init__(self, synthetic_spread_pct: float = 0.05,
                 risk_free: float = 0.04, dividend_yield: float = 0.0) -> None:
        self.synthetic_spread_pct = synthetic_spread_pct
        self.risk_free = risk_free
        self.dividend_yield = dividend_yield

    def expirations(self, underlying: str, asof: datetime) -> list[date]:
        raise NotImplementedError("SyntheticChainProvider.expirations — scaffold; see class docstring")

    def get_chain(self, underlying: str, asof: datetime,
                  expiries: Optional[list[date]] = None) -> list[OptionQuote]:
        raise NotImplementedError("SyntheticChainProvider.get_chain — scaffold; see class docstring")
