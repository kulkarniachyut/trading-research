# Component-Level Design — deep dive

Data flows left → right; each component depends only on the **contracts** of the one before it,
never its internals. This is the per-file design of every component.

---

## 0. Shared data contracts — `src/core/types.py`
The backbone. Every component speaks these; all are fully-typed dataclasses/enums.

- **OHLCV DataFrame** (a *convention*, not a class): pandas DataFrame, tz-aware
  `DatetimeIndex` in `America/New_York`, columns `open, high, low, close, volume`. Monotonic,
  no duplicate timestamps, RTH-filtered. The universal "bars" object.
- **`Signal`**: `timestamp, symbol, side("long"|"short"|"flat"), size_hint, stop, target,
  reason, meta`. What strategies emit.
- **`Trade`**: `symbol, entry_ts, exit_ts, side, entry_px, exit_px, qty, gross_pnl, costs,
  net_pnl, return_pct, bars_held, reason_in, reason_out`. Produced by the engine.
- **`Result`**: `strategy, symbol, params, trades, equity_curve, metrics, is_oos, period`.
  The unit everything downstream consumes.
- **`Order` / `Position` / `Account`**: execution-side contracts.
- **`TimeFrame`** enum: `M1, M5, M15, H1, D1` with `.pandas_freq` / `.minutes` helpers.
- **`MarketContext`**: the per-bar view handed to a strategy. Exposes ONLY completed bars as of
  `now`: `now`, `bars(tf)`, `last(tf)`, `window(tf, n)`, current `price`, `position`, `account`.
  The forming bar and any future bar are physically absent → look-ahead is impossible.

---

## 1. Ingestion — `src/data/`
Turn "give me SPY 5m bars for 2023" into a clean, cached, look-ahead-safe DataFrame.

- **`base.py` — `DataProvider` (ABC)**
  - `get_bars(symbol, timeframe, start, end) -> OHLCV df` (historical, cached)
  - `get_latest_bars(symbol, timeframe, n) -> df` (paper loop; REST poll)
  - `subscribe(symbols, timeframe, callback)` — **stub now**, WebSocket LATER.
  - Documented guarantees: tz-aware NY index, sorted, de-duped, RTH-filtered, and the last
    (possibly forming) bar dropped unless explicitly requested → structural look-ahead defense.
- **`yfinance_provider.py`** — free history (no keys). Handles UTC→NY and intraday range limits.
- **`alpaca.py`** — `alpaca-py` historical bars (IEX). Same contract → interchangeable.
- **`cache.py`** — Parquet store; path `data/cache/{provider}/{symbol}/{tf}/{start}_{end}.parquet`;
  SQLite `bar_cache_index` for lookups + gap-only refetch.
- **`calendar.py`** — NYSE sessions/holidays (pandas-market-calendars) for RTH + "is open?".
- *Decision:* providers are **dumb fetchers**; all caching/tz/RTH normalization centralized.

---

## 2. Transform / Indicators — `src/indicators/`
Pure functions `df -> df + feature columns`. Look-ahead prevented structurally by the engine;
indicators must be **causal**.

- **`classic.py`** — TA wrappers: `ema, atr, rsi, bollinger, donchian, vwap`. Strategies import
  from here, **never** from the underlying TA lib (insulates against `pandas-ta` breakage).
- **`smc.py`** — wraps `smartmoneyconcepts` into normalized columns: `fvg_top/bottom/dir/mitigated`,
  `ob_top/bottom/dir`, `liq_level/swept`, `swing_high/low`, `bos`, `choch`.
- **`causality.py`** — test utility asserting each indicator's value at bar t uses only bars ≤ t.
- *Decision:* stateless, causal, pure functions. No `shift()` hack — the engine exposes only
  completed bars; the causality test proves indicators respect that.

---

## 3. Strategy layer — `src/strategies/`
Consume feature-augmented bars, emit `Signal`s. The pluggable heart.

- **`base.py` — `BaseStrategy` (ABC), event-driven:**
  - `name`, `params`, `required_timeframes` (ICT → `[H1, M15, M5]`)
  - `on_start(ctx)` — optional warm-up / state init.
  - `on_bar(ctx: MarketContext) -> Signal | None` — called once per LTF bar close; reads
    HTF/MTF/LTF via `ctx`, updates internal state, returns ≤1 Signal. **Same method runs in
    backtest and live.**
  - `on_fill(trade)` — optional hook.
  - `param_space() -> dict` — grid walk-forward optimizes over.
  - **`@register_strategy`** → fills `STRATEGY_REGISTRY` for zero-wiring discovery.
- **`ict_fvg.py`** — state machine (idle → armed → in-trade): H1 EMA slope = bias; M15
  unmitigated FVG/OB = zone; M5 entry when price mitigates the zone *after* a liquidity sweep
  against bias; stop beyond sweep; target opposing liquidity; killzone = time-of-day filter.
- *Decision:* event-driven + native multi-TF, no shortcuts. A small state machine reacting to
  bar closes — exactly how it would behave live.

---

## 4. Cost model + backtest engine — `src/backtest/`
Simulate fills honestly; account for every cent of friction.

- **`costs.py` — `CostModel`**: `commission(qty, px)`, `spread_cost(px, bps)` (half-spread),
  `slippage(px, atr, volume, qty)`. `apply(fill) -> adjusted_fill, breakdown`. Every fill passes
  through; stress mode = ×2 slippage knob.
- **`clock.py` — `MultiTFClock`**: for any LTF `now`, yields the most-recent **completed** bar of
  every higher TF. The engine's no-look-ahead core; what makes multi-TF real during verification.
- **`engine.py` — `EventDrivenEngine`** (thin custom loop):
  1. advance over LTF bars; build `MarketContext` (completed bars only);
  2. `strategy.on_bar(ctx)`; 3. route Signal → risk sizing → simulated order;
  4. **realistic fills:** Signal at bar t close fills at bar t+1 **open** + spread/slippage;
  5. manage stops/targets intrabar; if a bar straddles both, **stop hit first** (pessimistic);
  6. record `Trade`s + equity curve → `Result`.
- *Decision:* custom event-driven, native multi-TF, realistic next-bar fills. Same loop shape the
  live `paper_loop` mirrors. Runner loops per-symbol; cross-symbol heat handled at risk/runner.

---

## 5. Risk / portfolio — `src/risk/`
Turn a `Signal` + account state into a *sized* order; halt when rules break.

- **`sizing.py`**: `fixed_fractional(equity, risk_pct, entry, stop) -> qty`;
  `portfolio_heat(open_positions) -> total_risk_pct` (capped);
  `drawdown_breaker(equity_curve, max_dd_pct) -> halt` (daily max-loss + max-DD breaker).
- *Decision:* engine- and broker-agnostic; operates on contracts so backtest sizing == paper ==
  live. No divergence.

---

## 6. Validation — `src/validation/`
The truth machine: is an edge real or a curve fit?

- **`metrics.py`**: `compute_metrics(result) -> dict` → cagr, sharpe, sortino, max_dd,
  profit_factor, win_rate, expectancy_per_trade, exposure, trade_count.
- **`walkforward.py`**: rolling train/test; optimize `param_space()` on train; run on untouched
  test; concatenate **OOS-only**; keep IS separately.
- **`montecarlo.py`**: bootstrap/reshuffle trade sequence → DD distribution + ruin probability.
- **`guards.py`**: flags `overfit` (OOS Sharpe < ~60% IS), `too_few_trades` (<~100),
  `cost_fragile` (edge dies at ×2 slippage), `ruin_risk`, `param_spike` (no plateau).
- *Decision:* consumes only `Result` objects → identical for every bucket → honest comparison.

---

## 7. Reporting / journal — `src/reporting/`
Persist results; make them reviewable.

- **`store.py`**: `Result`s → Parquet (trades, equity) + SQLite (`runs`, `metrics`, `journal`),
  indexed by strategy/symbol/params/period. Read-back API for the dashboard.
- **`dashboard.py`**: Streamlit — rank buckets by OOS post-cost expectancy; equity/DD charts;
  Monte-Carlo ruin; param-surface; guard report.
- **`journal.py`**: append-only decision log (signal, size, fill, skip + reason) — shared by
  backtest and the live paper loop.

---

## 8. Execution — `src/execution/`
Place orders through a broker, abstracted so strategy/risk never change.

- **`base.py` — `Broker` (ABC)**: `place_order(Order) -> Order`, `cancel(order_id)`,
  `get_positions()`, `get_account()`, `get_clock()`.
- **`alpaca_paper.py`**: `alpaca-py` paper adapter.
- **`paper_loop.py`**: poll latest bar (REST) → run strategy → risk-size →
  **manual-approval gate (ON)** → place via `Broker` → journal. Honors the DD breaker.
- *Decision:* live = same code path as paper; swapping the adapter changes nothing upstream.
  Streaming `subscribe()` slots in here LATER.
