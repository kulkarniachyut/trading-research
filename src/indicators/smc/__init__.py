"""Smart Money Concepts (ICT) indicators — wraps the ``smartmoneyconcepts`` library into
normalized, **causal** columns (FVG, order blocks, liquidity, swings, BOS/CHoCH).

Populated in Checkpoint 2.2. The library's swing/structure functions look ahead (repaint), so the
wrapper lags confirmations and every output is run through ``indicators.causality.assert_causal``.
"""
