---
id: exp-001
title: Cheaper instrument (futures economics) flips the edge
date: 2026-06-05
parents: [exp-000]
status: done
verdict: FAILED
tweak: re-price SPY/QQQ proxy into futures (MNQ/MES) cost space, matched leverage
data: SPY/QQQ RTH proxy → index-point space, 2021–2024
metrics: {gross_net: -3997, cost_cut: "-44%", flipped: false}
tags: [costs, instrument]
---

## Hypothesis
Tight 5m R makes cost a large fraction of R; futures (≈$2.24 RT/MNQ) might flip the breakeven edge.

## Setup
Futures cost preset + CME micro registry; scale-invariant strategy re-priced into index points with
matched leverage → identical trades, isolating cost. `scripts/exp_futures.py`.

## Result
Futures roughly **halve cost** ($14,651 → $8,163). But **gross P&L is −$3,997 before any cost.**
Cheaper cost cut the loss (−18,649 → −13,160), could not flip it.

## Mechanism
The signal is net-negative *gross*. Cost is not the binding constraint.

## Branches (next nodes)
- exp-002 — fix the signal via selectivity. (Keep futures as the cheaper execution vehicle.)
