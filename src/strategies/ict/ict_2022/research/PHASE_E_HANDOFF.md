# Phase E — Definitive Validation Run · session handoff

_Created 2026-06-06. Branch: `minsk` (synced with `origin/main`). Read `HANDOFF.md` first for model
state, then this for the validation job._

## The job (Step 2.7 · E — the verdict)
Decide whether the **narrative-layer redesign** (TIME + BIAS + regime + confluence wrapping the v1
trigger) lifts the breakeven edge into a **real, post-cost, out-of-sample edge** — or whether
mechanical ICT-2022 is finally falsified. This is the gate that ends Step 2.7. **No more tuning** — the
defaults already encode the full ICT setup; E *measures*, it does not fit.

The verdict criterion, decided up front so we can't move the goalposts:
- **Pass** = positive post-cost expectancy that holds across the **walk-forward OOS folds** AND on the
  **reserved 2025/26 holdout**, with **100+ pooled trades**, cross-sectional consistency (not one
  symbol carrying it), and a Monte-Carlo 5th-percentile outcome that is still ≥ breakeven.
- **Fail** = edge ≤ breakeven OOS, or it survives only in-sample / on one symbol / one regime.
- Either way the result is the deliverable. This is a **truth machine** (CLAUDE.md) — a clean "no"
  retires mechanical ICT and is a success.

## ⚠️ Two preconditions before any run
1. **No Alpaca keys anywhere — HUMAN BLOCKER, an agent cannot self-resolve this.** There is **no
   `.env` on this machine** (searched exhaustively: this workspace + parents, the `handoff-summary`
   worktree, the main repo at `/Users/achi/conductor/repos/trading-research`; no
   `config/secrets.yaml`; no `ALPACA_*` in the process env or shell profiles — the only `.env` files
   on disk belong to unrelated projects). The earlier "copy the working `.env`" note was wrong; there
   is nothing to copy, and keys must **not** be fabricated. Without keys, `AlpacaProvider` /
   `AlpacaCryptoProvider` return no data and Phase E cannot run.
   - **To unblock, the user must supply real Alpaca (paper) keys.** `src/core/config.py` resolves them
     in priority order: **(a)** process env, **(b)** `.env` at repo root, **(c)** `config/secrets.yaml`.
     Recognized names: `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY` (env + `.env`), or an
     `alpaca: {api_key_id, api_secret_key}` block in `config/secrets.yaml`. Simplest — create
     `minsk/.env`:
     ```
     ALPACA_API_KEY_ID=...
     ALPACA_API_SECRET_KEY=...
     ```
   - IEX 5m reaches back to 2021. After keys are in place, confirm with a one-symbol fetch
     (`AlpacaProvider().get_bars("SPY", TimeFrame.M5, ...)`) before launching the full sweep.
2. **`src/validation/` is EMPTY.** Walk-forward and Monte-Carlo do **not exist yet** — `__init__.py`
   is 0 bytes. Phase E is **build the validation harness, then run it**, not "run a script." Budget the
   build first. (Everything below the harness — the portfolio spine, the model, costs — is done.)

## Hard guardrail (do NOT violate — CLAUDE.md)
- **2025 + 2026 are the clean final holdout.** They have NEVER been touched. Do **not** peek, tune,
  inspect per-symbol pulls, or iterate against them. Build + dry-run the harness on the **burned** years
  (2021/22/24 OOS, 2023 IS) ONLY. Touch 2025/26 **once**, at the very end, for the single final readout.
- All indicators causal; the engine prevents look-ahead, not shifting hacks.
- Every backtest applies the cost model. Report OOS separately from IS.
- News/events: schedule is forward-safe, results are look-ahead until release. Decks + our own
  backtest agree news is a **catalyst, not a filter** → Phase-D block filters stay **off** by default.

## What already exists (build on these — don't rebuild)
- **Portfolio spine:** `src/backtest/portfolio.py::run_portfolio(make_strategy, universe, start, end,
  *, provider, crypto_provider=None, references=None, regime_series=None, news_calendar=None,
  base_tf=TimeFrame.M5, initial_equity=100_000, risk_pct=0.005, max_leverage=4.0)`.
  - `make_strategy` is a **factory** (clean state machine per symbol). Per-symbol $100k sleeves.
  - Returns `PortfolioResult` with `.results` (per-symbol `Result`), `.trade_count`,
    `.trades_per_week`, `.win_rate`, `.total_net`, `.expectancy_dollars`, `.expectancy_r`,
    `.per_symbol()`, `.errors`. (See `PortfolioResult` in `portfolio.py`.)
  - `references` = traded→SMT-correlate map for `ctx.ref()`; only needed if ablating `require_smt`.
- **Universe** (copy from `scripts/run_breadth.py`): 16 equities/ETFs
  `SPY QQQ IWM DIA AAPL MSFT NVDA AMZN META GOOGL TSLA AMD NFLX JPM XLE GLD`
  + 8 crypto `BTCUSD ETHUSD LTCUSD BCHUSD SOLUSD AVAXUSD LINKUSD DOGEUSD` (`AssetClass.CRYPTO`,
  via `AlpacaCryptoProvider`, 24/7). NOTE B.5 verdict: **crypto-in-NY-window is negative** (wrong
  session + %-notional cost) — keep crypto as a *separate* sleeve / session, don't let it mask the
  equity read. Consider equities-only as the headline and crypto as a secondary line.
- **Model:** `Ict2022({})` — `default_params` (full ICT setup, all toggles on by design) and
  `param_space` (the Phase-E ablation grid: `macro_time_gate`, `require_rebalance_bias`,
  `require_anchor_pd`, `skip_consolidation_day`, `require_fvg_in_disp_half`, `require_smt`, + trigger
  knobs) live in `src/strategies/ict/ict_2022/_strategy.py`.
- **Reference runners** to imitate: `scripts/run_breadth.py` (portfolio call shape),
  `scripts/exp_validate.py` (OOS-across-years framing: a real edge holds across regimes and varies
  *smoothly* with a threshold; a lucky fit spikes at one value and collapses around it).

## What to build (`src/validation/`)
1. **Walk-forward** (`walk_forward.py`): rolling/anchored train→test split over the burned years
   (2021–2024). Because defaults are theory-led (not fit), the "train" step is at most a light ablation
   pick from `param_space` (or none — prefer measuring the fixed full setup). Report **per-fold OOS**
   expectancy + pooled OOS. Keep it portfolio-level (call `run_portfolio` per fold).
2. **Monte-Carlo** (`monte_carlo.py`): bootstrap/shuffle the pooled trade-return (R) sequence
   (1000+ resamples) → distribution of total R / max-drawdown; report **5th-percentile** expectancy and
   DD. This is the "is the edge distinguishable from luck" test.
3. **Driver** `scripts/run_phase_e.py`: wire universe + model + WF + MC; print a one-screen verdict
   table (per-fold OOS, pooled OOS, MC p5, trade count, per-symbol consistency). Years as argv.
4. **Tests** for both new modules (causality / no-look-ahead in the split; MC determinism with a seed).
   Match existing test style; keep `uv run pytest` green and `ruff check .` clean (currently 110 pass).

## Sequence (so the holdout stays clean)
1. Fix `.env`, confirm data fetch.
2. Build WF + MC + driver. Dry-run + iterate **only on 2021–2024** (burned). Sanity-check trade
   counts, per-symbol spread, no exceptions in `.errors`.
3. Lock the harness + params. **One** final run including 2025/26. Record the verdict in CLAUDE.md
   "Build status" (Step 2.7 E) and in `HANDOFF.md`.

## Verify locally
```bash
uv run pytest -q      # 110 passing today; keep green
uv run ruff check .   # clean
```

## Pointers
- Model state / what shipped: `HANDOFF.md` (same dir).
- Synthesized model + idea backlog: `ICT_2022_MENTAL_MAP.html`. Per-deck notes: `DECK_NOTES.md`.
- A–D verdicts (all ~breakeven; why the narrative layers were added): CLAUDE.md "Build status".
