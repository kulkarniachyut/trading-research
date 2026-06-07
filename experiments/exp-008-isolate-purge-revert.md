---
id: exp-008
title: Isolate + sharpen the purge-revert (sweep→reversal) bias
date: 2026-06-07
parents: [exp-007]
status: done
verdict: INCONCLUSIVE
tweak: drop FVG/pdh_pdl blend; test purge-revert alone, + close-confirmation, + side-split
data: 16 equities, yfinance D1, 2021–2024 (burned OOS), open→close proxy
metrics: {purge_revert_only: "+1.9/+4.6/+6.0/+2.8 (all + )", purge_revert_close: "-6.4/+14.9/+15.0/+3.8", edge_side: long}
tags: [bias, purge-revert, sweep, regime]
---

## Hypothesis
The purge-revert (liquidity-sweep→reverse) component is the only consistently positive daily-direction
signal (exp-007); isolating it from the diluting FVG-draw + PDH/PDL fallback — and adding the
top-trader "show me rejection" filter (a sweep only counts if it CLOSED back inside) — should sharpen it.

## Setup
`scripts/diag_bias_direction.py` extended with `purge_revert_only`, `purge_revert_close`
(failed-sweep: closed back inside → revert, else stand aside), `purge_revert_cont`, and a long/short
side-split. Same open→close signed-return proxy across 16 equities, 2021–24.

## Result
signed return (bps/day), all years:

| variant | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|
| current (blend) | +1.0 | +4.3 | +4.7 | +1.0 |
| **purge_revert_only** | +1.9 | +4.6 | +6.0 | +2.8 | ← positive every year |
| **purge_revert_close** | **−6.4** | **+14.9** | **+15.0** | +3.8 | ← big, but fragile |

Side-split of `purge_revert_close` (long = buy failed-low-sweep; short = sell failed-high-sweep):
- 2021: long **−8.7 bps** / 48% · short +4.5 bps (wrong sign) / 49%
- 2023: long **+29.3 bps / 56%** · short −0.6 bps / 47%

## Mechanism
- **Isolation helps consistency:** `purge_revert_only` is positive in all four years (vs the blend's
  noise) — confirms the FVG-draw + PDH/PDL legs were diluting the one real component. Small (+2–6 bps).
- **Close-confirmation amplifies but adds fragility:** `purge_revert_close` is +15 bps in 2022/23 but
  −6 in 2021. Not a free win.
- **The edge is the LONG side; the short side is ~dead.** Selling failed-high-sweeps doesn't work on
  upward-drifting equities (echoes exp-000 "shorts lose every regime"). Buying failed-low-sweeps is
  the signal — +29 bps/56% in 2023 — but **regime/selection dependent** (negative 2021, likely because
  the high-flier names in the universe were topping under the index melt-up → "buy the dip" bled).
- **Caveat unchanged:** open→close is a coarse proxy for an intraday R-multiple reversal trade. These
  numbers say "there is a small, mostly-long sweep-reversal signal," not "here is the tradeable edge."

## Did anything change? Yes.
Isolating purge-revert beats the current blend, and the long-side failed-low-sweep is a real (if
regime-sensitive) signal. But it is **not** a standalone edge — it needs (a) to drop the dead short
side / gate direction by HTF bias, and (b) selection that isn't long names that are topping. Both
point at the same missing piece: **HTF (weekly) directional context** — the user's core thesis.

## Branches (next nodes)
- exp-009 — **with Alpaca keys now live**, stop using the daily proxy: test the REAL intraday strategy.
  Re-baseline ict_2022 on 2021–24 breadth, then apply the exp-008 read (close-confirmed sweep +
  long/HTF-gated) and see if post-cost expectancy moves off breakeven.
- exp-010 — add weekly (W1) direction gate (PWH/PWL draw); only take reversals with the weekly bias.
- exp-011 — sweep REAL liquidity (equal highs/lows, PDL/PWL, session range) instead of a generic pivot.
