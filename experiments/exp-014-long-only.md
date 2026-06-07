---
id: exp-014
title: Rescue stock shorts? Premium-gate fails → long-only wins
date: 2026-06-07
parents: [exp-012, exp-013]
status: done
verdict: WORKED
tweak: A) require_anchor_pd toggle (premium/discount) ; then long_only=True on full 16
data: 8–16 equities, 5m, 2021–2024, Alpaca IEX
metrics: {long_only_4yr_net: 17426, long_only_trades: 124, positive_all_4yr: true}
tags: [shorts, long-only, premium-discount, KEY-FINDING]
---

## Hypothesis (exp-012 branch A)
Can a harder gate rescue stock shorts (so we keep the 16-name frequency without the short bleed)?
Test the ICT premium/discount gate first; if it fails, fall back to long-only.

## A) Premium/discount gate — FAILED (8 stocks, 2023)
| config | trades | long | short |
|---|---|---|---|
| baseline | 48 | +10,865 (25 tr) | −6,959 (23 tr) |
| require_anchor_pd | 10 | +2,976 (5 tr) | **−2,652 (0% win, 5/5 stopped)** |

Premium-gating does **not** rescue shorts (still 100% stopped — drift doesn't care where in the
session range you enter) and throws away most profitable *longs* too (exp +0.163R → +0.065R). No
session-range filter beats the drift on single names.

## B) Long-only — WORKED (full 16, 2021–24)
Added a minimal reversible `long_only` / `short_only` toggle to the strategy (default both = no
behaviour change). `long_only=True`:

| year | trades (/wk) | win | net | exp |
|---|---|---|---|---|
| 2021 | 16 (0.3) | 25% | +870 | +0.109R |
| 2022 | 41 (0.8) | 29% | +1,262 | +0.062R |
| 2023 | 40 (0.8) | 42% | +8,054 | +0.403R |
| 2024 | 27 (0.5) | 48% | +7,242 | +0.536R |
| **4-yr** | **124** | | **+$17,426** | |

**Positive every year** (vs blended baseline ≈ −$1,100 over the same span). True long-only fires more
longs than the side-split of the blended run (39→124: longs no longer blocked by an open short).

## Mechanism
Removing the drift-doomed short side keeps the profitable long book and lets more longs fire. Win
rate climbs 25→48% over the years; expectancy is thin early (+0.06–0.11R in 21/22) and strong in
23/24 (+0.40/+0.54R). The edge is real but concentrated in the higher-vol two-sided years.

## Caveats
- Burned OOS years; long-only was *discovered* here. Theory-backed (drift), not curve-fit, but the
  **2025/26 holdout is the real test** — must run it before believing.
- Frequency still modest (~0.5/wk avg). The "few trades/week" target needs more instruments.
- Edge concentrated in 2023/24; 2021/22 are barely positive.

## Branches
- **exp-015 (C) — intraday futures/FX via Databento**: the frequency fix + where shorts actually work
  (two-sided, drift-neutral): NQ/ES + EUR/USD/GBP/USD/XAU. The "try harder on futures" path.
- **exp-016 — holdout validation**: run long-only on the reserved 2025/26 + walk-forward + Monte Carlo
  (the Phase-E harness already exists) before trusting the +$17.4k.
- exp-017 — fix `detect_sweep` ordering bias (still over-tags shorts; matters once shorts are back via futures/FX).
