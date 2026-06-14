# Options research module

Self-contained options research, built on the same **truth-machine discipline** as the rest of
this repo: no look-ahead, every backtest applies a (brutal) cost model, OOS reported separately,
survivors validated with walk-forward + Monte Carlo. Created 2026-06-14 as a scaffold — **no edge
yet**; this is the structure to research one honestly.

## Why a fresh module (not a downloaded framework)
We evaluated two popular repos (AlphaSuite, AutoHedge) — one a decent backtester with no edge, one
an LLM-agent demo with *no validation at all*. The lesson, repeated all campaign: **an edge is a
validated statistical inefficiency, never a repo you clone.** So options research starts here, on
infrastructure we control and trust.

## Layout
```
options/
  pricing.py      # ✅ DONE + tested: Black-Scholes price, greeks (trader units), implied-vol solver
  contracts.py    # ✅ types: OptionContract, OptionQuote (bid/ask/spread), OptionPosition, Right
  costs.py        # ✅ DONE + tested: options cost model — spread (dominant!) + commissions + fees
  data.py         # ⚠️ contract + live yfinance provider; SyntheticChainProvider = skeleton
  strategy.py     # ⚠️ interface: OptionStrategy.on_step(ctx) -> [OptionOrder]  (+ registry)
  backtest.py     # ⚠️ skeleton: event-driven harness; fill/mark/expiry specified, needs data
  tests/          # ✅ pricing (parity, greeks, IV round-trip) + costs — 11 passing
  README.md / HANDOFF.md
```
`✅` = implemented & tested. `⚠️` = interface/skeleton, finished when a data source is wired.

## The data reality (READ THIS — it's the real blocker)
**Options backtesting is hard because of DATA, not code.** Equity bars are free; historical option
*chains with bid/ask* are expensive. Three paths, in order of honesty:
1. **Paid vendor** (ORATS / CBOE / Polygon / Databento OPRA) behind `OptionsDataProvider` — the
   real answer for anything touching skew/quotes. Costs money.
2. **Synthetic reconstruction** (`SyntheticChainProvider`): price options from the underlying's
   historical bars + an IV input (VIX / realized-vol proxy) via `pricing.bs_price`, plus a punitive
   synthetic spread. **OK for vol-risk-premium / theta studies; useless for skew.** Free-ish, the
   pragmatic start.
3. **Live only** (`YFinanceOptionsProvider`): current chain, no history → paper/live signals only,
   *not* backtesting. (Guards against a historical `asof` to prevent silent look-ahead.)

## Discipline (inherited, non-negotiable)
- **No look-ahead:** a strategy sees the chain only *as of* `now`; providers must not return future
  quotes (the live provider raises on a historical `asof`).
- **Costs always:** fills cross the **bid/ask spread** (the #1 reason options backtests lie) +
  commissions. Use `OptionsCostModel.round_trip_drag_pct` as a first-pass go/no-go: if the gross
  edge < drag, the strategy is dead before you build it.
- **Validate:** route the backtest's per-trade results through the repo's `src/validation`
  (walk-forward + Monte Carlo) — same gate every other strategy passes. 100+ trades, breadth,
  MC p5 ≥ 0, OOS positive.
- **Theory-led params:** prefer fixed defaults; `param_space` is for robustness checks, not fitting.

## Candidate strategies to research (none built yet)
Short-premium / vol-risk-premium is the documented options edge (sellers harvest the IV-vs-realized
gap) and fits the synthetic-data path: **cash-secured puts**, **covered calls** (income on the
IBS/TOM ETFs we already trade), **short strangles/iron condors** (defined-risk). Each must clear the
cost drag and the validation gate — expect most to die there, like everything else.

## Quick start (what works today)
```python
from options.pricing import bs_price, greeks, implied_vol
bs_price(s=100, k=100, t=30/365, r=0.04, sigma=0.20, right="C")   # ~2.3
greeks(100, 100, 30/365, 0.04, 0.20, "C").delta                  # ~0.52
implied_vol(price=2.5, s=100, k=100, t=30/365, r=0.04, right="C") # recovers the vol
```
`uv run pytest options/tests/ -q` → 11 passing.
