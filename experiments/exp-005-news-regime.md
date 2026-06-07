---
id: exp-005
title: News / macro-regime filters
date: 2026-06-05
parents: [exp-003]
status: done
verdict: FAILED
tweak: block_risk_off (VIX) + block_news_day (FOMC/NFP) toggles
data: equities, 5m, 2024
metrics: {both_filters: "hurt expectancy"}
tags: [news, regime, catalyst]
---

## Hypothesis
Standing down on risk-off / high-impact-news days improves expectancy.

## Setup
VIX `block_risk_off`, FOMC/NFP `block_news_day`. `scripts/exp_events.py`.

## Result
Both filters **hurt**. The setup is volatility-expansion and *likes* risk-off / news days.

## Mechanism
News/risk-off are **catalysts, not filters** — they create the very liquidity-engineering moves ICT
trades. Gating them out removes the best days.

## Branches (next nodes)
- Later: use news/risk-off as a *catalyst* (lean in), not a veto — but only once the compass works.
