"""Local bar cache: Parquet for the bars, SQLite for a coverage index that drives gap-only
refetch.

One consolidated Parquet file per ``(provider, symbol, timeframe)`` holds all cached completed
bars; the SQLite ``bar_cache_index`` records which date ranges have been fetched so a repeat
request serves from disk and an extended request fetches only the missing tail. Only *completed*
bars are ever cached (the data layer drops the forming bar before writing).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.core.types import TimeFrame

NY_TZ = "America/New_York"

# Coverage ranges within this gap are treated as contiguous when coalescing, so tiny session
# boundaries (overnight, weekends) don't fragment the index into thousands of rows.
_COALESCE_GAP = pd.Timedelta(days=4)


def _to_ny(ts) -> pd.Timestamp:
    """Parse a (possibly stringified) timestamp into a tz-aware NY Timestamp."""
    t = pd.Timestamp(ts)
    return t.tz_localize(NY_TZ) if t.tz is None else t.tz_convert(NY_TZ)


class BarCache:
    """Parquet bar store keyed by ``(provider, symbol, timeframe)`` with a SQLite range index."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._db_path = self.root / "bar_cache_index.sqlite"
        self._init_db()

    # --- paths / db --------------------------------------------------------

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS bar_cache_index (
                    provider    TEXT NOT NULL,
                    symbol      TEXT NOT NULL,
                    timeframe   TEXT NOT NULL,
                    range_start TEXT NOT NULL,
                    range_end   TEXT NOT NULL,
                    n_bars      INTEGER NOT NULL,
                    updated_at  TEXT NOT NULL
                )
                """
            )

    def _parquet_path(self, provider: str, symbol: str, tf: TimeFrame) -> Path:
        return self.root / provider / symbol / f"{tf.value}.parquet"

    # --- coverage / gaps ---------------------------------------------------

    def _ranges(self, provider: str, symbol: str, tf: TimeFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        with sqlite3.connect(self._db_path) as con:
            rows = con.execute(
                "SELECT range_start, range_end FROM bar_cache_index "
                "WHERE provider=? AND symbol=? AND timeframe=? ORDER BY range_start",
                (provider, symbol, tf.value),
            ).fetchall()
        # Re-attach the named NY tz: round-tripping through SQLite as a string degrades the
        # zone to a fixed UTC offset, which later breaks tz-sensitive ops like ``date_range``.
        return [(_to_ny(a), _to_ny(b)) for a, b in rows]

    def covered_gaps(
        self, provider: str, symbol: str, tf: TimeFrame, start: datetime, end: datetime
    ) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        """Sub-ranges of ``[start, end]`` not yet covered by the index. Empty ⇒ full cache hit."""
        req_start, req_end = pd.Timestamp(start), pd.Timestamp(end)
        gaps: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        cursor = req_start
        for r_start, r_end in self._ranges(provider, symbol, tf):
            if r_end < cursor:
                continue
            if r_start > req_end:
                break
            if r_start > cursor:
                gaps.append((cursor, min(r_start, req_end)))
            cursor = max(cursor, r_end)
            if cursor >= req_end:
                break
        if cursor < req_end:
            gaps.append((cursor, req_end))
        return gaps

    # --- read / write ------------------------------------------------------

    def read(
        self, provider: str, symbol: str, tf: TimeFrame, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Cached bars in ``[start, end]`` (inclusive), or empty if nothing stored."""
        path = self._parquet_path(provider, symbol, tf)
        if not path.exists():
            from src.data.normalize import OHLCV_COLS

            return pd.DataFrame(columns=OHLCV_COLS, index=pd.DatetimeIndex([], tz=NY_TZ))
        df = pd.read_parquet(path)
        lo, hi = _to_ny(start), _to_ny(end)
        return df.loc[(df.index >= lo) & (df.index <= hi)]

    def write(
        self,
        provider: str,
        symbol: str,
        tf: TimeFrame,
        bars: pd.DataFrame,
        covered_start: datetime,
        covered_end: datetime,
    ) -> None:
        """Merge ``bars`` into the Parquet store and record ``[covered_start, covered_end]`` in
        the index. ``covered_*`` is the *requested* span (so empty-but-fetched ranges still count
        as covered and aren't re-fetched forever).
        """
        path = self._parquet_path(provider, symbol, tf)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists() and len(bars) > 0:
            existing = pd.read_parquet(path)
            merged = pd.concat([existing, bars])
            merged = merged.sort_index()
            merged = merged[~merged.index.duplicated(keep="last")]
        elif path.exists():
            merged = pd.read_parquet(path)
        else:
            merged = bars
        if len(merged) > 0:
            merged.to_parquet(path)

        self._record_range(provider, symbol, tf, covered_start, covered_end, len(bars))

    def _record_range(
        self,
        provider: str,
        symbol: str,
        tf: TimeFrame,
        start: datetime,
        end: datetime,
        n_bars: int,
    ) -> None:
        new_start, new_end = pd.Timestamp(start), pd.Timestamp(end)
        ranges = self._ranges(provider, symbol, tf)

        # Coalesce with any existing range it touches (within the slack gap).
        for r_start, r_end in ranges:
            if new_start <= r_end + _COALESCE_GAP and r_start <= new_end + _COALESCE_GAP:
                new_start = min(new_start, r_start)
                new_end = max(new_end, r_end)

        with sqlite3.connect(self._db_path) as con:
            con.execute(
                "DELETE FROM bar_cache_index WHERE provider=? AND symbol=? AND timeframe=?",
                (provider, symbol, tf.value),
            )
            # Re-insert the kept (non-overlapping) ranges plus the coalesced one.
            kept = [
                (s, e)
                for s, e in ranges
                if not (new_start <= e + _COALESCE_GAP and s <= new_end + _COALESCE_GAP)
            ]
            kept.append((new_start, new_end))
            now = pd.Timestamp.now(tz="UTC").isoformat()
            con.executemany(
                "INSERT INTO bar_cache_index "
                "(provider, symbol, timeframe, range_start, range_end, n_bars, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                [
                    (provider, symbol, tf.value, str(s), str(e), n_bars, now)
                    for s, e in sorted(kept)
                ],
            )
