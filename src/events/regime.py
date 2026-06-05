"""Macro risk regime — the yen-carry-style risk-off detector (Phase D, toggle).

A coarse market-wide tag ("risk_on" / "risk_off") from VIX. Strategies can stand down in risk-off
(when sweeps fail and volatility expansion runs stops both ways). Built once and shared across the
universe — it is a *market* state, not per-symbol.

Causality: day T's regime uses VIX through **T-1** (a 1-day shift), so an intraday bar on day T
never peeks at that day's VIX close. The tag is session-dated, so ``Series.asof(now)`` returns the
regime in force for the bar's day.
"""

from __future__ import annotations

import pandas as pd


def vix_regime(vix_close: pd.Series, threshold: float = 20.0) -> pd.Series:
    """Map a daily VIX close series → a session-dated regime tag series.

    ``risk_off`` when the prior session's VIX closed above ``threshold`` (elevated fear), else
    ``risk_on``. The input index is treated as session dates (tz-aware NY midnight from the D1
    provider); the output shares it so intraday ``asof`` lookups land on the right day.
    """
    if vix_close is None or len(vix_close) == 0:
        return pd.Series(dtype=object)
    prior = vix_close.shift(1)  # causal: today's regime uses yesterday's close
    tags = prior.map(lambda v: "risk_off" if pd.notna(v) and v > threshold else "risk_on")
    tags.name = "regime"
    return tags


def fetch_vix_regime(start, end, *, threshold: float = 20.0, provider=None) -> pd.Series:
    """Convenience: pull ^VIX daily (yfinance — no keys) and build the regime series."""
    from src.core.types import TimeFrame

    if provider is None:
        from src.data.yfinance_provider import YFinanceProvider

        provider = YFinanceProvider()
    vix = provider.get_bars("^VIX", TimeFrame.D1, start, end)
    return vix_regime(vix["close"], threshold=threshold)
