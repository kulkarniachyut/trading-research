# High-Level Design — Trading Research System

## Purpose
Empirically test whether each strategy bucket (ICT/SMC, momentum, mean-reversion, event) has
**positive expectancy after costs**, on a common interface, and discard the ones that don't.
The backtester is a truth machine. Execution is the last, smallest piece.

## Locked decisions
| Area | Choice |
|---|---|
| Market / broker | US equities + **index-futures micros** (the instrument ICT is built for). Data: **Alpaca** (free IEX equities) + **Databento** (CME futures, free credits) behind one `DataProvider`; SPY/QQQ RTH proxy fallback. Brokers: Alpaca paper (default) → **Robinhood futures** (MES/MNQ/M2K/MYM) for live, behind the `Broker` interface |
| First strategy | ICT/SMC — `ict_fvg` (simple) + `ict_2022` flagship (full 2022 model); modular buckets |
| ICT direction (2026-06-05) | Mechanical `ict_2022` proved **no post-cost edge** on SPY/QQQ 5m → hardening plan **A→B→C→D→E** (futures economics → time precision → SMT → events/macro-regime → validation). See `ICT_RESEARCH_AND_PLAN.md` |
| News / events | Two layers: country-grouped **economic calendar** (schedule forward-safe, results gated to release; ICT filter + news-sweep catalyst) **+** cross-market **macro-regime gate** (VIX/DXY/JPY risk-off, e.g. yen-carry unwind) |
| Backtest engine | **Custom event-driven, native multi-timeframe** (no single-series shortcut) |
| Signal model | **Event-driven** `on_bar(ctx) -> Signal \| None` — same code path backtest & live |
| Persistence | Parquet (bars, equity curves) + SQLite (journal, run-metadata, results index) |
| Real-time | REST bar-polling first; WebSocket streaming later, same interface |
| Hosting | Local Mac; small cloud box only later for an always-on loop |

## Component flow
```
┌─────────────────────────────────────────────────────────────────┐
│  DATA SOURCES   Alpaca REST (hist) │ Alpaca WS (live, LATER)      │
│                 yfinance (free history / backup)                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │  DataProvider interface (one contract)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  INGESTION & CACHE   →  Parquet (OHLCV bars) + SQLite (meta)      │
│  tz=America/New_York, RTH-filtered, de-duped, forming bar dropped │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  TRANSFORM / INDICATORS   classic.py (TA) + smc.py (ICT)          │
│  pure, CAUSAL functions (value at t uses only bars ≤ t)           │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  EVENTS / NEWS    economic calendar (FOMC/CPI/NFP…) + headlines   │
│  schedule forward-safe; results gated to release ─────────────┐   │
└───────────────────────────────────────────────────────────────│──┘
                                                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  STRATEGY LAYER   BaseStrategy plug-ins → on_bar(ctx) → Signal    │
│  ict_fvg + ict_2022; registry-discovered; multi-TF state machines │
│  (consume bars + indicators + events as filter / catalyst)        │
└──────────────┬───────────────────────────────┬──────────────────┘
              ▼                               ▼
┌──────────────────────────┐   ┌──────────────────────────────────┐
│  BACKTEST ENGINE          │   │  RISK LAYER                       │
│  MultiTFClock + event loop│   │ sizing, portfolio heat, DD breaker│
│  + COST MODEL (every fill)│   │ (same math backtest & live)       │
└────────────┬─────────────┘   └────────────────┬─────────────────┘
            ▼                                   ▼
┌──────────────────────────┐   ┌──────────────────────────────────┐
│  VALIDATION               │   │  EXECUTION (Broker interface)     │
│  walk-fwd, MonteCarlo,    │   │  Alpaca paper → live (LATER)      │
│  metrics, overfit guards  │   │  manual-approval gate ON          │
└────────────┬─────────────┘   └────────────────┬─────────────────┘
            ▼                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  REPORTING / JOURNAL   Parquet+SQLite store → Streamlit dashboard │
│  rank buckets by OOS post-cost expectancy; append-only journal    │
└─────────────────────────────────────────────────────────────────┘
```
The backtest path and the live path **share** the strategy (`on_bar`), cost, and risk layers.
That shared code path is what makes "validated in backtest → paper → live" honest.

## Dependency direction (no cycles)
`core/types` ← everything.
`data → indicators → strategies → {backtest, risk} → validation → reporting`.
`events` (economic calendar + news) is a data-side layer consumed by `strategies` (exposed to
`on_bar` via `MarketContext`); its provider is sealed behind one file and country-grouped.
`execution` depends on `strategies + risk + data` only.
Each third-party engine/broker/TA-lib/data-or-news provider is sealed behind a single file so it
is swappable.

## Why a custom event-driven engine (not backtesting.py / vectorbt)
ICT is inherently multi-timeframe (HTF bias → MTF zone → LTF entry). Wrapping a single-series
library would force a flattening hack — a shortcut that distorts exactly what we want to verify.
A small custom event loop driven by a `MultiTFClock` (which only ever exposes *completed* bars
of each timeframe) gives true multi-TF semantics, makes look-ahead structurally impossible, and
is the same loop shape the live paper trader mirrors.

See `COMPONENT_DESIGN.md` for the per-file deep dive.
