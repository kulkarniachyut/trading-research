---
id: exp-000
title: Mechanical ICT baseline (ict_2022 first-touch OTE)
date: 2026-06-05
parents: []
status: done
verdict: FAILED
tweak: root finding — the wired mechanical model, no edge-hunting yet
data: SPY,QQQ 5m; IS=2023, OOS=2021/22/24 (Alpaca IEX)
metrics: {expectancy_r: ~0, win_rate: "22-39%", note: "shorts lose every regime"}
tags: [baseline, bias]
---

## Hypothesis
The faithfully-wired ICT 2022 model (daily-narrative-gated sweep → MSS/displacement → OTE/FVG entry)
has a post-cost edge on SPY/QQQ 5m.

## Setup
`ict_2022` flagship, default params, single-symbol engine. Calibrated on 2023, validated on untouched
2021/22/24. Diagnostics: `scripts/diag_ict_2022.py`, `diag_mfe.py`, `exp_ict.py`, `exp_validate.py`.

## Result
Win 22–39% across regimes; **shorts lose in every regime, incl. the 2022 bear.** MFE: setups reach
+1R only ~43–66% of the time, +2R only ~24–34%, with targets at ~2.3R → win rate sits *just below*
cost-adjusted breakeven at every R:R. The 2023 "winner" overfit (−2970 in 2022 OOS).

## Mechanism
Directional edge ≈ noise; costs are a large fraction of the tight 5m R → reliably net-negative.
"More model, not more tuning."

## Branches (next nodes)
- exp-001 (instrument/cost), exp-002 (time/selectivity), exp-003 (breadth), exp-004 (SMT), exp-005 (news/regime).
