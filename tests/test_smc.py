"""Checkpoint 2.2 — SMC wrappers + the causal bridge.

Two things matter here:
1. The wrappers faithfully expose the library's signals under our normalized column names.
2. The library output *repaints* on the full series (proven), but ``causal_apply`` turns it into a
   look-ahead-safe feature column (proven with the causality guard). This is the contract that lets
   us use authentic SMC signals without cheating.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.indicators import smc
from src.indicators.causality import assert_causal

NY = "America/New_York"


def make_ohlcv(days=("2024-03-11", "2024-03-12", "2024-03-13", "2024-03-14"), seed=5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for d in days:
        idx = pd.date_range(f"{d} 09:30", f"{d} 15:55", freq="5min", tz=NY)
        n = len(idx)
        close = 100 + np.cumsum(rng.normal(0, 0.25, n))
        sp = rng.uniform(0.05, 0.4, n)
        frames.append(
            pd.DataFrame(
                {
                    "open": close + rng.normal(0, 0.05, n),
                    "high": np.maximum(close, close + sp),
                    "low": np.minimum(close, close - sp),
                    "close": close,
                    "volume": rng.integers(1_000, 5_000, n).astype(float),
                },
                index=idx,
            )
        )
    return pd.concat(frames)


# --- wrappers expose normalized columns, aligned to the input index --------

def test_wrappers_normalized_columns_and_alignment():
    df = make_ohlcv()
    cases = [
        (smc.fvg(df), ["fvg", "fvg_top", "fvg_bottom", "fvg_mitigated_index"]),
        (smc.swings(df, swing_length=10), ["swing", "swing_level"]),
        (smc.bos_choch(df, swing_length=10), ["bos", "choch", "structure_level", "broken_index"]),
        (smc.order_blocks(df, swing_length=10),
         ["ob", "ob_top", "ob_bottom", "ob_volume", "ob_mitigated_index", "ob_percentage"]),
        (smc.liquidity(df, swing_length=10), ["liquidity", "liq_level", "liq_end", "liq_swept"]),
        (smc.previous_high_low(df), ["prev_high", "prev_low", "broken_high", "broken_low"]),
    ]
    for out, cols in cases:
        assert list(out.columns) == cols
        assert out.index.equals(df.index)  # row-aligned to the source bars


# --- the heart of it: raw SMC repaints, causal_apply fixes it --------------

def test_raw_swings_repaint_but_causal_apply_is_causal():
    df = make_ohlcv()

    # Raw, full-series swings look ahead → the guard must flag them.
    with pytest.raises(AssertionError, match="causality violated"):
        assert_causal(lambda d: smc.swings(d, swing_length=10)["swing_level"], df)

    # Run causally (engine-style, past-only windows) → now it passes the guard.
    def causal_swing_level(d: pd.DataFrame) -> pd.Series:
        return smc.causal_apply(lambda w: smc.swings(w, swing_length=10), d, lookback=60)["swing_level"]

    assert_causal(causal_swing_level, df)


def test_causal_apply_aligns_and_keeps_columns():
    df = make_ohlcv()
    out = smc.causal_apply(lambda w: smc.fvg(w), df, lookback=60)
    assert out.index.equals(df.index)
    assert list(out.columns) == ["fvg", "fvg_top", "fvg_bottom", "fvg_mitigated_index"]
