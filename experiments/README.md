# Experiments — the strategy-search graph

This folder is our **backtracking search over strategy-space**. Each experiment is a **node**
(`exp-NNN-slug.md`). A node records what we *knew* (its `parents`), what we *tweaked* (the delta vs
the parent), *why* (the hypothesis + its source), and what we *got* (the result + verdict). Following
`parents` backward reconstructs the reasoning chain; following them forward branches into the
alternatives we tried. The whole folder is meant to render as a DAG: "what we knew → what we changed
→ what happened," so we never re-walk a dead end and can always branch off any past node.

We do **not** know what works. The edge is somewhere in this space; our job is to find it by
disciplined tries — experiments + reading the market and the community — and to record every step so
the search is cumulative, not circular.

## How to use
1. Copy `TEMPLATE.md` → `exp-NNN-slug.md` (next free number).
2. Fill the frontmatter (`parents`, `tweak`, `hypothesis`, `data`) **before** running — it's a
   pre-registration; you state the bet before you see the result.
3. Run, paste the headline metrics into `metrics`, write the **Mechanism** (why), set the `verdict`.
4. List the **branches** it suggests — those become the next nodes' parents.

## Frontmatter schema (keep it machine-parseable so we can graph it later)
```yaml
id: exp-NNN
title: <short title>
date: YYYY-MM-DD
parents: [exp-XXX, ...]      # breadcrumbs — what this branched from ([] only for the root)
status: planned|running|done
verdict: WORKED|FAILED|INCONCLUSIVE|PENDING
tweak: <one line: what changed vs the parent>
data: <symbols / timeframe / period / IS|OOS>
metrics: {expectancy_r: , trades: , win_rate: , net: }
tags: [bias, smt, costs, ...]
```

## Ground rules
- **Burned data:** 2021/22/24 are spent OOS, 2023 was IS. **2025+2026 = reserved holdout, never peek.**
- Every result is **post-cost**, or it doesn't count.
- A verdict needs a number. Community win-rates (70–80%) are leads, not evidence.
- Record the **mechanism**, not just the metric.

## The graph so far (newest at the bottom)
```
exp-000 mechanical ICT baseline — no robust edge (root finding)
 ├─ exp-001 cheaper instrument (futures)            FAILED  (signal, not cost)
 ├─ exp-002 time precision + displacement selectivity FAILED (⚠ "counter-bias beats aligned" anomaly)
 │   └─ exp-006 RESEARCH: bias engine ignores the daily close (R1)
 │       └─ exp-007 daily-bias direction diagnostic  FAILED (R1 rejected — compass weak, not inverted)
 │           └─ exp-008 isolate + sharpen purge-revert  INCONCLUSIVE (long-side signal, regime-dep.)
 │               └─ exp-009 REAL strategy baseline + side-split  WORKED (shorts lose every yr; longs +$18.5k)
 │                   └─ exp-012 WHY shorts fail (audit+research+decomp)  WORKED (drift: 87% stop-out)
 │                       ├─ exp-013 indices-only (instrument test B)  WORKED (+0.2–0.39R, shorts recover, thin freq)
 │                       └─ exp-014 premium-gate fails → LONG-ONLY  WORKED (+$17.4k, positive all 4 yrs)
 │                           └─ exp-015 ICT on CME futures (Databento)  WORKED(shorts +) / freq too low
 │                               └─ exp-016 open the 23h session / London killzone  ← CURRENT FRONTIER (see HANDOFF.md)
 ├─ exp-003 breadth (universe × session)            INCONCLUSIVE (freq yes, edge no)
 ├─ exp-004 SMT divergence                          FAILED
 └─ exp-005 news / macro-regime filters             FAILED  (they're catalysts, not filters)
```

## Current frontier → **see `HANDOFF.md`** (authoritative next-steps + repro commands + env notes)
**Two proven results:** (1) `long_only` on stocks is positive all 4 years (+$17.4k); (2) on **CME
futures the short side works** (+1,357 / +1,297 / −370 across 2022–24, vs −$5–9k on stocks) — the
instrument was the answer, not deleting shorts. **The blocker is now frequency:** futures run only
0.4–0.7/wk (NY session only) so yearly expectancy is noisy (+0.58/+0.28/−0.26). **Next (exp-016): open
the 23h session (London killzone)** + add FX, to get the trade count that makes the edge stable. Then
holdout 2025/26 + walk-forward/MC on the finished version. (Older nodes' "Branches" use provisional
exp-010/011 numbers that were superseded — `HANDOFF.md` has the clean backlog.)
