---
id: exp-009
title: Real intraday strategy baseline (keys live) + long/short split
date: 2026-06-07
parents: [exp-008]
status: done
verdict: WORKED
tweak: run the actual ict_2022 engine on 2021–24 breadth; split P&L by side
data: 16 equities (no crypto), 5m, 2021–2024, Alpaca IEX, default params
metrics: {long_4yr_net: +18500, short_4yr_net: -19700, blended_4yr_net: -1100}
tags: [baseline, breadth, shorts, long-only, KEY-FINDING]
---

## Hypothesis
Now that Alpaca keys work, stop using the daily open→close proxy and measure the *real* strategy.
exp-008 implied the short side is weak; the live engine should show where the P&L actually comes from.

## Setup
`/tmp/breadth_eq.py` (throwaway): `run_portfolio(Ict2022(), 16 equities, base_tf=M5)`, per year,
default params, equities only (crypto dropped — it's a known-negative confound and OOM-heavy here).
Per-year P&L split into long vs short. Each year run as its own process (parallel runs OOM/thrash).

## Result
| year | overall | long (n / win / net) | short (n / win / net) |
|---|---|---|---|
| 2021 (bull) | −0.056R | 15 / 20% / **−1,273** | 47 / 34% / −457 |
| 2022 (bear) | −0.102R | 40 / 30% / **+1,763** | 33 / 27% / **−5,502** |
| 2023 | +0.018R | 38 / 45% / **+10,027** | 48 / 19% / **−9,264** |
| 2024 (bull) | +0.114R | 26 / 50% / **+8,013** | 37 / 24% / **−4,432** |
| **4-yr** | **≈ −1,100** | **≈ +18,500** | **≈ −19,700** |

(Full breadth *with* crypto, 2024: −0.18R — crypto is a large drag; equities-only 2024 is +0.11R.)

## Mechanism
- **The short side loses in every single year, including the 2022 bear** (−5,502, 27% win). A
  reversal-short model that can't profit in a bear market is structurally broken, not regime-unlucky.
- **The long side is positive every year except the 2021 melt-up** (where the universe's high-flier
  names — TSLA/NVDA/AMD/NFLX — were topping, so "buy the dip" bled; the same effect exp-008 saw).
  Long win rate *climbs* 20→30→45→50%.
- **Longs (+18.5k) and shorts (−19.7k) nearly cancel** → the blended strategy reads ~breakeven. The
  "ICT has no edge" conclusion of Phase A–D was really "a profitable long book dragged to zero by a
  broken short book." This is consistent across exp-000, exp-008, and now the live engine.
- Equity upward drift is the likely root: fading rallies (short failed-high-sweeps) fights the drift.
  Open question: is shorting inherently wrong here, or is our *short setup detection* mis-built
  (asymmetric sweep/MSS/stop logic)? A top trader shorts indices fine.

## Caveats
- 2021–24 are burned OOS; "long-only" was *discovered* on them. But it's a robust, theory-backed
  structural read (drift + bear-market short failure), not a parameter fit → low overfit risk. The
  2025/26 holdout remains the real test.
- Frequency is LOW (1.2–1.7/wk both sides). Long-only ≈ halves it → ~0.6–0.8/wk. Thin; needs more
  breadth (universe size / full session) to reach the "few trades/week" target.
- Edge magnitude is modest; realistic execution + holdout could erode it.

## Branches (next nodes)
- **exp-010 (lead) — long-only** (drop or hard-gate shorts): expected ~all-years-positive ex-2021.
  Simplest, highest-impact, one toggle. Test on 2021–24, then check frequency cost.
- exp-011 — instead of deleting shorts, **gate shorts behind a genuine HTF-bearish condition**
  (weekly direction down + premium) — keeps real-downtrend shorts, kills random rally-fading.
- exp-012 — diagnose *why* shorts fail (is the short SETUP mis-built vs just drift?) before deleting.
