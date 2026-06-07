# HANDOFF — pick up here (2026-06-07)

Branch: **`strategy-redesign`** (off `origin/main`). Read this + `experiments/README.md` (the graph)
first. Full detail is in the per-experiment nodes `exp-000…015`.

## The one-paragraph story
"ICT 2022 has no edge" (the old verdict) was wrong about the *cause*. The blended strategy reads
~breakeven because a **profitable long book is cancelled by a short book that loses every year**. The
short failure is **instrument-specific**: on drifting single-name stocks, short targets are reached
only 13% of the time (87% stop-out) — fighting the equity upward-drift anomaly. **Fix the instrument,
not the strategy:** on two-sided CME futures the short side is **positive**, and futures give the best
expectancy seen. The remaining blocker is **frequency** (futures trade only 0.4–0.7/wk on the NY
session) — solved by opening the **23h session (London killzone)** + adding **FX futures**.

## What is PROVEN (post-cost, burned OOS years 2021–2024)
| finding | evidence | node |
|---|---|---|
| Blended ≈ breakeven hides long(+$18.5k) vs short(−$19.7k) | side-split baseline | exp-009 |
| Stock shorts fail by drift (87% stop-out, targets 13%) | exit decomposition | exp-012 |
| Indices-only recovers shorts (+0.2–0.39R, but ~0.2/wk) | SPY/QQQ/IWM/DIA | exp-013 |
| **Long-only on stocks: positive all 4 yrs, +$17.4k** | `run_breadth.py --long-only` | exp-014 |
| **Futures shorts WORK** (+1357/+1297/−370, 2022–24) | `run_futures.py` | exp-015 |
| ICT bias compass is weak (~51% hit), not inverted | daily-bias diagnostic | exp-007 |
| Premium/discount gate does NOT rescue stock shorts | toggle test | exp-014 |

## Current best configs
- **Stocks:** `Ict2022({"long_only": True})` — +$17.4k / 124 trades / positive every year (thin freq).
- **Futures:** `Ict2022({})` both sides on ES/NQ/RTY/YM/GC micros — best expectancy, but ~0.5/wk (noisy).

## NEXT EXPERIMENT — exp-016: open the 23h session (THE frequency unlock)
This is the whole reason to be on futures. Do this first.
1. The strategy's `killzones` / `macro_windows` are **RTH equity times** (`_strategy.py` default_params
   L81–84; `DEFAULT_MACRO_WINDOWS` in `ict/ict_2022/_time.py`). On 23h futures we only trade NY → 0.5/wk.
2. Add the **London killzone (~02:00–05:00 ET)** and London macro window(s); keep NY. Pass via params
   to `run_futures.py` (add a `killzones=[...]` / `macro_windows=[...]` override, or a `--full-session`
   flag). London is where ICT's session model (Asian accumulation → London manipulation → NY) lives.
3. Re-run `scripts/run_futures.py 2022 2023 2024` and check: does trade count rise to a few/week and
   does expectancy stabilize across years (vs the current +0.58/+0.28/−0.26 noise)?

## Backlog (after exp-016)
- **exp-017** — add **FX futures** (`6E`/`6B`/`6J`/`6A` EUR/GBP/JPY/AUD) to `run_futures.py` FUT list.
  Need correct contract specs (6E pt value 125000, tick 0.00005; 6B 62500; 6A 100000; 6J ~12.5M-yen).
  More breadth + diversification → more frequency.
- **exp-018** — fix `detect_sweep` ordering bias (`_model.py:36` checks buyside-first & returns →
  over-tags shorts on expansion bars). Matters now that shorts are live on futures.
- **exp-019** — weekly (W1) direction gate (PWH/PWL draw); engine has NO weekly TF yet
  (`required_timeframes = [M5,M15,H1,D1]`). The user's core thesis; only short *with* the weekly draw.
- **exp-020** — sweep REAL liquidity (equal highs/lows, PDH/PDL, session range) not a generic N-bar pivot.
- **exp-021 (FINAL) — holdout validation:** once session + universe are set, run the finished strategy
  on the reserved **2025/26** holdout + walk-forward + Monte Carlo (`src/validation/`, `run_phase_e.py`).
  **Do NOT peek at 2025/26 before this.** Monte Carlo on long-only was started but not finished.

## Environment / operational notes (save yourself the pain)
- **Setup:** `uv sync --all-extras` (needs `TA_INCLUDE_PATH=/usr/local/include TA_LIBRARY_PATH=/usr/local/lib`
  because TA-Lib's C lib is brew-installed at `/usr/local` — this is an **x86_64 Rosetta** Python).
- **Keys** live in `.env` (gitignored): `ALPACA_API_KEY_ID/SECRET` (equities IEX 5m back to 2021) and
  `DATABENTO_API_KEY` (CME futures, GLBX.MDP3, ~$125 free credits — used some on 2022–24 ES/NQ/RTY/YM/GC).
- **Runs are SLOW** (~2–3 min per 16-symbol-year) — engine compute under Rosetta numba, NOT fetching
  (the Parquet cache works). Run **one year / small universe per process**; multi-year-in-one gets
  killed by background timeouts. Pipe through `grep` block-buffers output — read the task file at the end.
- **Data:** equities via Alpaca (RTH); futures via Databento (23h continuous `ES.c.0` etc., micro
  economics); keyless **yfinance daily** used for the bias diagnostics (`diag_bias_direction.py`).

## Repro commands
```
uv run python scripts/run_breadth.py 2021 2022 2023 2024 --long-only --equities-only   # exp-014
uv run python scripts/run_breadth.py 2023 --indices-only                                # exp-013
uv run python scripts/run_futures.py 2022 2023 2024                                     # exp-015
uv run python scripts/diag_bias_direction.py 2023                                       # exp-007/008
```

## Repo discipline (user's standing rules)
- Nothing to `main` without explicit say-so. Work stays on `strategy-redesign`. Be selective about
  what graduates to the repo (scratch runners stayed in `/tmp`, now deleted).
- Every result post-cost. 2025/26 holdout is one-shot — spend once on the final strategy.
