"""``MultiTFClock`` — the no-look-ahead heart of multi-timeframe backtesting.

The engine steps over the lowest (base) timeframe. At each step it knows the wall-clock time
``now`` (the close of the just-completed base bar). The clock then answers, for any requested
higher timeframe, *which of its bars are already complete as of ``now``* — never the bar that is
still forming.

Higher timeframes are **resampled from the base stream** (see ``data.resample``), so they're always
consistent with what the engine has actually seen, and a higher bar appears only once all its base
bars are in. A bar opened at ``label`` closes at ``label + duration``; it's complete iff that close
time is ``<= now``. That single rule is what makes look-ahead impossible by construction.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.core.types import TimeFrame
from src.data.resample import resample_ohlcv

NY_TZ = "America/New_York"


def _bar_duration(tf: TimeFrame) -> pd.Timedelta:
    """Wall-clock span of one bar (for computing its close time from its open label)."""
    if tf is TimeFrame.W1:
        return pd.Timedelta(weeks=1)
    if tf is TimeFrame.D1:
        return pd.Timedelta(days=1)
    return pd.Timedelta(minutes=tf.minutes)


class MultiTFClock:
    """Serves completed bars of each required timeframe as of a given ``now``.

    Construct with the base bars (lowest TF) and the timeframes the strategy needs; higher ones are
    resampled from the base. Every requested timeframe must be >= the base timeframe.
    """

    def __init__(
        self,
        base_bars: pd.DataFrame,
        base_tf: TimeFrame,
        timeframes: list[TimeFrame],
    ) -> None:
        wanted = sorted(set(timeframes) | {base_tf}, key=lambda t: t.minutes)
        too_low = [t for t in wanted if t.minutes < base_tf.minutes]
        if too_low:
            raise ValueError(
                f"cannot serve timeframes below the base {base_tf.value}: {[t.value for t in too_low]}"
            )

        self.base_tf = base_tf
        self._frames: dict[TimeFrame, pd.DataFrame] = {}
        self._closes: dict[TimeFrame, pd.DatetimeIndex] = {}
        for tf in wanted:
            frame = base_bars if tf is base_tf else resample_ohlcv(base_bars, tf)
            self._frames[tf] = frame
            self._closes[tf] = frame.index + _bar_duration(tf)

    @property
    def timeframes(self) -> list[TimeFrame]:
        return sorted(self._frames, key=lambda t: t.minutes)

    def frame(self, tf: TimeFrame) -> pd.DataFrame:
        """The full resampled frame for ``tf`` (all bars, including not-yet-complete ones)."""
        return self._frames[tf]

    def completed(self, tf: TimeFrame, now: datetime) -> pd.DataFrame:
        """All bars of ``tf`` complete as of ``now`` (close time <= now). No forming bar."""
        now_ts = self._to_ny(now)
        return self._frames[tf][self._closes[tf] <= now_ts]

    def last(self, tf: TimeFrame, now: datetime):
        """The most recent completed bar of ``tf`` (pandas Series), or None if none yet."""
        done = self.completed(tf, now)
        return done.iloc[-1] if len(done) else None

    def window(self, tf: TimeFrame, now: datetime, n: int) -> pd.DataFrame:
        """The last ``n`` completed bars of ``tf`` as of ``now``."""
        return self.completed(tf, now).tail(n)

    @staticmethod
    def _to_ny(now: datetime) -> pd.Timestamp:
        t = pd.Timestamp(now)
        return t.tz_localize(NY_TZ) if t.tz is None else t.tz_convert(NY_TZ)
