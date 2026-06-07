---
id: exp-007
title: Daily-bias direction diagnostic (is the compass inverted?)
date: 2026-06-07
parents: [exp-002, exp-006]
status: done
verdict: FAILED
tweak: measure forward-return of daily_rebalance().direction; compare a close-confirmed candidate
data: 16 equities, yfinance D1, 2021–2024 (burned OOS)
metrics: {current_hit: "49-51%", current_t: "0.4-1.9", inverted: false, purge_revert_signed_bps: "+4 to +8 all 4 yrs"}
tags: [bias, diagnostic, R1]
---

## Hypothesis
If exp-006 is right, the current `daily_rebalance()` direction will **fail to predict** the day's
own return (and likely be net-negative when traded with), while a **close-confirmed** bias rule will
predict it better. Test before rebuilding any strategy code.

## Setup
`scripts/diag_bias_direction.py`. For each session day `t` per symbol:
- `bias = daily_rebalance(D1 bars strictly before t, price = open[t])` (causal).
- `realized = sign(close[t] − open[t])`; `signed_ret = bias.direction × (close[t]−open[t])/open[t]`.
- Pool across 16 equities, 2024. Report hit-rate and mean signed return (bps), **broken down by
  `basis`** (daily_fvg / purge_revert / pdh_pdl) to localize where the compass breaks.
- Reference columns: a **close-confirmed** candidate bias, and a naive **continuation** baseline.

## Result
Signed return = bias.direction × (open→close), bps/day. 16 equities, yfinance D1.

| year | current (hit / bps / t) | close_confirmed | continuation | **purge_revert basis** | daily_fvg | pdh_pdl |
|------|--------------------------|-----------------|--------------|------------------------|-----------|---------|
| 2021 | 50.6% / +1.2 / 0.51 | 48.4% / −6.7 / −2.47 | 48.7% / −5.0 | **+4.3 / 1.31** | +0.6 | −7.0 |
| 2022 | 49.2% / +4.3 / 1.21 | 51.9% / +5.5 / 1.44 | +1.2 / 0.33 | **+5.9 / 1.17** | −1.4 | +15.2 |
| 2023 | 50.1% / +4.7 / 1.90 | 51.1% / +4.9 / 1.75 | −3.3 / −1.34 | **+8.5 / 2.48** | +2.7 | −3.3 |
| 2024 | 51.2% / +1.0 / 0.43 | 50.2% / −0.1 / −0.05 | +0.9 / 0.36 | **+5.4 / 1.62** | −2.5 | −4.3 |

## Mechanism
- **[R1] inverted-compass: REJECTED.** Current bias is *not* backwards — signed return is small but
  **positive every year** and hit ≈ 50–51%. Counter-bias does **not** beat aligned at the daily
  horizon. exp-002's "counter beats aligned" did not reproduce here (it was likely specific to the
  intraday entry context, or noise). The doc's "weak proxy" call was right; "inverted" was wrong.
- **close-confirmed candidate: REJECTED.** Not robust — *negative* in 2021 (t=−2.47), positive in
  22/23. Simply "check the close" adds no consistent daily directional info.
- **NEW LEAD — the `purge_revert` (sweep-and-revert) component is the one consistent signal:**
  **+4 to +8 bps/day, positive in all four years** (t up to 2.48). The other two bases dilute it —
  `daily_fvg` is near-zero/noisy and **takes precedence in the current blend**, and `pdh_pdl` is
  unstable (−7 to +15). The engine waters down its best component. Note purge-revert *is* the
  "liquidity sweep → reverse" concept that is the user's core thesis; the FVG-draw and
  premium/discount reads are the noise around it.
- **Caveat:** open→close is a *coarse* proxy — the strategy takes an intraday R-multiple reversal
  trade gated by this bias, not a full-day hold. So this under-measures the bias's real use; the
  purge_revert consistency showing up *even in this coarse proxy* is the encouraging part.

## Branches (next nodes)
- **exp-008 (lead)** — isolate purge-revert as the bias (drop/demote daily_fvg precedence + pdh_pdl);
  re-measure here, then gate the *actual strategy* on it and check expectancy.
- exp-009 — weekly (W1) direction is still completely untested; add PWH/PWL weekly draw and measure.
- exp-010 — purge-revert × close-confirmation (does the failed-sweep subset sharpen the +bps further?).
