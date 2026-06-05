"""Phase B.5.2 — crypto data path: 24/7 normalization (no RTH strip) + symbol→pair mapping.

Offline: no network. Verifies the central normalizer keeps overnight bars when rth=False, and the
Alpaca crypto symbol mapping (BTCUSD -> BTC/USD).
"""

from __future__ import annotations

import pandas as pd

from src.core.types import TimeFrame
from src.data.alpaca_crypto import _to_pair
from src.data.normalize import normalize_bars

NY = "America/New_York"


def _utc_bars(hours):
    idx = pd.date_range("2024-03-12 00:00", periods=hours, freq="1h", tz="UTC")
    return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)


def test_rth_false_keeps_overnight_bars():
    raw = _utc_bars(24)                      # a full UTC day, incl. hours outside US RTH
    rth_on = normalize_bars(raw, TimeFrame.H1, rth=True, now=pd.Timestamp("2024-03-13", tz=NY))
    rth_off = normalize_bars(raw, TimeFrame.H1, rth=False, now=pd.Timestamp("2024-03-13", tz=NY))
    assert len(rth_off) == 24                 # 24/7: every bar kept
    assert len(rth_on) < 24                   # equities: overnight stripped
    assert str(rth_off.index.tz) == NY        # still NY-tz canonical


def test_symbol_to_pair_mapping():
    assert _to_pair("BTCUSD") == "BTC/USD"
    assert _to_pair("ETHUSD") == "ETH/USD"
    assert _to_pair("SOLUSDT") == "SOL/USDT"
    assert _to_pair("BTC/USD") == "BTC/USD"   # already paired → pass-through
