# ict_2022 — handoff / start-fresh state

_Last updated: 2026-06-06. Branch: `ict-2022-mentorship-research`._

Read this first when picking the work back up. It captures **where we are**, **what just shipped**,
and **what's next** so a fresh session can continue without re-deriving context.

## TL;DR
The 68-deck ICT-2022 read-through is **done**, and the **narrative-layer redesign** built from it is
**done and tested** (110/110 tests pass, lint clean). The mechanical v1 trigger
(`sweep → MSS/displacement → OTE/FVG entry`) is unchanged; it is now **wrapped in the TIME + BIAS +
regime + confluence layers** the decks say must gate it. Every layer is an **independent toggle** and the
defaults encode the *full* ICT setup. **The model has NOT yet been re-validated** — that is Phase E, the
next and final step, on the reserved **2025/26 holdout**.

## What just shipped (this branch)
New model layers (all causal, all unit-tested):
- **`_time.py` — TIME layer.** `session_anchor` (RTH→session-open, crypto/futures→true Midnight-NY),
  `anchor_pd` / `anchor_allows` (premium/discount vs the daily anchor), `at_macro_time` +
  `DEFAULT_MACRO_WINDOWS` (08:30 / 09:30 / 10:00 Silver-Bullet / 13:30). Supplies the **TIME** half of
  ICT's TIME×PRICE thesis that v1 lacked.
- **`_bias.py` — BIAS layer (Daily Rebalance Theory, Ep25/19/37).** `daily_rebalance` returns a
  `DailyDraw(direction, draw, basis)` from precedence: unfilled last-3-day daily **FVG** → **purge &
  revert** → **PDH/PDL** premium/discount. `is_consolidation_day` (Ep32, post-outside-day stand-aside).
  This is the **draw-on-liquidity bias engine** v1 never had.
- **`_strategy.py` — wired the layers into `Ict2022` as toggles** (see `default_params`), organized in tiers:
  - Tier 1 (timing + narrative): `macro_time_gate` (default **on**), `require_rebalance_bias` (**on**),
    `require_anchor_pd` (off — faithful default; OTE already enforces leg PD), `target_rebalance_draw` (**on**).
  - Tier 2 (regime/discipline): `skip_consolidation_day` (**on**), `no_trade_lunch` (**on**, 12–13 ET),
    `max_trades_per_day=4` (ICT's ~2 AM + 2 PM).
  - Tier 3 (confluence): `require_fvg_in_disp_half` (**on**, Ep29 quality filter), `require_smt` (off,
    now correctly **timed + biased**), IFVG/breaker (off).
  - Legacy persistent-BOS bias + Phase-D macro filters kept **off** for A/B ablation in Phase E.
  - `_target` now picks the **nearest opposite pool that clears `min_rr`**, choosing between the intraday
    draw and the daily-rebalance draw. Per-day trade cap bookkeeping (`_roll_day`).
  - `param_space` extended with each narrative gate on/off for the Phase-E ablation grid.
- **`tests/test_ict_2022_narrative.py`** — covers TIME, BIAS, and the strategy-level bias gate (allow vs
  block). `tests/test_ict_2022_strategy.py` updated for the new signatures.

## Where this sits in the build plan (CLAUDE.md Step 2.7)
- A–D scaffolding (cost reality, time/selectivity, breadth/portfolio, SMT, events/regime) = **complete**;
  verdict across all of them: **edge sits at ~breakeven (+0.01R)**. The diagnosis from the decks: we had
  the LTF **trigger** but none of the **daily narrative** that gates it.
- **This branch is the redesign that adds that narrative** — the missing-model fix, not more tuning.
- **Step E (NEXT, unstarted) — the definitive run.** Full setup (toggles) across all tickers/markets,
  4–5 yr, portfolio **walk-forward + Monte Carlo** on the **reserved 2025/26 holdout** (untouched — do
  **not** peek before this run). 2021/22/24 are burned as OOS. This is the verdict on whether the
  narrative layers lift the breakeven edge.

## How to verify locally
```bash
uv run pytest -q            # 110 passing
uv run ruff check .         # clean
```

## Guardrails (do not violate — see CLAUDE.md)
- **2025 + 2026 are the clean final holdout.** Do not tune or peek until the Phase-E run.
- All indicators **causal**; the engine prevents look-ahead, not shifting hacks.
- News/events: **schedule** is forward-safe; **results** are look-ahead until release. Decks + our own
  backtest agree: **news is a catalyst, not a filter** (the Phase-D block filters stay off by default).
- Every backtest applies the cost model. Report OOS separately from IS.

## Pointers
- Synthesized model + idea backlog: `research/ICT_2022_MENTAL_MAP.html` (open in a browser).
- Per-deck notes: `research/DECK_NOTES.md`. Deck tracker + the ~12 codeable rules: `research/LEARNING_TRACKER.md`.
- Source decks (read-only, not committed): `~/Desktop/ict-2022/2022 ICT Mentorship @arjoio/`.
