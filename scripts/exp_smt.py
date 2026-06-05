"""Phase C measurement — does SMT divergence (require_smt) lift the equity breadth edge?

Toggle test on the equity universe (crypto's NY-window confound is excluded — see breadth finding):
run the same selective ict_2022 with SMT off vs on, each symbol confirmed against a correlated
reference (tech→QQQ, broad/sector→SPY). Reports frequency + pooled expectancy for each. A real
confluence raises expectancy (fewer, higher-quality setups); a useless one just cuts trades.
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.portfolio import UniverseItem, run_portfolio
from src.core.types import TimeFrame
from src.data.alpaca import AlpacaProvider
from src.strategies.ict.ict_2022 import Ict2022

EQUITIES = ["SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN",
            "META", "GOOGL", "TSLA", "AMD", "NFLX", "JPM", "XLE", "GLD"]
REFERENCES = {
    "SPY": "QQQ", "QQQ": "SPY", "IWM": "SPY", "DIA": "SPY", "JPM": "SPY", "XLE": "SPY", "GLD": "SPY",
    "AAPL": "QQQ", "MSFT": "QQQ", "NVDA": "QQQ", "AMZN": "QQQ", "META": "QQQ",
    "GOOGL": "QQQ", "TSLA": "QQQ", "AMD": "QQQ", "NFLX": "QQQ",
}


def _run(params, prov, universe, refs, start, end):
    return run_portfolio(lambda: Ict2022(params), universe, start, end,
                         provider=prov, references=refs, base_tf=TimeFrame.M5)


def main() -> None:
    years = sys.argv[1:] or ["2024"]
    prov = AlpacaProvider()
    universe = [UniverseItem(s) for s in EQUITIES]
    for yr in years:
        s = pd.Timestamp(f"{yr}-01-01", tz="America/New_York")
        e = pd.Timestamp(f"{yr}-12-31", tz="America/New_York")
        off = _run({}, prov, universe, REFERENCES, s, e)
        on = _run({"require_smt": True}, prov, universe, REFERENCES, s, e)
        print(f"\n=== SMT toggle, equities {yr} ===")
        print(f"{'':10s} {'trades':>8} {'/wk':>5} {'win%':>6} {'net$':>9} {'expR':>7}")
        for name, r in (("SMT off", off), ("SMT on", on)):
            print(f"{name:10s} {r.trade_count:8d} {r.trades_per_week:5.1f} {r.win_rate:6.0f} "
                  f"{r.total_net:9.0f} {r.expectancy_r:+7.2f}")


if __name__ == "__main__":
    main()
