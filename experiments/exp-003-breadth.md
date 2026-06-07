---
id: exp-003
title: Breadth (universe × full session) for frequency + pooled edge
date: 2026-06-05
parents: [exp-002]
status: done
verdict: INCONCLUSIVE
tweak: run the same fixed rule across ~16 equities + 8 crypto, pool the trades
data: 16 equities + 8 crypto, 5m, 2024
metrics: {trades_per_week: "3.6 eq / 6 +crypto", expectancy_r: +0.01}
tags: [breadth, portfolio]
---

## Hypothesis
Frequency comes from breadth (a universe × the full session), not from loosening quality; a portfolio
of A+ setups yields a few/week and a positive *pooled* edge. Breadth is also the anti-overfit defense.

## Setup
`src/backtest/portfolio.py` `run_portfolio`; crypto 24/7 data; DST fix. `scripts/run_breadth.py`.

## Result
Breadth **solves frequency** (3.6/wk equities, 6/wk +crypto) but pooled edge is **~breakeven
(+0.01R)**; crypto-in-NY-window negative (wrong session + %-notional cost).

## Mechanism
More trades of a ~zero-edge signal = more ~zero-edge trades. Frequency was never the real blocker.

## Branches (next nodes)
- exp-004 (SMT), exp-005 (news/regime) — both context layers on top of the signal.
