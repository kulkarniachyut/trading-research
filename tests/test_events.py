"""Phase D — macro regime + news calendar primitives, and their causal context wiring."""

from __future__ import annotations

import datetime as dt

import pandas as pd

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import MarketContext, TimeFrame
from src.events.calendar import FOMC_DATES, NewsCalendar, nfp_days
from src.events.regime import vix_regime
from src.strategies.base import BaseStrategy

NY = "America/New_York"


def test_vix_regime_is_threshold_and_causal():
    idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-04"], tz=NY)
    vix = pd.Series([25.0, 15.0, 30.0], index=idx)
    reg = vix_regime(vix, threshold=20.0)
    # day T uses T-1's close (shift): 01-03 sees 25→risk_off; 01-04 sees 15→risk_on; 01-02 NaN→risk_on
    assert reg.loc["2024-01-02"] == "risk_on"
    assert reg.loc["2024-01-03"] == "risk_off"
    assert reg.loc["2024-01-04"] == "risk_on"


def test_nfp_is_first_friday_and_fomc_present():
    assert dt.date(2024, 1, 5) in nfp_days(2024)    # Jan 2024 first Friday
    assert dt.date(2024, 2, 2) in nfp_days(2024)    # Feb 2024 first Friday
    cal = NewsCalendar()
    assert cal.is_news_day(pd.Timestamp("2024-01-31 10:00", tz=NY))   # FOMC day
    assert dt.date(2024, 1, 31) in FOMC_DATES
    assert not cal.is_news_day(pd.Timestamp("2024-01-30 10:00", tz=NY))


def _bars(date, periods=6):
    idx = pd.date_range(f"{date} 09:30", periods=periods, freq="5min", tz=NY)
    return pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0, "volume": 1.0}, index=idx)


def test_context_regime_and_news_day_wired_causally():
    bars = _bars("2024-01-31")                       # an FOMC day
    regime = pd.Series(["risk_off"], index=pd.DatetimeIndex(["2024-01-31"], tz=NY))
    seen = {}

    class Peek(BaseStrategy):
        required_timeframes = [TimeFrame.M5]

        def on_bar(self, ctx: MarketContext):
            seen["regime"] = ctx.regime()
            seen["news"] = ctx.is_news_day()
            return None

    eng = BacktestEngine(cost_model("US", "equity"),
                         InstrumentSpec("X", Market("US", AssetClass.EQUITY, Product.INTRADAY)))
    eng.run(Peek(), bars, TimeFrame.M5, regime_series=regime, news_calendar=NewsCalendar())
    assert seen["regime"] == "risk_off"
    assert seen["news"] is True


def test_context_defaults_none_when_unwired():
    bars = _bars("2024-03-12")
    seen = {}

    class Peek(BaseStrategy):
        required_timeframes = [TimeFrame.M5]

        def on_bar(self, ctx):
            seen["regime"] = ctx.regime()
            seen["news"] = ctx.is_news_day()
            return None

    BacktestEngine(cost_model("US", "equity"),
                   InstrumentSpec("X", Market("US", AssetClass.EQUITY, Product.INTRADAY))
                   ).run(Peek(), bars, TimeFrame.M5)
    assert seen["regime"] is None and seen["news"] is False
