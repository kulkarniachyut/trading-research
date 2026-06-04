"""Checkpoint 2.1 — classic indicators are causal (no look-ahead) and numerically sane.

The headline test is causality: for every indicator, its value at bar t must not change when
future bars are removed. We also prove the guard itself works by feeding it a deliberately
future-peeking function and asserting it gets caught.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.indicators import classic
from src.indicators.causality import assert_causal

NY = "America/New_York"


def make_ohlcv(days=("2024-03-13", "2024-03-14", "2024-03-15"), freq="5min", seed=7) -> pd.DataFrame:
    """Synthetic but realistic intraday RTH bars across several NY sessions (random walk)."""
    rng = np.random.default_rng(seed)
    frames = []
    for d in days:
        idx = pd.date_range(f"{d} 09:30", f"{d} 15:55", freq=freq, tz=NY)
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


# --- causality (the important one) ----------------------------------------

@pytest.mark.parametrize(
    "fn",
    [
        lambda d: classic.ema(d, 20),
        lambda d: classic.atr(d, 14),
        lambda d: classic.rsi(d, 14),
        lambda d: classic.bollinger(d, 20, 2.0),
        lambda d: classic.donchian(d, 20),
        classic.vwap,
    ],
    ids=["ema", "atr", "rsi", "bollinger", "donchian", "vwap"],
)
def test_indicator_is_causal(fn):
    assert_causal(fn, make_ohlcv())


def test_guard_catches_a_lookahead_indicator():
    """A function that reads the NEXT bar must be flagged — proves the guard actually bites."""
    def future_peek(df: pd.DataFrame) -> pd.Series:
        return df["close"].shift(-1).rename("peek")  # uses bar t+1 → look-ahead

    with pytest.raises(AssertionError, match="causality violated"):
        assert_causal(future_peek, make_ohlcv())


# --- numerical sanity ------------------------------------------------------

def test_ema_of_constant_is_constant():
    df = make_ohlcv()
    df["close"] = 50.0
    assert np.isclose(classic.ema(df, 10).iloc[-1], 50.0)


def test_rsi_bounded_0_100():
    r = classic.rsi(make_ohlcv(), 14).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_bollinger_ordering():
    bb = classic.bollinger(make_ohlcv(), 20, 2.0).dropna()
    assert (bb["bb_upper"] >= bb["bb_mid"]).all()
    assert (bb["bb_mid"] >= bb["bb_lower"]).all()


def test_vwap_resets_each_session():
    df = make_ohlcv()
    v = classic.vwap(df)
    # On the first bar of a session, VWAP == that bar's typical price (cumulative just started).
    second_day = pd.Timestamp("2024-03-14", tz=NY)
    first_bar = df[df.index.normalize() == second_day].iloc[0]
    typical = (first_bar["high"] + first_bar["low"] + first_bar["close"]) / 3.0
    assert np.isclose(v.loc[df.index.normalize() == second_day].iloc[0], typical)
