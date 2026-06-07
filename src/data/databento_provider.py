"""Databento data provider — CME futures bars, served **offline from the committed archive**.

The instruments the ICT 2022 model was actually built for: two-sided, drift-neutral, 23h index
and FX/metal futures (ES/NQ/YM/RTY, 6E/6B/6J/6A, GC), where — unlike drifting single-name equities —
the *short* side is not structurally doomed (see exp-012/exp-014/exp-015).

**This provider never hits the network.** Databento historical is metered against finite free credits,
so all paid fetching is funnelled through ``scripts/data_pull.py`` (the one online path), which banks
canonical **1-minute** bars into the committed archive (``src/data/archive.py``). Here we just read
that archive and resample to whatever timeframe the engine asks for — so backtests are reproducible,
offline, and free, and don't even need the ``databento`` package installed.

Sealed behind the same ``DataProvider`` contract as Alpaca/yfinance: implements only ``_fetch_raw``;
the base class caches into ``data/cache/``, normalizes (the archive is already NY-tz), and drops the
forming bar. Futures trade ~23h → no RTH filter (``rth = False``).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from src.core.types import TimeFrame
from src.data import archive
from src.data.base import DataProvider
from src.data.resample import resample_ohlcv

_NOT_ARCHIVED_MSG = (
    "No archived Databento 1m bars for {symbol} over [{start} .. {end}]"
    "{holdout_hint}. Backtests read only the committed archive (data/archive/databento/) — they "
    "never spend credits. Pull it once with:  uv run python scripts/data_pull.py "
    "--symbols {symbol} --years <YYYY-YYYY> --yes"
)


class DatabentoProvider(DataProvider):
    """Offline reader over the committed 1-minute Databento archive.

    Every requested timeframe is derived from the canonical 1m series, so adding a timeframe costs
    nothing. Pass ``allow_holdout=True`` only for the final 2025/26 validation — by default the
    reserved holdout scope is invisible even if the requested range extends into it.
    """

    key = "databento"
    rth = False  # CME futures run ~23h — no RTH filtering

    def __init__(self, cache_dir: Optional[str | Path] = None, *, allow_holdout: bool = False) -> None:
        self._allow_holdout = allow_holdout
        super().__init__(cache_dir=cache_dir)

    def _fetch_raw(
        self, symbol: str, timeframe: TimeFrame, start: datetime, end: datetime
    ) -> pd.DataFrame:
        m1 = archive.read_for_range(symbol, start, end, allow_holdout=self._allow_holdout)
        if m1.empty:
            hint = "" if self._allow_holdout else " (holdout 2025+ is sealed; pass allow_holdout=True if intended)"
            raise RuntimeError(
                _NOT_ARCHIVED_MSG.format(symbol=symbol, start=start, end=end, holdout_hint=hint)
            )
        # Canonical atom is 1m; everything higher is a local rollup.
        return m1 if timeframe is TimeFrame.M1 else resample_ohlcv(m1, timeframe)
