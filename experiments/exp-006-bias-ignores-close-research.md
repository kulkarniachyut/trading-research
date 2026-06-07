---
id: exp-006
title: "RESEARCH: our daily-bias engine ignores the daily close (R1)"
date: 2026-06-07
parents: [exp-002]
status: done
verdict: INCONCLUSIVE
tweak: read community mechanical-bias rules vs our _bias.py (no code run)
data: community sources + src/strategies/ict/ict_2022/_bias.py
metrics: {}
tags: [bias, research, R1]
---

## Hypothesis
The buried "counter-bias beats aligned" anomaly (exp-002) is not noise — our daily-bias engine is
**inverted on trend/continuation days** because it never checks the daily *close*.

## What the community actually does (mechanical daily bias)
The recurring rule across credible ICT sources keys on **the daily close relative to a swept level**:
- Sweep yesterday's **high** but **close back inside** the range → bias flips **bearish** (failed sweep).
- Sweep yesterday's **low** but **close back inside** → bias flips **bullish**.
- "Next-day model": a level is swept and price closes back inside → next day tends to run the opposite.
- Stated #1 error: reading bias off 15m/1h instead of the **daily/weekly** chart. The close is the
  confirmation; the wick alone is not.

## What our `daily_rebalance()` does (the gap)
Purge & revert keys off a **wick penetration** — `last["low"] < prior["low"]` — and **never checks the
daily close.** A trend-down day that breaks PDL and *closes at its lows* (bearish continuation) is
mislabeled as a bullish "purge & revert → draw up." That inversion mechanically reproduces exp-002's
anomaly: if the compass is inverted on continuation days, aligned trades lose and counter wins.

Also: **no weekly (W1) timeframe exists** (`required_timeframes = [M5, M15, H1, D1]`); PWH/PWL weekly
draw is absent, though the community treats weekly as the dominant gate.

## Mechanism
A broken compass explains "directional edge ≈ noise" better than any missing *filter* (SMT/news/
regime — exp-004/005). Those were all layers on top of the signal; none tested the signal itself.

## Branches (next nodes)
- exp-007 — diagnostic: prove/kill the inversion before rebuilding (measure forward return of the
  current bias direction, vs a close-confirmed candidate, on a burned year).

Sources: ttrades.com (mechanical daily bias), innercircletrader.net, tradingfinder.com.
