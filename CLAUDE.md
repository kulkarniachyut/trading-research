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
- Backtest and live share ONE strategy code path (`on_bar`) and ONE engine loop shape.
- No strategy is "done" until it passes walk-forward + Monte Carlo and survives costs.

## Architecture (data flows left → right, each layer depends only on the prior layer's contract)
data (`src/data`) → indicators (`src/indicators`) → strategies (`src/strategies`)
→ {backtest engine + cost model (`src/backtest`), risk (`src/risk`)}
→ validation (`src/validation`) → reporting (`src/reporting`).
Execution (`src/execution`) depends on strategies + risk + data only.
All shared contracts live in `src/core/types.py`. See `docs/COMPONENT_DESIGN.md`.

## Stack
Python 3.11+ (managed by `uv`), pandas, numpy, pyarrow (Parquet), SQLite (stdlib),
pandas-market-calendars. Later: yfinance + alpaca-py (data/broker), smartmoneyconcepts +
a pinned pandas-ta fork (indicators), statsmodels (stat-arb), streamlit + plotly (dashboard).
`pandas-ta` on PyPI is broken on modern numpy/pandas — strategies import indicators only
from `src/indicators/classic.py`, never from a TA lib directly.

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

## Build status (one step at a time, review gate after each)
- [x] Step 0 — Environment & scaffold (core contracts, BaseStrategy + registry, DataProvider)
- [ ] Step 1 — Data layer (yfinance/Alpaca providers, Parquet cache, tz/look-ahead tests)
- [ ] Step 2 — Vertical slice (smc/classic indicators, ICT strategy, engine+costs, metrics)
- [ ] Step 3 — Validation (walk-forward, Monte Carlo, overfit/cost guards)
- [ ] Step 4 — More strategies (momentum, mean-reversion)
- [ ] Step 5 — Comparison runner + Streamlit dashboard
- [ ] Step 6 — Paper execution (Broker, risk layer, paper loop, manual approval)
