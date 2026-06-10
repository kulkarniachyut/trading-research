"""Step 4, family 3 — the IBS mean-reversion strategy.

Constructed daily sequences must produce: a long when a day closes near its low above the trend
MA, no entry below the MA (trend gate), an IBS exit when strength returns, a time exit after
``max_hold_days``, and correct IBS math. H1 base / D1 decisions through the real engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import src.strategies  # noqa: F401  (imports buckets -> registers strategies)
from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import TimeFrame
from src.strategies.base import get_strategy, list_strategies
from src.strategies.meanrev.ibs import IbsRev, ibs

NY = "America/New_York"

# tiny windows so tests need few synthetic days
PARAMS = {"trend_ma": 5, "atr_period": 3, "atr_stop": 3.0, "max_hold_days": 5}


def _h1_days(start: str, days: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """6 H1 bars per day shaped so the daily rollup gives exactly (open, high, low, close)."""
    frames = []
    day0 = pd.Timestamp(start, tz=NY).normalize()
    for d, (o, h, lo, c) in enumerate(days):
        idx = pd.date_range(day0 + pd.Timedelta(days=d, hours=9), periods=6, freq="1h", tz=NY)
        opens = np.array([o, h, h, lo, lo, c])
        closes = np.array([h, h, lo, lo, c, c])
        highs = np.maximum(opens, closes)
        lows = np.minimum(opens, closes)
        frames.append(pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": 1000.0},
            index=idx))
    return pd.concat(frames)


def _engine() -> BacktestEngine:
    inst = InstrumentSpec("ES.c.0", Market("US", AssetClass.FUTURE, Product.FUTURES),
                          multiplier=5.0, tick_size=0.25)
    return BacktestEngine(cost_model("US", "future"), inst,
                          initial_equity=100_000.0, risk_pct=0.005, max_leverage=10.0)


def _run(bars: pd.DataFrame, params: dict | None = None):
    return _engine().run(IbsRev({**PARAMS, **(params or {})}), bars, TimeFrame.H1)


def _flat_days(n: int, px: float = 100.0) -> list[tuple[float, float, float, float]]:
    return [(px, px + 1, px - 1, px)] * n  # IBS 0.5 — no signal


def test_registered_and_ibs_math() -> None:
    assert "ibs_rev" in list_strategies()
    assert get_strategy("ibs_rev") is IbsRev
    bar = pd.Series({"high": 110.0, "low": 100.0, "close": 102.0})
    assert abs(ibs(bar) - 0.2) < 1e-9
    assert ibs(pd.Series({"high": 100.0, "low": 100.0, "close": 100.0})) == 0.5


def test_buys_dip_above_trend_and_exits_on_strength() -> None:
    days = _flat_days(6)
    days.append((100.0, 101.0, 95.0, 95.5))   # IBS=(95.5-95)/6≈0.08 <= 0.2, close > MA? 95.5 < ~100 MA...
    # keep the dip mild so close stays above the 5d MA: lows at 99, close 99.1
    days[-1] = (100.0, 100.5, 99.0, 99.1)     # IBS=(99.1-99)/1.5≈0.067, MA5≈100 -> 99.1 < MA. Fails gate.
    # put the trend higher first: rise then dip
    days = [(100 + d, 101 + d, 99 + d, 100.5 + d) for d in range(6)]  # uptrend, IBS≈0.75
    days.append((106.0, 106.5, 104.0, 104.2))  # IBS=0.08, close 104.2 > MA5(≈103.5)
    days.append((104.2, 106.0, 104.0, 105.9))  # strong close, IBS=0.95 -> exit
    days.append((106.0, 107.0, 105.0, 106.0))  # spare day so the exit fill bar exists
    res = _run(_h1_days("2022-03-07", days))
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.side == "long"
    assert t.reason_out == "signal"
    assert t.reason_in.startswith("ibs_buy")


def test_trend_gate_blocks_dips_in_downtrend() -> None:
    days = [(110 - 2 * d, 111 - 2 * d, 108 - 2 * d, 108.2 - 2 * d) for d in range(8)]  # down, IBS low
    res = _run(_h1_days("2022-03-07", days))
    assert res.trades == []


def test_time_exit_after_max_hold() -> None:
    days = [(100 + d, 101 + d, 99 + d, 100.5 + d) for d in range(6)]   # uptrend warm-up
    days.append((106.0, 106.5, 104.0, 104.2))                          # dip -> entry
    days += [(104.0, 104.6, 103.6, 104.0)] * 7                         # IBS≈0.4 — never strong
    res = _run(_h1_days("2022-03-07", days), {"max_hold_days": 3})
    assert len(res.trades) == 1
    assert res.trades[0].reason_out == "signal"
    assert "_d3" in str(res.trades[0].reason_in) or res.trades[0].bars_held <= 6 * 5
