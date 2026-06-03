# Trading Research System

A **backtesting-first, multi-strategy** research platform. The goal is not to "make a bot" —
it is to **empirically test whether each strategy bucket has positive expectancy after costs,
and discard the ones that don't.** Execution is the last, smallest piece.

The backtester is a **truth machine**: built to disprove strategies, not confirm them.

## Quick start
```bash
uv sync --extra dev      # install (Python 3.11 managed by uv)
uv run pytest            # run tests
```

## Documentation
- `docs/HLD.md` — high-level design (component flow).
- `docs/COMPONENT_DESIGN.md` — per-file deep dive of every component.
- `CLAUDE.md` — project context + hard rules.

## Design pillars
1. **Costs are king** — modeled on every fill; nothing is frictionless.
2. **Out-of-sample or it didn't happen** — OOS metrics reported separately; never tune on test.
3. **One signal interface** — every strategy emits `Signal` via event-driven `on_bar(ctx)`.
4. **No look-ahead by construction** — the engine exposes only completed bars; indicators are causal.
5. **Backtest == live** — the same `on_bar` code path runs in both.
6. **Human-in-the-loop to live** — paper → tiny live with manual approval → scale only if it tracks.

## Status
Built incrementally, one reviewable step at a time. See the checklist in `CLAUDE.md`.
