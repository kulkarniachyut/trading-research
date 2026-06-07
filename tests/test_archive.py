"""Tests for the durable Databento archive + the offline provider that reads it.

Covers: 1m round-trip + idempotent merge, scope routing by year, holdout sealing, and that the
provider derives higher timeframes from the canonical 1m without any network access.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.core.types import TimeFrame
from src.data import archive
from src.data.databento_provider import DatabentoProvider

NY = "America/New_York"


def _synthetic_1m(day: str, n: int = 120) -> pd.DataFrame:
    """A monotonic n-minute 1m OHLCV frame starting 09:30 NY on ``day``."""
    idx = pd.date_range(f"{day} 09:30", periods=n, freq="1min", tz=NY)
    base = np.arange(n, dtype=float)
    return pd.DataFrame(
        {"open": base, "high": base + 0.5, "low": base - 0.5, "close": base + 0.25,
         "volume": np.full(n, 100.0)},
        index=idx,
    )


@pytest.fixture
def archive_root(tmp_path, monkeypatch):
    """Redirect the archive at module level so tests never touch the committed data."""
    root = tmp_path / "databento"
    monkeypatch.setattr(archive, "ARCHIVE_ROOT", root)
    monkeypatch.setattr(archive, "MANIFEST_PATH", root / "manifest.json")
    return root


def test_scope_routing_by_year():
    assert archive.scope_for_year(2023) == archive.REFERENCE
    assert archive.scope_for_year(2024) == archive.REFERENCE
    assert archive.scope_for_year(2025) == archive.HOLDOUT
    assert archive.scope_for_year(2026) == archive.HOLDOUT


def test_write_read_roundtrip_and_idempotent_merge(archive_root):
    bars = _synthetic_1m("2023-06-01")
    archive.write_1m("ES.c.0", bars, archive.REFERENCE)

    back = archive.read_1m("ES.c.0", archive.REFERENCE)
    assert len(back) == len(bars)
    assert str(back.index.tz) == NY
    pd.testing.assert_frame_equal(back, bars, check_freq=False)

    # Re-writing an overlapping range must not duplicate rows.
    total = archive.write_1m("ES.c.0", bars, archive.REFERENCE)
    assert total == len(bars)


def test_read_for_range_slices_and_seals_holdout(archive_root):
    archive.write_1m("ES.c.0", _synthetic_1m("2023-06-01"), archive.REFERENCE)
    archive.write_1m("ES.c.0", _synthetic_1m("2025-06-01"), archive.HOLDOUT)

    span = (pd.Timestamp("2023-01-01", tz=NY), pd.Timestamp("2026-01-01", tz=NY))

    # Default: holdout invisible even though the range covers 2025.
    ref_only = archive.read_for_range("ES.c.0", *span)
    assert ref_only.index.max().year == 2023

    # Opt in: holdout now included.
    with_holdout = archive.read_for_range("ES.c.0", *span, allow_holdout=True)
    assert with_holdout.index.max().year == 2025


def test_provider_derives_higher_timeframe_from_1m(archive_root, tmp_path):
    archive.write_1m("ES.c.0", _synthetic_1m("2023-06-01", n=60), archive.REFERENCE)
    prov = DatabentoProvider(cache_dir=tmp_path / "cache")

    m5 = prov.get_bars("ES.c.0", TimeFrame.M5,
                       pd.Timestamp("2023-06-01", tz=NY), pd.Timestamp("2023-06-02", tz=NY))
    assert len(m5) == 12  # 60 one-minute bars roll up into 12 five-minute bars
    # First 5m bar aggregates minutes 0..4: open=first, high=max, low=min, close=last.
    first = m5.iloc[0]
    assert first["open"] == 0.0
    assert first["close"] == 4.25
    assert first["volume"] == 500.0


def test_provider_seals_holdout_by_default(archive_root, tmp_path):
    archive.write_1m("ES.c.0", _synthetic_1m("2025-06-01"), archive.HOLDOUT)
    prov = DatabentoProvider(cache_dir=tmp_path / "cache")
    span = (pd.Timestamp("2025-06-01", tz=NY), pd.Timestamp("2025-06-02", tz=NY))

    with pytest.raises(RuntimeError, match="archive"):
        prov.get_bars("ES.c.0", TimeFrame.M5, *span)

    allowed = DatabentoProvider(cache_dir=tmp_path / "cache2", allow_holdout=True)
    bars = allowed.get_bars("ES.c.0", TimeFrame.M5, *span)
    assert len(bars) > 0


def test_manifest_reflects_disk(archive_root):
    archive.write_1m("ES.c.0", _synthetic_1m("2023-06-01"), archive.REFERENCE)
    archive.write_1m("NQ.c.0", _synthetic_1m("2025-06-01"), archive.HOLDOUT)
    manifest = archive.write_manifest()

    assert manifest["coverage"][archive.REFERENCE]["ES.c.0"]["rows"] == 120
    assert manifest["coverage"][archive.HOLDOUT]["NQ.c.0"]["rows"] == 120
    assert archive.MANIFEST_PATH.exists()
