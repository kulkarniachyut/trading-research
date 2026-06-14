"""VMC Cipher B trend-gated strategy (go-wide crypto brick).

cipher_b and its primitives are proven causal in test_vumanchu.py; this file proves the *strategy*
behavior through the real engine: it fires a long on a WaveTrend buy inside an uptrend, and the
200-EMA trend gate blocks the same buy signals in a downtrend (the part naked IBS lacked). Uses a
relaxed ``oversold`` so a small synthetic series triggers — the rule, not the exact threshold, is
under test (real crypto routinely drives wt2 past the -53 default).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import src.strategies  # noqa: F401  (imports buckets -> registers strategies)
from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import TimeFrame
from src.strategies.base import get_strategy, list_strategies
from src.strategies.vumanchu.cipher_strategy import VmcCipher

NY = "America/New_York"

# relaxed so a short series triggers; short trend EMA so the gate is meaningful on few bars
PARAMS = {"decision_tf": "4h", "oversold": -15.0, "trend_len": 20, "atr_period": 5,
          "max_hold_bars": 6}


def _sawtooth(n: int, drift: float) -> pd.DataFrame:
    """H4 bars: a linear-drift baseline with periodic sharp V-dips (recovery bars are green).

    The dips drive WaveTrend negative; the cross-up out of the dip is the Cipher B ``buy``.
    ``drift`` > 0 keeps price above the trend EMA (entries allowed); < 0 is a downtrend (gated)."""
    idx = pd.date_range("2022-01-01", periods=n, freq="4h", tz=NY)
    base = 100 + drift * np.arange(n)
    saw = np.zeros(n)
    green = np.zeros(n, bool)
    for i in range(0, n, 18):
        for j, amp in enumerate([-3, -8, -14, -9, -2]):
            if i + j < n:
                saw[i + j] = amp
        if i + 5 < n:
            green[i + 5] = True
    close = base + saw
    op = close.copy()
    op[green] = close[green] - 2.0  # close > open -> green body -> money_flow turns positive
    return pd.DataFrame(
        {"open": op, "high": np.maximum(op, close) + 0.5, "low": np.minimum(op, close) - 0.5,
         "close": close, "volume": 1000.0},
        index=idx,
    )


def _engine() -> BacktestEngine:
    inst = InstrumentSpec("BTCUSD", Market("US", AssetClass.CRYPTO, Product.INTRADAY),
                          multiplier=1.0, tick_size=0.01)
    return BacktestEngine(cost_model("US", "crypto"), inst,
                          initial_equity=100_000.0, risk_pct=0.005, max_leverage=2.0)


def _run(bars: pd.DataFrame, params: dict | None = None):
    return _engine().run(VmcCipher({**PARAMS, **(params or {})}), bars, TimeFrame.H4)


def test_registered() -> None:
    assert "vmc_cipher" in list_strategies()
    assert get_strategy("vmc_cipher") is VmcCipher


def test_fires_long_in_uptrend_with_dips() -> None:
    res = _run(_sawtooth(200, drift=0.2))
    assert len(res.trades) >= 1
    t = res.trades[0]
    assert t.side == "long"
    assert t.reason_in.startswith("vmc_buy")


def test_trend_gate_blocks_dips_in_downtrend() -> None:
    # Same dip structure (buy signals exist) but a falling baseline: close stays below the EMA,
    # so the trend gate must veto every entry.
    res = _run(_sawtooth(200, drift=-0.2))
    assert res.trades == []


def test_money_flow_gate_can_be_disabled() -> None:
    # Ablation hook works: turning off the money-flow confirmation never reduces entries.
    with_mf = _run(_sawtooth(200, drift=0.2), {"require_money_flow": True})
    without_mf = _run(_sawtooth(200, drift=0.2), {"require_money_flow": False})
    assert len(without_mf.trades) >= len(with_mf.trades)
