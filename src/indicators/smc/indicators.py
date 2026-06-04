"""Smart Money Concepts (ICT) indicators — thin wrappers over the ``smartmoneyconcepts`` library,
normalized to our snake_case convention and aligned to the input index.

We deliberately use the library's *exact* logic (it's the battle-tested reference for these
definitions) rather than reimplementing it. Functions that need swings compute them internally,
so callers just pass an OHLCV frame.

CAUSALITY CONTRACT — read this:
- These wrap the library faithfully, which means the **full-series** output *repaints*: a swing is
  confirmed ``swing_length`` bars late, an FVG's ``*_mitigated_index`` points to a future bar, etc.
- The look-ahead-safe way to use them is to read the **current (last) bar** of a past-only window —
  which is exactly what the event-driven engine provides (``ctx.bars()`` = completed bars only).
- To precompute a causal feature column outside the engine (analysis/plotting), wrap any of these
  with ``smc.causal.causal_apply`` — it runs them bar-by-bar on past-only windows.
- Columns ending in ``_index`` (mitigated/broken) are forward references — hindsight-only.
"""

from __future__ import annotations

import pandas as pd
from smartmoneyconcepts import smc as _smc


def _normalize(out: pd.DataFrame, mapping: dict[str, str], index: pd.Index) -> pd.DataFrame:
    """Rename library columns to our convention and re-attach the source index (row-aligned)."""
    out = out.rename(columns=mapping)[list(mapping.values())].copy()
    out.index = index
    return out


def swings(df: pd.DataFrame, swing_length: int = 50) -> pd.DataFrame:
    """Swing highs/lows. Columns: ``swing`` (+1 high / -1 low), ``swing_level`` (price)."""
    out = _smc.swing_highs_lows(df, swing_length=swing_length)
    return _normalize(out, {"HighLow": "swing", "Level": "swing_level"}, df.index)


def fvg(df: pd.DataFrame, join_consecutive: bool = False) -> pd.DataFrame:
    """Fair value gaps. Columns: ``fvg`` (+1 bull / -1 bear), ``fvg_top``, ``fvg_bottom``,
    ``fvg_mitigated_index`` (forward reference — hindsight-only)."""
    out = _smc.fvg(df, join_consecutive=join_consecutive)
    return _normalize(
        out,
        {"FVG": "fvg", "Top": "fvg_top", "Bottom": "fvg_bottom", "MitigatedIndex": "fvg_mitigated_index"},
        df.index,
    )


def bos_choch(df: pd.DataFrame, swing_length: int = 50, close_break: bool = True) -> pd.DataFrame:
    """Break of structure / change of character. Columns: ``bos`` (+1/-1), ``choch`` (+1/-1),
    ``structure_level``, ``broken_index`` (forward reference)."""
    sw = _smc.swing_highs_lows(df, swing_length=swing_length)
    out = _smc.bos_choch(df, sw, close_break=close_break)
    return _normalize(
        out,
        {"BOS": "bos", "CHOCH": "choch", "Level": "structure_level", "BrokenIndex": "broken_index"},
        df.index,
    )


def order_blocks(df: pd.DataFrame, swing_length: int = 50, close_mitigation: bool = False) -> pd.DataFrame:
    """Order blocks. Columns: ``ob`` (+1 bull / -1 bear), ``ob_top``, ``ob_bottom``,
    ``ob_volume``, ``ob_mitigated_index`` (forward ref), ``ob_percentage``."""
    sw = _smc.swing_highs_lows(df, swing_length=swing_length)
    out = _smc.ob(df, sw, close_mitigation=close_mitigation)
    return _normalize(
        out,
        {
            "OB": "ob",
            "Top": "ob_top",
            "Bottom": "ob_bottom",
            "OBVolume": "ob_volume",
            "MitigatedIndex": "ob_mitigated_index",
            "Percentage": "ob_percentage",
        },
        df.index,
    )


def liquidity(df: pd.DataFrame, swing_length: int = 50, range_percent: float = 0.01) -> pd.DataFrame:
    """Liquidity pools (equal highs/lows). Columns: ``liquidity`` (+1/-1), ``liq_level``,
    ``liq_end`` (forward ref), ``liq_swept`` (forward ref)."""
    sw = _smc.swing_highs_lows(df, swing_length=swing_length)
    out = _smc.liquidity(df, sw, range_percent=range_percent)
    return _normalize(
        out,
        {"Liquidity": "liquidity", "Level": "liq_level", "End": "liq_end", "Swept": "liq_swept"},
        df.index,
    )


def previous_high_low(df: pd.DataFrame, time_frame: str = "1D") -> pd.DataFrame:
    """Prior-period high/low (e.g. previous day). Columns: ``prev_high``, ``prev_low``,
    ``broken_high``, ``broken_low``."""
    out = _smc.previous_high_low(df, time_frame=time_frame)
    return _normalize(
        out,
        {"PreviousHigh": "prev_high", "PreviousLow": "prev_low", "BrokenHigh": "broken_high", "BrokenLow": "broken_low"},
        df.index,
    )
