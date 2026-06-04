"""Classic technical indicators — thin, **causal** wrappers over TA-Lib (plus a couple hand-rolled
where TA-Lib has no session-aware version).

Strategies import indicators ONLY from this module, never from ``talib`` directly, so the TA
backend stays swappable and every indicator is guaranteed **causal** — its value at bar ``t`` uses
only bars ``<= t`` (no peeking at the future). That guarantee is proven for each function by
``tests/test_indicators.py`` using ``src/indicators/causality.py``.

Input: an OHLCV DataFrame (lowercase columns ``open/high/low/close/volume``, tz-aware NY index,
as produced by the data layer). Output: a pandas Series (or DataFrame for multi-line indicators)
aligned to ``df.index``, with NaN during the warm-up period.
"""

from __future__ import annotations

import pandas as pd
import talib


def _f(df: pd.DataFrame, col: str):
    return df[col].to_numpy(dtype=float)


def ema(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Exponential moving average of close."""
    return pd.Series(talib.EMA(_f(df, "close"), timeperiod=period), index=df.index, name=f"ema_{period}")


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average true range — volatility in price units."""
    out = talib.ATR(_f(df, "high"), _f(df, "low"), _f(df, "close"), timeperiod=period)
    return pd.Series(out, index=df.index, name=f"atr_{period}")


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Relative strength index (0-100)."""
    return pd.Series(talib.RSI(_f(df, "close"), timeperiod=period), index=df.index, name=f"rsi_{period}")


def bollinger(df: pd.DataFrame, period: int = 20, n_std: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands: SMA mid +/- ``n_std`` standard deviations."""
    upper, mid, lower = talib.BBANDS(
        _f(df, "close"), timeperiod=period, nbdevup=n_std, nbdevdn=n_std, matype=0
    )
    return pd.DataFrame({"bb_upper": upper, "bb_mid": mid, "bb_lower": lower}, index=df.index)


def donchian(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Donchian channel: rolling highest-high / lowest-low over the trailing ``period`` bars
    (inclusive of the current bar — causal). Strategies wanting a prior-bar breakout level can
    use the engine's completed-bar view rather than shifting here."""
    upper = df["high"].rolling(period).max()
    lower = df["low"].rolling(period).min()
    return pd.DataFrame({"dc_upper": upper, "dc_lower": lower, "dc_mid": (upper + lower) / 2.0})


def vwap(df: pd.DataFrame) -> pd.Series:
    """Session-anchored VWAP: cumulative typical-price*volume / cumulative volume, **reset each
    trading day** (NY calendar date). Causal — only bars at or before ``t`` within the session."""
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical * df["volume"]
    session = df.index.normalize()  # NY date = session anchor
    cum_pv = pv.groupby(session).cumsum()
    cum_vol = df["volume"].groupby(session).cumsum()
    return (cum_pv / cum_vol).rename("vwap")
