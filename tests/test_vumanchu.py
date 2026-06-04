"""Checkpoint 2.1b — VuManChu Cipher B and its reusable primitives.

Each building block (cross helpers, pivots, WaveTrend, money flow, divergences) is tested on its
own and proven causal, then the assembled ``cipher_b`` is proven causal as a whole.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators import classic
from src.indicators.causality import assert_causal
from src.indicators.common import crossover, crossunder, find_divergences, pivots
from src.indicators.vumanchu import cipher_b, money_flow, wavetrend

NY = "America/New_York"


def make_ohlcv(days=("2024-03-12", "2024-03-13", "2024-03-14", "2024-03-15"), seed=11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for d in days:
        idx = pd.date_range(f"{d} 09:30", f"{d} 15:55", freq="5min", tz=NY)
        n = len(idx)
        close = 100 + np.cumsum(rng.normal(0, 0.2, n))
        spread = rng.uniform(0.02, 0.3, n)
        frames.append(
            pd.DataFrame(
                {
                    "open": close + rng.normal(0, 0.05, n),
                    "high": np.maximum(close, close + spread),
                    "low": np.minimum(close, close - spread),
                    "close": close,
                    "volume": rng.integers(1_000, 5_000, n).astype(float),
                },
                index=idx,
            )
        )
    return pd.concat(frames)


# --- cross helpers ---------------------------------------------------------

def test_crossover_and_crossunder():
    a = pd.Series([1, 3, 1.0])  # crosses above 2 at t=1, below 2 at t=2
    b = pd.Series([2, 2, 2.0])
    assert crossover(a, b).tolist() == [False, True, False]
    assert crossunder(a, b).tolist() == [False, False, True]


# --- pivots ----------------------------------------------------------------

def test_pivot_confirmed_late_and_located():
    # A clear low at position 2; with left=right=2 it confirms at position 4.
    s = pd.Series([5, 4, 3, 4, 5, 6, 7.0])
    piv = pivots(s, left=2, right=2, high=False)
    assert piv["value"].iloc[4] == 3 and piv["src_pos"].iloc[4] == 2
    # Nothing confirmed at the pivot bar itself (that would be look-ahead).
    assert np.isnan(piv["value"].iloc[2])


def test_pivots_causal():
    df = make_ohlcv()
    assert_causal(lambda d: pivots(d["close"], 3, 3, high=True)["value"], df)
    assert_causal(lambda d: pivots(d["close"], 3, 3, high=False)["value"], df)


# --- wavetrend / money flow ------------------------------------------------

def test_wavetrend_causal():
    assert_causal(wavetrend, make_ohlcv())


def test_money_flow_causal():
    assert_causal(money_flow, make_ohlcv())


# --- divergence ------------------------------------------------------------

def test_regular_bullish_divergence_detected():
    # Oscillator low rises (3 -> 3.5) while price low falls (100 -> 98): regular bullish.
    osc = pd.Series([5, 4, 3, 4, 5, 6, 5, 4, 3.5, 4, 5, 6, 7.0])
    price = pd.Series([100, 100, 100, 100, 100, 100, 100, 100, 98, 98, 98, 98, 98.0])
    div = find_divergences(osc, price, left=2, right=2)
    assert div["regular_bullish"].iloc[10]  # confirmed at second pivot's confirmation bar (8+2)
    assert not div["regular_bullish"].iloc[:10].any()


def test_divergence_causal():
    df = make_ohlcv()
    wt2 = wavetrend(df)["wt2"]
    combined = pd.DataFrame({"osc": wt2, "px": df["close"]})
    assert_causal(lambda d: find_divergences(d["osc"], d["px"]), combined)


# --- classic additions used by Cipher B ------------------------------------

def test_mfi_and_stochrsi_causal():
    assert_causal(lambda d: classic.mfi(d, 14), make_ohlcv())
    assert_causal(lambda d: classic.stochrsi(d), make_ohlcv())


# --- full Cipher B ---------------------------------------------------------

def test_cipher_b_columns_and_types():
    out = cipher_b(make_ohlcv())
    for col in ["wt1", "wt2", "money_flow", "stochrsi_k", "stochrsi_d", "rsi",
                "buy", "sell", "gold_buy",
                "regular_bullish", "hidden_bullish", "regular_bearish", "hidden_bearish"]:
        assert col in out.columns
    for col in ["buy", "sell", "gold_buy", "regular_bullish"]:
        assert out[col].dtype == bool


def test_cipher_b_causal():
    assert_causal(cipher_b, make_ohlcv())
