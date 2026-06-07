---
id: exp-013
title: Indices/ETFs only (drop individual stocks) — instrument test B
date: 2026-06-07
parents: [exp-012]
status: done
verdict: WORKED
tweak: restrict universe to SPY/QQQ/IWM/DIA (drop 14 single names)
data: 4 index ETFs, 5m, 2021–2024, Alpaca IEX, default params
metrics: {exp_r: "+0.39/+0.23/+0.25/-0.24", shorts_recovered: true, freq_per_wk: 0.2}
tags: [instrument, indices, shorts, frequency, KEY-FINDING]
---

## Hypothesis (exp-012 branch B)
If the short bleed is single-name drift/squeezes (not the setup), dropping individual stocks and
keeping only index ETFs should recover shorts and lift expectancy.

## Result
| year | overall | long | short (all-16 baseline) |
|---|---|---|---|
| 2021 | **+0.388R** (10 tr) | +1,509 (1 tr) | +429 (was −457) |
| 2022 | **+0.230R** (13 tr) | +1,616 | **−119 (was −5,502)** |
| 2023 | **+0.254R** (17 tr) | +1,823 | **+334 (was −9,264)** |
| 2024 | −0.235R (9 tr) | +371 | −1,431 |
4-yr: ~+$4,534 net, 49 trades, positive 3 of 4 years.

## Mechanism
**The catastrophic short losses (−$19.7k on all-16) were almost entirely individual stocks.** On index
ETFs the shorts are ~breakeven (the single-name squeezes/earnings/idiosyncratic drift are gone), and
expectancy jumps to **+0.2–0.39R, positive in 3 of 4 years.** Confirms exp-012: instrument is the
dominant factor. 2024 is the lone negative but only 9 trades (noise).

## The new binding constraint: FREQUENCY
Only **~0.2/wk** (10–17 trades/yr) on 4 ETFs. Great expectancy, far too few trades. This is the
selectivity↔frequency tension again — and the answer is **breadth on the *right* instruments**: more
index + FX + futures, not more single stocks. (Note: the 16-stock *long* book was +$18.5k/4yr — the
stock longs ride the drift and add frequency; it's only stock *shorts* that are toxic.)

## Implication for sequencing
- Best-of-both candidate: **stock LONGS (ride drift, high freq) + index/futures SHORTS (two-sided)**,
  or HTF-gate stock shorts so the 16-name universe keeps its frequency without the short bleed → exp-014 (A).
- The real frequency fix is **more two-sided instruments** → futures/FX via Databento (exp-015 / C).

## Branches
- exp-014 (A) — HTF-gate / premium-gate shorts on the full 16 universe: can we keep stock-long
  frequency while cutting the stock-short bleed?
- exp-015 (C) — intraday futures/FX (Databento): frequency at +0.2R quality on drift-neutral instruments.
