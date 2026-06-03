"""Step 1 verification — the data layer's correctness guarantees:

- normalization: tz -> America/New_York, RTH filter (intraday only), sort/de-dupe
- no look-ahead: the trailing forming bar is dropped unless explicitly requested
- caching: a repeat pull hits cache (0 refetch); an extended pull fetches only the gap
- calendar: holidays have no session; early-close half-days truncate RTH
- the Alpaca provider fails loudly when keys are absent

All offline/deterministic via a synthetic ``MockProvider``. The one live pull (Alpaca IEX) is
marked ``network`` — skipped by default, and skipped if Alpaca keys aren't configured.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from src.core.types import TimeFrame
from src.data import calendar
from src.data.base import DataProvider
from src.data.normalize import OHLCV_COLS, normalize_bars

NY = "America/New_York"


# --------------------------------------------------------------------------
# synthetic raw-bar builders + a counting MockProvider
# --------------------------------------------------------------------------

def make_intraday_raw(start_ny: str, end_ny: str, freq: str = "5min") -> pd.DataFrame:
    """UTC-indexed raw bars with capitalized columns (to exercise normalization)."""
    idx = pd.date_range(start=start_ny, end=end_ny, freq=freq, tz=NY).tz_convert("UTC")
    n = len(idx)
    return pd.DataFrame(
        {
            "Open": range(n),
            "High": [i + 1 for i in range(n)],
            "Low": [i - 1 for i in range(n)],
            "Close": [i + 0.5 for i in range(n)],
            "Volume": [100 * (i + 1) for i in range(n)],
        },
        index=idx,
    )


class MockProvider(DataProvider):
    """Generates deterministic daily bars and counts every ``_fetch_raw`` call."""

    key = "mock"

    def __init__(self, cache_dir):
        super().__init__(cache_dir=cache_dir)
        self.fetch_calls: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    def _fetch_raw(self, symbol, timeframe, start, end):
        self.fetch_calls.append((pd.Timestamp(start), pd.Timestamp(end)))
        idx = pd.date_range(start=start, end=end, freq="D")  # tz-aware NY (from base)
        n = len(idx)
        return pd.DataFrame(
            {
                "open": range(n),
                "high": [i + 1 for i in range(n)],
                "low": [i - 1 for i in range(n)],
                "close": [i + 0.5 for i in range(n)],
                "volume": [1000] * n,
            },
            index=idx,
        )


# --------------------------------------------------------------------------
# normalization: tz + RTH
# --------------------------------------------------------------------------

def test_normalize_tz_and_rth():
    # 2024-03-15 (a normal Friday): premarket -> after-hours in NY.
    raw = make_intraday_raw("2024-03-15 08:00", "2024-03-15 17:00")
    out = normalize_bars(raw, TimeFrame.M5, now=pd.Timestamp("2030-01-01", tz=NY))

    assert list(out.columns) == OHLCV_COLS
    assert str(out.index.tz) == NY
    assert out.index.is_monotonic_increasing
    assert not out.index.has_duplicates
    # RTH only: first bar 09:30, last RTH 5m bar opens 15:55 (16:00 is excluded, half-open).
    assert out.index.min().strftime("%H:%M") == "09:30"
    assert out.index.max().strftime("%H:%M") == "15:55"
    # a premarket 09:00 bar must be gone
    assert not ((out.index.hour == 9) & (out.index.minute == 0)).any()


def test_normalize_dedupe_and_sort():
    raw = make_intraday_raw("2024-03-15 13:30", "2024-03-15 15:00")
    shuffled = pd.concat([raw.iloc[::-1], raw.iloc[[0]]])  # reversed + a duplicate of row 0
    out = normalize_bars(shuffled, TimeFrame.M5, now=pd.Timestamp("2030-01-01", tz=NY))
    assert out.index.is_monotonic_increasing
    assert not out.index.has_duplicates


def test_daily_bars_not_rth_filtered():
    idx = pd.DatetimeIndex(["2024-03-11", "2024-03-12", "2024-03-13"])  # naive session dates
    raw = pd.DataFrame(
        {"open": [1, 2, 3], "high": [1, 2, 3], "low": [1, 2, 3],
         "close": [1, 2, 3], "volume": [9, 9, 9]},
        index=idx,
    )
    out = normalize_bars(raw, TimeFrame.D1, now=pd.Timestamp("2030-01-01", tz=NY))
    assert len(out) == 3
    assert str(out.index.tz) == NY


# --------------------------------------------------------------------------
# no look-ahead: the forming bar is dropped
# --------------------------------------------------------------------------

def test_forming_bar_dropped_by_default():
    raw = make_intraday_raw("2024-03-15 09:30", "2024-03-15 11:00")  # NY RTH bars
    now = pd.Timestamp("2024-03-15 11:02", tz=NY)  # bar opened 11:00 closes 11:05 > now -> forming

    completed = normalize_bars(raw, TimeFrame.M5, now=now)
    assert completed.index.max().strftime("%H:%M") == "10:55"  # 11:00 bar dropped

    with_forming = normalize_bars(raw, TimeFrame.M5, include_forming=True, now=now)
    assert with_forming.index.max().strftime("%H:%M") == "11:00"  # kept on request


# --------------------------------------------------------------------------
# caching: hit on repeat + gap-only refetch
# --------------------------------------------------------------------------

def test_cache_hit_and_gap_only_refetch(tmp_path):
    prov = MockProvider(cache_dir=tmp_path)
    s1, e1 = datetime(2024, 1, 2), datetime(2024, 1, 31)

    first = prov.get_bars("SPY", TimeFrame.D1, s1, e1)
    assert len(first) > 0
    assert len(prov.fetch_calls) == 1  # one gap fetched

    # identical pull -> served entirely from cache, no refetch
    prov.get_bars("SPY", TimeFrame.D1, s1, e1)
    assert len(prov.fetch_calls) == 1

    # extend the window -> only the new tail [2024-01-31, 2024-02-29] is fetched
    prov.get_bars("SPY", TimeFrame.D1, s1, datetime(2024, 2, 29))
    assert len(prov.fetch_calls) == 2
    gap_start, gap_end = prov.fetch_calls[1]
    assert gap_start >= pd.Timestamp("2024-01-31", tz=NY)
    assert gap_end <= pd.Timestamp("2024-02-29", tz=NY) + pd.Timedelta(days=1)


# --------------------------------------------------------------------------
# calendar: holidays + early close
# --------------------------------------------------------------------------

def test_calendar_skips_holiday():
    # 2024-01-01 New Year's Day = market closed; 2024-01-02 open.
    sess = calendar.sessions(datetime(2024, 1, 1), datetime(2024, 1, 3))
    assert pd.Timestamp("2024-01-01") not in sess
    assert pd.Timestamp("2024-01-02") in sess
    assert not calendar.is_session_open(pd.Timestamp("2024-01-01 12:00", tz=NY))


def test_calendar_early_close_truncates_rth():
    # 2024-07-03 is a 1pm early close. 12:00 is in session; 14:00 is after the early close.
    idx = pd.DatetimeIndex(
        [pd.Timestamp("2024-07-03 12:00", tz=NY), pd.Timestamp("2024-07-03 14:00", tz=NY)]
    )
    mask = calendar.rth_mask(idx)
    assert bool(mask.iloc[0]) is True
    assert bool(mask.iloc[1]) is False


# --------------------------------------------------------------------------
# alpaca: clear error when keys are missing
# --------------------------------------------------------------------------

def test_alpaca_missing_keys_raises(monkeypatch, tmp_path):
    import src.data.alpaca as alpaca_mod

    monkeypatch.setattr(alpaca_mod, "alpaca_credentials", lambda: None)
    with pytest.raises(RuntimeError, match="Alpaca API keys not found"):
        alpaca_mod.AlpacaProvider(cache_dir=tmp_path)


# --------------------------------------------------------------------------
# live Alpaca IEX pull (opt-in)
# --------------------------------------------------------------------------

@pytest.mark.network
def test_alpaca_live_contract(tmp_path):
    from src.core.config import alpaca_credentials
    from src.data.alpaca import AlpacaProvider

    if alpaca_credentials() is None:
        pytest.skip("Alpaca keys not configured (.env / config/secrets.yaml)")

    prov = AlpacaProvider(cache_dir=tmp_path)
    end = pd.Timestamp.now(tz=NY)
    start = end - pd.Timedelta(days=7)
    df = prov.get_bars("SPY", TimeFrame.M5, start.to_pydatetime(), end.to_pydatetime())

    assert len(df) > 0
    assert list(df.columns) == OHLCV_COLS
    assert str(df.index.tz) == NY
    assert df.index.is_monotonic_increasing
    assert not df.index.has_duplicates
    assert df.index.min().strftime("%H:%M") >= "09:30"
    assert df.index.max().strftime("%H:%M") <= "16:00"
