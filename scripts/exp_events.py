"""Phase D measurement — do the macro-regime gate and the news-day filter help (toggles)?

Equity universe, 2024. Compares baseline vs +regime (stand down risk-off), +news (stand down on
FOMC/NFP days), and +both. A useful filter raises expectancy (drops bad trades); a useless one just
cuts frequency. Regime = VIX (yfinance ^VIX), shifted 1 day (causal). News = FOMC + NFP days.
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.alpaca import AlpacaProvider
from src.events.calendar import NewsCalendar
from src.events.regime import fetch_vix_regime
from src.strategies.ict.ict_2022 import Ict2022

EQUITIES = ["SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN",
            "META", "GOOGL", "TSLA", "AMD", "NFLX", "JPM", "XLE", "GLD"]

CONFIGS = {
    "baseline": {},
    "+regime": {"block_risk_off": True},
    "+news": {"block_news_day": True},
    "+both": {"block_risk_off": True, "block_news_day": True},
}


def main() -> None:
    yr = sys.argv[1] if len(sys.argv) > 1 else "2024"
    prov = AlpacaProvider()
    universe = [UniverseItem(s) for s in EQUITIES]
    s = pd.Timestamp(f"{yr}-01-01", tz="America/New_York")
    e = pd.Timestamp(f"{yr}-12-31", tz="America/New_York")
    regime = fetch_vix_regime(pd.Timestamp(f"{int(yr)-1}-12-01", tz="America/New_York"), e, threshold=20.0)
    risk_off_frac = (regime == "risk_off").mean() * 100
    cal = NewsCalendar()
    print(f"\n=== Phase D toggles, equities {yr} (VIX risk-off {risk_off_frac:.0f}% of days) ===")
    print(f"{'config':10s} {'trades':>8} {'/wk':>5} {'win%':>6} {'net$':>9} {'expR':>7}")
    for name, params in CONFIGS.items():
        res = run_portfolio(lambda p=params: Ict2022(p), universe, s, e,
                            provider=prov, regime_series=regime, news_calendar=cal,
                            base_tf=TimeFrame.M5)
        print(f"{name:10s} {res.trade_count:8d} {res.trades_per_week:5.1f} {res.win_rate:6.0f} "
              f"{res.total_net:9.0f} {res.expectancy_r:+7.2f}")


if __name__ == "__main__":
    main()
