"""Diagnostic harness: run ict_2022 on real historical SPY/QQQ 5m bars and report results.

Not a unit test — a throwaway calibration tool. Pulls via yfinance (no keys), runs the engine,
and prints trade count / win rate / post-cost net so we can sanity-check the recalibration.
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import TimeFrame
from src.data.alpaca import AlpacaProvider
from src.strategies.ict.ict_2022 import Ict2022


def summarize(symbol: str, res, params: dict) -> None:
    trades = res.trades
    n = len(trades)
    wins = [t for t in trades if t.net_pnl > 0]
    net = sum(t.net_pnl for t in trades)
    gross = sum(t.gross_pnl for t in trades)
    costs = sum(t.costs for t in trades)
    wr = (len(wins) / n * 100) if n else 0.0
    eq = res.equity_curve
    ret = (eq.iloc[-1] / eq.iloc[0] - 1) * 100 if len(eq) else 0.0
    print(f"\n=== {symbol} ===")
    print(f"  trades        : {n}")
    print(f"  win rate      : {wr:.1f}%")
    print(f"  gross PnL     : {gross:,.0f}")
    print(f"  costs         : {costs:,.0f}")
    print(f"  net PnL       : {net:,.0f}")
    print(f"  equity return : {ret:.2f}%")
    if n:
        by_out: dict[str, int] = {}
        for t in trades:
            by_out[t.reason_out] = by_out.get(t.reason_out, 0) + 1
        print(f"  exits         : {by_out}")
        avg_bars = sum(t.bars_held for t in trades) / n
        print(f"  avg bars held : {avg_bars:.1f}")
        longs = [t for t in trades if t.side == "long"]
        shorts = [t for t in trades if t.side == "short"]
        for label, grp in (("long", longs), ("short", shorts)):
            if grp:
                gw = sum(1 for t in grp if t.net_pnl > 0)
                gnet = sum(t.net_pnl for t in grp)
                print(f"  {label:5s}: {len(grp):3d} trades  {gw/len(grp)*100:4.0f}% win  net {gnet:8.0f}")
        avg_win = sum(t.net_pnl for t in wins) / len(wins) if wins else 0.0
        losers = [t for t in trades if t.net_pnl <= 0]
        avg_loss = sum(t.net_pnl for t in losers) / len(losers) if losers else 0.0
        print(f"  avg win/loss  : {avg_win:.0f} / {avg_loss:.0f}  (expectancy {net/n:.1f}/trade)")


def run(symbol: str, bars: pd.DataFrame, params: dict | None = None):
    inst = InstrumentSpec(symbol, Market("US", AssetClass.EQUITY, Product.INTRADAY))
    eng = BacktestEngine(cost_model("US", "equity"), inst, initial_equity=100_000.0, risk_pct=0.005)
    strat = Ict2022(params or {})
    return eng.run(strat, bars, TimeFrame.M5)


def load(prov, sym: str, start: str, end: str) -> pd.DataFrame:
    s = pd.Timestamp(start, tz="America/New_York")
    e = pd.Timestamp(end, tz="America/New_York")
    return prov.get_bars(sym, TimeFrame.M5, s, e)


def main() -> None:
    # usage: diag_ict_2022.py [SYM ...] [--start YYYY-MM-DD --end YYYY-MM-DD]
    args = sys.argv[1:]
    start, end = "2022-01-01", "2024-12-31"
    if "--start" in args:
        start = args[args.index("--start") + 1]
    if "--end" in args:
        end = args[args.index("--end") + 1]
    symbols = [a for a in args if not a.startswith("--") and a not in (start, end)] or ["SPY", "QQQ"]
    prov = AlpacaProvider()
    for sym in symbols:
        print(f"\nPulling {sym} 5m {start} -> {end} (alpaca IEX) ...")
        try:
            bars = load(prov, sym, start, end)
        except Exception as e:  # noqa: BLE001
            print(f"  fetch failed: {e}")
            continue
        print(f"  got {len(bars)} bars  [{bars.index[0]} .. {bars.index[-1]}]")
        res = run(sym, bars)
        summarize(sym, res, res.params)


if __name__ == "__main__":
    main()
