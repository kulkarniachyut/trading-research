"""VuManChu Cipher B — the full composite, assembled from reusable primitives.

This module is deliberately thin: it *composes* standalone pieces rather than reimplementing them,
so each part stays independently usable:
- ``wavetrend.wavetrend``        — the WT1/WT2 momentum waves (the backbone)
- ``money_flow`` (below)         — VuManChu's RSI+MFI area (green/red)
- ``classic.stochrsi`` / ``rsi`` — confirmation oscillators
- ``utils.crossover/crossunder`` — WT cross detection
- ``divergence.find_divergences``— regular/hidden divergences on the WaveTrend

Everything is causal (each primitive is proven causal on its own), so ``cipher_b`` is causal too.
Reproduces the *behavior* of the TradingView script; exact decimals will differ (EMA seeding etc.).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators import classic
from src.indicators.divergence import find_divergences
from src.indicators.utils import crossover, crossunder
from src.indicators.wavetrend import wavetrend


def money_flow(df: pd.DataFrame, period: int = 60, multiplier: float = 150.0) -> pd.Series:
    """VuManChu's RSI+MFI area: ``SMA(((close-open)/(high-low)) * multiplier, period)``.
    Positive = buying pressure (green), negative = selling (red). Causal (trailing SMA)."""
    rng = (df["high"] - df["low"]).to_numpy(dtype=float)
    body = (df["close"] - df["open"]).to_numpy(dtype=float)
    ratio = np.where(rng != 0, body / rng, 0.0) * multiplier
    s = pd.Series(ratio, index=df.index)
    return s.rolling(period).mean().rename("money_flow")


def cipher_b(
    df: pd.DataFrame,
    *,
    channel_len: int = 9,
    average_len: int = 12,
    ma_len: int = 3,
    oversold: float = -53.0,
    overbought: float = 53.0,
    mfi_period: int = 60,
    mfi_multiplier: float = 150.0,
    rsi_period: int = 14,
    div_left: int = 3,
    div_right: int = 3,
) -> pd.DataFrame:
    """Full Cipher B as a DataFrame aligned to ``df.index``.

    Columns: ``wt1, wt2, money_flow, stochrsi_k, stochrsi_d, rsi`` (values) and the signal flags
    ``buy, sell, gold_buy`` plus the four divergence columns. Buy/sell = WT cross in the
    oversold/overbought zone; ``gold_buy`` = oversold buy confirmed by a regular bullish divergence
    and a low RSI (the classic "yellow/gold" setup, simplified).
    """
    wt = wavetrend(df, channel_len=channel_len, average_len=average_len, ma_len=ma_len)
    wt1, wt2 = wt["wt1"], wt["wt2"]

    mf = money_flow(df, period=mfi_period, multiplier=mfi_multiplier)
    srsi = classic.stochrsi(df)
    rsi = classic.rsi(df, period=rsi_period)

    cross_up = crossover(wt1, wt2)
    cross_down = crossunder(wt1, wt2)
    buy = cross_up & (wt2 <= oversold)
    sell = cross_down & (wt2 >= overbought)

    div = find_divergences(wt2, df["close"], left=div_left, right=div_right)
    gold_buy = buy & div["regular_bullish"] & (rsi < 30)

    out = pd.DataFrame(
        {
            "wt1": wt1,
            "wt2": wt2,
            "money_flow": mf,
            "stochrsi_k": srsi["stochrsi_k"],
            "stochrsi_d": srsi["stochrsi_d"],
            "rsi": rsi,
            "buy": buy,
            "sell": sell,
            "gold_buy": gold_buy,
        },
        index=df.index,
    )
    return out.join(div)
