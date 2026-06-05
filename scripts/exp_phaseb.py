"""Phase B measurement — does concentrating to the Silver-Bullet window + strong displacement
turn ict_2022 net-positive? Compares the old broad config vs the new selective defaults on the
SPY/QQQ proxy (equity + futures economics), 2021–2024 (reference; 2025/26 reserved for Phase E).

NOTE: the pocket was *chosen* on 2021–24, so this is in-sample confirmation that the config
captures it, not OOS proof. OOS verdict is Phase E on the untouched holdout.
"""

from __future__ import annotations

import sys

import pandas as pd

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.instruments import micro_future
from src.backtest.simulator import BacktestEngine
from src.core.types import TimeFrame
from src.data.alpaca import AlpacaProvider
from src.strategies.ict.ict_2022 import Ict2022

BROAD = {"killzones": [("09:30", "11:30"), ("13:30", "15:30")], "entry_killzones": None,
         "min_disp_strength": 0.0}
SELECTIVE: dict = {}   # = new defaults (form 09:30–11:00, enter 10–11, min_disp_strength 2.5)
PAIRS = [("SPY", "MES"), ("QQQ", "MNQ")]
YEARS = ["2021", "2022", "2023", "2024"]


def _net(res):
    n = len(res.trades)
    net = sum(t.net_pnl for t in res.trades)
    wins = sum(1 for t in res.trades if t.net_pnl > 0)
    return n, (wins / n * 100 if n else 0.0), net


def _run(params, etf, fut, bars):
    eq_inst = InstrumentSpec(etf, Market("US", AssetClass.EQUITY, Product.INTRADAY))
    eq = BacktestEngine(cost_model("US", "equity"), eq_inst, 100_000.0, risk_pct=0.005, max_leverage=4.0)
    mf = micro_future(fut)
    scaled = bars.copy()
    for c in ("open", "high", "low", "close"):
        scaled[c] = scaled[c] * mf.proxy_factor
    ft = BacktestEngine(cost_model("US", "future"), mf.instrument(), 100_000.0, risk_pct=0.005, max_leverage=4.0)
    return _net(eq.run(Ict2022(params), bars, TimeFrame.M5)), _net(ft.run(Ict2022(params), scaled, TimeFrame.M5))


def main() -> None:
    years = sys.argv[1:] or YEARS
    prov = AlpacaProvider()
    print(f"\n=== Phase B: broad vs selective (SB 10–11 + strong disp), {years[0]}..{years[-1]} ===")
    print(f"{'pair':10s} {'year':5s} | {'broad n/win/eqNet/futNet':>30s} | {'selective n/win/eqNet/futNet':>30s}")
    tot = {"b_eq": 0.0, "b_ft": 0.0, "s_eq": 0.0, "s_ft": 0.0, "b_n": 0, "s_n": 0}
    for etf, fut in PAIRS:
        for yr in years:
            bars = prov.get_bars(etf, TimeFrame.M5, pd.Timestamp(f"{yr}-01-01", tz="America/New_York"),
                                 pd.Timestamp(f"{yr}-12-31", tz="America/New_York"))
            (beq, bft) = _run(BROAD, etf, fut, bars)
            (seq, sft) = _run(SELECTIVE, etf, fut, bars)
            tot["b_eq"] += beq[2]
            tot["b_ft"] += bft[2]
            tot["b_n"] += beq[0]
            tot["s_eq"] += seq[2]
            tot["s_ft"] += sft[2]
            tot["s_n"] += seq[0]
            print(f"{etf}->{fut:5s} {yr:5s} | {beq[0]:3d}/{beq[1]:3.0f}%/{beq[2]:6.0f}/{bft[2]:6.0f}        "
                  f"| {seq[0]:3d}/{seq[1]:3.0f}%/{seq[2]:6.0f}/{sft[2]:6.0f}")
    print(f"\nBROAD     trades {tot['b_n']:4d}  equity_net {tot['b_eq']:8.0f}  futures_net {tot['b_ft']:8.0f}")
    print(f"SELECTIVE trades {tot['s_n']:4d}  equity_net {tot['s_eq']:8.0f}  futures_net {tot['s_ft']:8.0f}")


if __name__ == "__main__":
    main()
