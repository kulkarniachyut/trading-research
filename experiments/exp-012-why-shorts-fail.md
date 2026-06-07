---
id: exp-012
title: "Why do shorts fail? (code audit + ICT research + exit decomposition + FX/futures test)"
date: 2026-06-07
parents: [exp-009]
status: done
verdict: WORKED
tweak: investigate the root cause of short failure before deleting the short side
data: code read; web research; SPY/QQQ+stocks 5m 2023; FX/futures daily 2022-23
tags: [shorts, drift, instrument, futures, fx, research, KEY-FINDING]
---

## Question
exp-009 found shorts lose every year. The setup is symmetric (sweep→reverse mirrored), so *why*?
Bug in our short code, or a fundamental market asymmetry? Research before going long-only.

## Evidence gathered

### 1. Exit decomposition (the smoking gun) — SPY/QQQ/IWM + AAPL/NVDA/TSLA/NFLX/MSFT, 2023
| | longs | shorts |
|---|---|---|
| hit **target** | 13/25 (52%) → +17,639 | **3/23 (13%)** → +3,874 |
| hit **stop**   | 12/25 (48%) → −6,775  | **20/23 (87%)** → −10,832 |

Shorts are **stopped out 87% of the time**; their downside targets are reached only **13%** (vs 52%
for longs). After a short entry price *drifts up* into the stop before reaching the target below.
**This is the equity upward-drift signature — not a setup bug.** The mechanics are symmetric; the
market is not.

### 2. Code asymmetry (a real, but secondary, contributor) — `_model.py:36 detect_sweep`
Within each bar it tests **buyside (→short) FIRST and `return`s immediately**, before testing
sellside. So any wide-range/expansion bar that takes out *both* a prior high and a prior low is
**always labelled "buyside → short."** Expansion bars cluster at the open and in uptrends and usually
resolve up → the code structurally over-generates losing shorts (matches the 47-short vs 15-long skew
in the 2021 bull). Fixable, but not the main driver (the exit decomposition shows the thesis itself
is drift-fighting).

### 3. ICT doctrine: shorts are trend-CONTINUATION, not reversal (research)
The bearish order-block / 2022 short setup explicitly requires: **confirm a downtrend**, enter in
**premium**, target sell-side **below**. Our model shorts on *any* buyside sweep with **no HTF trend
gate** — i.e. it shorts into uptrends, which ICT says not to do.

### 4. Instrument fit: ICT is built for index futures + FX, NOT individual stocks (research)
Huddleston's 2022 model targets **NQ/ES futures, major USD pairs (EUR/USD, GBP/USD, XAU/USD)** —
"time-of-day delivery on index futures is more predictable." Individual stocks (14 of our 16) are the
worst case for shorts: idiosyncratic upward drift, earnings gaps, single-name squeezes. The
**overnight-drift anomaly** (one of the strongest in finance) is a structural long tailwind.

### 5. FX/futures daily test (suggestive, noisy) — ES/NQ/GC + EUR/GBP/JPY/AUD, 2022-23
On two-sided instruments the long/short asymmetry **largely disappears** (2022: long +0.1 / short
+0.1 bps; 2023: short slightly *better* than long), vs equities where shorts are consistently far
worse. Supports "instrument/drift, not setup." CAVEAT: daily FX open→close is a noisy proxy (hit
rates 20–33% flag it) — the decisive test needs **intraday** futures/FX (Databento).

## Conclusion
Shorts fail for a **fundamental** reason, layered:
1. (primary) **equity drift** — short downside-targets unreached (13%), stops above hit (87%);
2. **no HTF trend gate** — shorts fired into uptrends, against ICT's own rule;
3. **wrong instrument** — drifting individual stocks vs ICT's two-sided futures/FX;
4. (secondary) **code** — `detect_sweep` over-tags shorts on expansion bars.
**Shorts are not hopeless — they are mis-applied.** Don't just go long-only; test the principled fixes.

## Branches (the experiment menu → exp-013+)
- **A. HTF-gate shorts** (ICT-correct): short only when daily/weekly draw is bearish AND price in
  premium. Long-only is the degenerate case. *(principled, within current data)*
- **B. Indices/ETFs only**: drop the 14 individual stocks, keep SPY/QQQ/IWM/DIA. *(quick; tests if
  shorts recover even within equities once single-name drift/squeeze is removed)*
- **C. Intraday futures/FX via Databento**: NQ/ES + EUR/USD/GBP/USD/XAU — the ICT-correct, drift-
  neutral instruments. *(biggest lever; the real fix; "try harder on futures")*
- **D. Fix `detect_sweep` ordering bias**: pick the sweep aligned with HTF bias / by magnitude, not
  always buyside. *(quick code fix)*
- **E. Bearish-OB continuation short model**: rebuild shorts as downtrend continuation, not high-sweep
  reversal. *(method change)*
- **F. Long-only**: the fallback if A–E don't recover shorts.
