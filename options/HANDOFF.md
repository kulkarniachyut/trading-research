# Options module — session handoff

_Created 2026-06-14. Read `options/README.md` first for the full picture; this is the "what's
done / what's next" for a fresh session._

## State
Scaffold complete and green. **No edge researched yet — by design** (user asked for structure only).
- ✅ `pricing.py` — Black-Scholes + greeks (trader units: theta/day, vega/point) + IV bisection.
  Stdlib only (no scipy/numpy). Fully tested (parity, bounds, greek signs, IV round-trip).
- ✅ `contracts.py` — `OptionContract`, `OptionQuote` (with `.spread_pct`), `OptionPosition`, `Right`.
- ✅ `costs.py` — `OptionsCostModel` (crosses the spread + per-contract commission/fees) +
  `round_trip_drag_pct` go/no-go filter. Tested.
- ⚠️ `data.py` — `OptionsDataProvider` ABC + live `YFinanceOptionsProvider` (no history; guarded).
  `SyntheticChainProvider` (BS-reconstructed) is a **skeleton** — the key TODO.
- ⚠️ `strategy.py` — `OptionStrategy.on_step(ctx) -> [OptionOrder]` interface + registry. No concrete
  strategy yet.
- ⚠️ `backtest.py` — event-driven harness **skeleton**; `_fill`/`_settle_expiries`/`_mark_equity`
  specified but raise/stub until a data provider exists.
- 13 tests pass (`uv run pytest options/tests/ -q`), `ruff check options/` clean.

## The blocker (don't skip)
**Historical options data.** You cannot backtest without as-of chains *with bid/ask*. Decide the
data path before writing a strategy (see README §Data reality):
1. Wire a paid vendor behind `OptionsDataProvider` (real, costs money), OR
2. Implement `SyntheticChainProvider.get_chain` (free-ish, vol/theta studies only) — **most likely
   next step**: pull the underlying close as-of from the repo's existing `DataProvider`, take an IV
   input (VIX or realized-vol proxy), build a strike ladder, price via `pricing.bs_price`, wrap as
   `OptionQuote` with a punitive synthetic spread. Keep it causal.

## Suggested next steps (in order)
1. **Implement `SyntheticChainProvider`** (unblocks everything, zero data cost).
2. **Finish `OptionBacktest._fill` / `_settle_expiries` / `_mark_equity`** against it.
3. **First strategy: cash-secured put or covered call** on an ETF we already trade (SPY/IWM) — the
   vol-risk-premium income family fits synthetic data. Pre-register criteria.
4. **Run it through `src/validation`** (walk-forward + MC). Expect cost drag to kill naive versions
   — `round_trip_drag_pct` will tell you before you build.
5. Only if it survives synthetic + costs: consider paying for real chains to confirm on quotes.

## Honest expectation
Options don't escape the campaign's lesson: the documented edge (short premium / VRP) is real but
modest, and options' **spread costs are far worse than equities'**, so the bar is higher. Most
ideas will die at `round_trip_drag_pct` or the MC gate. The win condition is the same: a small,
validated, post-cost edge — not a fantasy. This scaffold makes finding (or disproving) one honest.

## Cross-refs
- Discipline: repo `CLAUDE.md`, `docs/SESSION_HANDOFF.md`. Validation: `src/validation/`.
- Why fresh (not AlphaSuite/AutoHedge): README §Why a fresh module.
