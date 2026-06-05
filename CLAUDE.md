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
  - [ ] B.5 — **Multi-symbol portfolio foundation** (the spine): universe scanner + portfolio runner +
        `MarketContext.ref()`; breadth baseline on ~15–20 US equities/ETFs **+ liquid crypto**
  - [ ] C — SMT divergence (toggle, measured) on the multi-symbol engine (QQQ↔SPY, BTC↔ETH)
  - [ ] D — Events/News + macro-regime gate (toggle, measured): economic calendar + VIX/DXY/JPY risk-off
  - [ ] E — Definitive breadth run + validation: portfolio walk-forward + Monte Carlo on the reserved 2025/26
- [ ] Step 4 — More strategies (momentum, mean-reversion)
- [ ] Step 5 — Comparison runner + Streamlit dashboard
- [ ] Step 6 — Paper execution (Broker, risk layer, paper loop, manual approval)
