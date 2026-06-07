---
id: exp-004
title: SMT divergence confluence
date: 2026-06-05
parents: [exp-003]
status: done
verdict: FAILED
tweak: require_smt toggle (timed, biased SMT vs ctx.ref)
data: equities, 5m, 2024
metrics: {expectancy_r_lift: "+0.01 → +0.02"}
tags: [smt, confluence]
---

## Hypothesis
SMT divergence (one symbol sweeps a level while its correlate doesn't) adds marginal directional edge.

## Setup
`MarketContext.ref()` multi-symbol architecture; `require_smt`. `scripts/exp_smt.py`.

## Result
**No marginal lift** (+0.01 → +0.02R; diluted by stock↔own-index pairs).

## Mechanism
A confluence filter cannot rescue a directional signal that is itself ~zero/inverted.

## Branches (next nodes)
- Revisit SMT *after* the bias signal is fixed (it may help a working compass; it can't fix a broken one).
