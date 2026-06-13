# Trading Research System

## What this is
A backtesting-first research platform to test multiple trading-strategy "buckets"
(ICT/SMC, momentum, mean-reversion, event) on a common interface, compare them on
risk-adjusted, post-cost expectancy, and only promote validated strategies to paper,
then small live trading. The backtester is a **truth machine** — built to disprove
strategies, not confirm them.

## Hard rules (do not violate)
- Every strategy subclasses `BaseStrategy` and emits `Signal` objects via the event-driven
  `on_bar(ctx) -> Signal | None` method. No bespoke pipelines.
- Every backtest applies the cost model (commission + spread + slippage). No frictionless results.
- Report out-of-sample (OOS) metrics separately from in-sample. Never tune on the test set.
- Risk layer enforces: max % risk/trade, max portfolio heat, max-drawdown circuit breaker.
- Execution is abstracted behind the `Broker` interface. Default broker = Alpaca paper,
  manual-approval ON by default.
- **No look-ahead:** the event-driven engine exposes only *completed* bars via `MarketContext`.
  Indicators must be **causal** (value at bar t uses only bars ≤ t), proven by a unit test.
- **News/events causality:** an event's *schedule* is public ahead of time (forward-safe to use as
  a filter), but its *actual result* is look-ahead until release — strategies see results only
  at/after the release timestamp.
- Backtest and live share ONE strategy code path (`on_bar`) and ONE engine loop shape.
- No strategy is "done" until it passes walk-forward + Monte Carlo and survives costs.

## Architecture (data flows left → right, each layer depends only on the prior layer's contract)
data (`src/data`) → indicators (`src/indicators`) → strategies (`src/strategies`)
→ {backtest engine + cost model (`src/backtest`), risk (`src/risk`)}
→ validation (`src/validation`) → reporting (`src/reporting`).
events/news (`src/events`) is a parallel data-side layer (economic calendar + headlines) that
strategies consume as an extra analysis layer — a filter (stand down near high-impact releases)
and a catalyst (news-driven liquidity sweeps). Like costs, it is country-grouped (US, India).
Execution (`src/execution`) depends on strategies + risk + data only.
All shared contracts live in `src/core/types.py`. See `docs/COMPONENT_DESIGN.md`.

## Stack
Python 3.11+ (managed by `uv`), pandas, numpy, pyarrow (Parquet), SQLite (stdlib),
pandas-market-calendars. yfinance + alpaca-py (data/broker), TA-Lib (classic indicators,
self-contained wheel) + smartmoneyconcepts (SMC; numba pinned to a wheel build), statsmodels
(stat-arb), an economic-calendar provider + Alpaca news (events/news), streamlit + plotly
(dashboard). `pandas-ta` is broken on modern numpy/pandas, so we use TA-Lib instead. Strategies
import indicators only from the `src/indicators/` packages (`classic`, `vumanchu`, `smc`,
`common`), never from a TA lib directly.
Futures (the instrument ICT is built for, per `docs/ICT_RESEARCH_AND_PLAN.md`): historical data via
**Databento** (CME `GLBX.MDP3`, free signup credits) behind the same `DataProvider` contract, with
SPY/QQQ (Alpaca IEX) as an RTH proxy fallback; eventual live execution on **Robinhood futures**
(micros MES/MNQ/M2K/MYM) behind the `Broker` interface. Alpaca paper stays the default broker.

## Conventions
- Type hints everywhere; dataclasses for Signal/Trade/Result/Order.
- Pure, causal indicator functions. The engine — not shifting hacks — prevents look-ahead.
- OHLCV DataFrames are tz-aware in `America/New_York`, RTH-filtered, de-duped, monotonic.
- Tests for every indicator (causality) and the cost model.
- Persistence: Parquet for bars/equity curves, SQLite for journal/run-metadata/results index.

## Agent model selection
Default subagents to haiku. Upgrade only when the task requires judgment:
- haiku: file reads, grep/search, data gathering, counting, formatting, test runs
- sonnet: code generation, analysis, debugging, architecture decisions
- opus: cross-cutting synthesis, novel debugging across many files

## Commands
- `uv sync` — install deps. `uv sync --extra dev` — include test/lint tooling.
- `uv run pytest` — run tests.
- `uv run ruff check .` — lint.

## Key finding (2026-06-05) — drives the ICT-hardening plan
Mechanical `ict_2022` (first-touch-OTE) has **no robust post-cost edge** on SPY/QQQ 5m across
2021–2024 (validated IS=2023 / OOS=2021,22,24 via Alpaca IEX). Directional edge ≈ noise; costs are
a large fraction of the tight 5m R. Research agrees the SMC framework alone isn't an edge. The fix
is **more model, not more tuning** — see `docs/ICT_RESEARCH_AND_PLAN.md`. 2021/22/24 are *burned* as
OOS; **2025 + 2026 are reserved as the clean final holdout** — do not peek during A–D tuning.
Alpaca keys now live in `.env` and work; IEX 5m reaches back to 2021. Futures data → Databento free
credits (else SPY/QQQ RTH proxy). Diagnostics in `scripts/diag_*.py` + `scripts/exp_*.py`.

## Compact instructions
When compacting, always preserve:
- Current build step number and what's blocking it
- Any failing tests or open errors
- The last 2–3 architectural decisions made
- Hard rules summary: no look-ahead, cost model required, OOS/IS split, causal indicators only
- Active strategy bucket under investigation and its validation status

## Build status (one step at a time, review gate after each)
- [x] Step 0 — Environment & scaffold (core contracts, BaseStrategy + registry, DataProvider)
- [x] Step 1 — Data layer (yfinance/Alpaca providers, Parquet cache, tz/look-ahead tests)
- [x] Step 2 — Vertical slice: indicators ✓, cost model ✓, MultiTFClock ✓, engine ✓, strategy
      buckets + `ict_fvg` ✓, flagship `ict_2022` v1 ✓, SPY/QQQ multi-regime validation ✓ (→ finding above)
- [ ] Step 2.7 — **ICT hardening (full plan in `docs/ICT_RESEARCH_AND_PLAN.md`)**
  - [x] A — Instrument & cost reality: futures cost model + CME micro specs ✓; verdict: cost ≠ the edge
        problem (futures halve cost, but gross is negative — the **signal** is the problem)
  - [x] B — Time precision & selectivity: formation/entry-window split + `min_disp_strength` ✓; verdict:
        edge concentrates in the Silver-Bullet hour but single-symbol selectivity is **net-negative** →
  - **Reframe:** frequency (a few trades/week, net+) comes from **BREADTH** (universe × full session),
    not narrower tuning; breadth is also the anti-overfit defense (cross-sectional consistency, 100+ trades).
    Crypto (Alpaca, 24/7) tests the session thesis for free. Build the full scaffolding, measure each
    layer, THEN one definitive multi-ticker 4–5yr run. (Revised sequence in the plan doc §5a.)
  - [x] B.5 — Multi-symbol portfolio foundation ✓ (`run_portfolio`, crypto 24/7 data, DST fix). Verdict:
        breadth **solves frequency** (3.6/wk equities, 6/wk +crypto) but pooled edge is ~breakeven
        (+0.01R); crypto-in-NY-window negative (wrong session + %-notional cost). Per-market timeframes deferred.
  - [x] C — SMT divergence ✓ (`MarketContext.ref()` multi-symbol architecture, `require_smt` toggle).
        Verdict on 2024 equities: **no marginal lift** (+0.01→+0.02R; diluted by stock↔own-index pairs).
  - [x] D — Events/News + macro-regime ✓ (VIX `block_risk_off`, FOMC/NFP `block_news_day` toggles).
        Verdict: both filters **hurt** — the setup is volatility-expansion and *likes* risk-off/news days
        (use as catalyst, not filter). None of SMT/regime/news lifts the breakeven edge.
  - [x] E — **Definitive run (2026-06-11): FAIL — mechanical ICT-2022 falsified.** Anchored WF
        on burned years (16 equities, 2021→2024 folds): pooled OOS +0.005R, breadth 56%,
        MC P(total≤0) = 49% (coin flip). The narrative redesign did not lift breakeven. Per the
        pre-stated criterion (positive WF OOS required first), the **2025/26 holdout was NOT
        spent**. Step 2.7 closed — a clean "no" is the deliverable.
- [~] Step 4 — More strategies (momentum, mean-reversion) — **in progress, see
      `docs/STEP4_EDGE_SEARCH_PLAN.md`** (pivot decision 2026-06-10: ICT Phase E deferred,
      runs later as comparison baseline)
  - [x] Diagnostic: ES/NQ session anatomy 2017–22 (overnight drift weak; ORB raw +0.13–0.15R
        gross; upside OR breaks follow through, downside don't; small ES gaps fade)
  - [x] ORB (`orb`) — **retired**: gross +0.04–0.11R real in every variant, but no predeclared
        construction clears micro costs (all within ±0.005R of breakeven post-cost)
  - [x] TSMOM (`tsmom`) — **parked**: IS weakly + at all lookbacks but lumpy; OOS 2023/24
        +0.128R yet breadth 44%, MC p5 −14R, GC carries 77%. 9 markets ≠ enough breadth.
  - [x] IBS mean-reversion (`ibs_rev`) — **parked, replicated**: IS +0.028R → OOS +0.026R
        (magnitude replicates!), 60% breadth, but MC p5 −2.5R (P(luck) 9.9%) — real-looking
        but sub-scale on 5 instruments. Strongest candidate for a combo/scale-up.
  - **2023/24 now burned for IBS+TSMOM** (one-shot OOS spent). Engine fix shipped: open
    positions mark-to-market at end-of-data (`end_of_data`), censoring bias removed.
  - [ ] Next: gap-fade family, cross-sectional equity momentum (yfinance daily), crypto
        momentum, or edge-combination (combo's only clean test = the 2025/26 holdout)
- [ ] Step 5 — Comparison runner + Streamlit dashboard
- [ ] Step 6 — Paper execution (Broker, risk layer, paper loop, manual approval)
