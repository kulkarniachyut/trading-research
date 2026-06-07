---
id: exp-015
title: ICT 2022 on real CME futures (Databento) — do shorts work on two-sided instruments?
date: 2026-06-07
parents: [exp-012, exp-014]
status: done
verdict: WORKED (shorts) / INCONCLUSIVE (overall — too few trades)
tweak: swap drifting equities for two-sided 23h CME futures (ES/NQ/RTY/YM/GC, micro economics)
data: 5 index/gold micros, Databento GLBX.MDP3 continuous, 5m, 2022–2024
metrics: {exp_r: "+0.28/+0.58/-0.26", short_net: "+1357/+1297/-370", freq_per_wk: "0.4-0.7"}
tags: [futures, databento, shorts, instrument, frequency, KEY-FINDING]
---

## Hypothesis (exp-012/014 branch C)
Stock shorts fail because of equity drift (87% stop-out). On two-sided, drift-neutral CME futures —
the instruments ICT was actually built for — the short side should work, and expectancy should rise.

## Setup
- New `DatabentoProvider` (CME `GLBX.MDP3`, continuous front-month `ES.c.0`…, `ohlcv-1m`→5m, 23h, no
  RTH filter). `run_portfolio` extended for the FUTURE asset class (`scripts/run_futures.py`).
- Continuous full-size data traded with **micro economics** (MES/MNQ/M2K/MYM/MGC — Robinhood's
  contracts): ES×5, NQ×2, RTY×5, YM×0.5, GC×10. Default params (NY-session killzones; both sides).

## Result
| year | overall | long | short |
|---|---|---|---|
| 2022 (bear) | 35 tr (0.7/wk), 20% win, +$4,836, **+0.276R** | +3,479 (22 stop/4 tgt) | **+1,357** (6/3) |
| 2023 | 20 tr (0.4/wk), 30% win, +$5,768, **+0.577R** | +4,470 (9/4) | **+1,297** (5/2) |
| 2024 (bull) | 26 tr (0.5/wk), 23% win, −$3,394, **−0.261R** | −3,024 (7 stop/0 tgt) | −370 (13/6) |

Per-symbol is high-variance: YM +$11,678 (2022) then −$898 (2024); RTY −$3,736 (2022); NQ carried 2023.

## Mechanism / verdict
- **WORKED (the question asked): the short side is positive on two-sided futures** — +1,357 / +1,297 /
  −370 across 2022–24, vs −$5.5k/−$9.3k on stocks. Confirms exp-012: shorts were never broken, just
  mis-applied to drifting single names. The instrument *was* the fix.
- **INCONCLUSIVE (overall): too low-frequency to be stable.** 0.4–0.7/wk (20–35 tr/yr) → yearly
  expectancy swings +0.58/+0.28/−0.26 and single symbols dominate. 2024's −0.26R is 7 longs all
  stopping (small-sample). Not yet a reliable edge — a promising signal that needs *more trades*.
- Futures cost model is cheaper per R, and two-sided action lets reversal targets hit both ways.

## Open issues
- **Frequency still low (0.4/wk).** We only trade the NY session — the default killzones/macro windows
  are RTH equity times. The 23h session (esp. the **London killzone**) is unused. That's the next
  frequency unlock (exp-017) and the whole point of using futures.
- Gold (GC) produced no setups under default params; ES/YM slightly negative on tiny samples — need
  more years + the full session before reading per-symbol.
- FX (6E/6B/6J/6A) not yet added — needs contract specs; another frequency + diversification source.

## Branches
- exp-016 — confirm across 2021/2022/2024 (regime robustness of futures shorts).
- exp-017 — **open the 23h session / add the London killzone** → the real frequency fix.
- exp-018 — add FX futures (6E/6B/6J/6A) with correct specs.
- (later) holdout 2025/26 + walk-forward/MC on the *futures* strategy once session + universe are set.
