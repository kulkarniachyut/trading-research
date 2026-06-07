---
id: exp-002
title: Time precision + displacement selectivity
date: 2026-06-05
parents: [exp-000]
status: done
verdict: FAILED
tweak: Silver-Bullet entry window + min_disp_strength floor (2.5×ATR)
data: SPY,QQQ 5m, 2021–24, gross R
metrics: {silver_bullet_R: +0.22, strong_disp_R: +0.12, single_symbol_net: negative}
tags: [time, selectivity, bias, ANOMALY]
---

## Hypothesis
Narrowing to Silver Bullet (10–11 ET) + a displacement-strength floor concentrates the edge enough
to go net-positive.

## Setup
Formation/entry-window split, `min_disp_strength`. `scripts/diag_edge_pockets.py`, `exp_phaseb.py`.

## Result
Edge **concentrates where theory predicts** — Silver-Bullet entries **+0.22R**, strong displacement
**+0.12R** vs ~flat overall. BUT the selective config still ran **net-negative** single-symbol
(180→61 trades, bleed cut ~40%, not flipped).

## Mechanism
Selectivity removes bad trades but single-symbol frequency collapses before reaching positive
expectancy after fills.

## ⚠️ Buried anomaly (the lead we are now chasing)
Diagnostics showed **"counter-bias beats aligned"** — trades *against* our computed `daily_bias` did
better than aligned ones. Dismissed at the time as "our daily_bias is a weak proxy; not built on."
**This may be the real signal, not an artifact** — see exp-006 / exp-007.

## Branches (next nodes)
- exp-003 (breadth, for frequency), exp-006 (RESEARCH: is the bias compass inverted?).
