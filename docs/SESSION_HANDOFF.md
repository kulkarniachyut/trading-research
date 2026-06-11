# Session handoff — Step 4 edge search → live paper operation

_Last updated 2026-06-10 (the session that built Step 4 end-to-end). Read this first, then
`docs/STEP4_EDGE_SEARCH_PLAN.md` (full audit trail) and CLAUDE.md build status._

## TL;DR — where we are
**Two validated systems are LIVE in Alpaca paper trading as of 2026-06-10.** Six IBS limit
orders were submitted (SPY/IWM/DIA/XLV/XLI/XLB) and rest for the 2026-06-10 session; the
journal is `data/paper_journal.jsonl` (git-ignored, lives on the user's machine). The next
session's first job is usually: **run the daily loop / review fills** (see Runbook).

## The two systems (parameters FROZEN — do not tune)
1. **IBS-limit** (`ibs_rev`, `limit_entry=True`): buy-limit at signal close when daily
   IBS ≤ 0.2 above the 200d MA; ttl 1 day, never chase; exit IBS ≥ 0.8 / 5th session / 3-ATR
   stop. Evidence: 25yr × 16 ETFs +0.026R, 88% breadth, MC P(luck) 0.0% (pre-2017 alone 0.0%);
   futures OOS replication +0.034R. **Passive execution is load-bearing** — taker entry kills it.
2. **Turn-of-month** (`turn_of_month`): buy SPY/QQQ/DIA/IWM at the open of the 4th-to-last
   session of each month, sell at the open of the 4th session of the next. Evidence: 25yr
   +0.057R, all eras positive, month-clustered MC P 2.5%, futures corroboration (+0.050R,
   not independently significant). **Next window entry: 2026-06-25.**
Combined (the actual portfolio): +9.4R/yr, monthly corr +0.14, clustered MC P(luck) 0.7%.
Honest expectations: ≈ +4.7%/yr at 0.5% risk/trade, worst backtest month −17R, Sharpe ≈ 0.45.

## Runbook (daily, after the 16:00 ET close)
```bash
uv run python scripts/paper_loop.py --yes      # reconcile fills -> stops; plan + submit orders
uv run python scripts/paper_review.py          # journal vs PRE-REGISTERED gates
uv run python scripts/signals_ibs_etf.py --equity 15000   # human-readable signal sheet
```
- The loop reconciles by broker order lookup and journals **actual fill prices**.
- Manual-approval is the default; `--yes` is for unattended runs. PAPER-ONLY by construction
  (`AlpacaPaperBroker` hard-codes `paper=True`). Keys in `.env`.
- **Pre-registered live gates** (plan doc, fixed before any fill existed — DO NOT revise):
  IBS interim n=60, full n=120: fill rate ≥ 70%, expectancy ≥ −0.04R at n=120, slippage ≤ 2×
  modeled. TOM at 12 window-events. Below a gate ⇒ stop and post-mortem, not re-tune.

## Data discipline ledger (critical — what is burned/sealed)
- **2025/26 = SEALED holdout, everywhere** (Databento archive enforces via `allow_holdout`;
  ETF reads were capped at 2024). The project's single clean offline bullet. User explicitly
  said (2026-06-10): **do not spend it**, and **no Databento credit spend** (~$78 breadth
  pull quoted and declined).
- **2023/24 BURNED for IBS + TSMOM** (pre-registered one-shot OOS, spent).
- ICT equities: 2021/22/24 burned as OOS, 2023 IS (see CLAUDE.md key finding).
- Era reads on ETFs 2000–2024 used twice (market-entry, then limit-entry qualified re-read).

## Verdicts so far (full details in STEP4_EDGE_SEARCH_PLAN.md run log)
| Family | Verdict |
|---|---|
| ICT 2022 (Step 2.7) | ~breakeven, Phase E deferred (WF on burned years only; holdout stays sealed) |
| ORB | **retired** — gross +0.04–0.11R real, never clears micro costs |
| TSMOM 9-futures | **parked** — needs 20+ market breadth we declined to buy |
| IBS taker / IBS-ETF taker | parked / superseded by limit-entry |
| **IBS-limit** | **validated → live paper** |
| **Turn-of-month** | **validated → live paper** |

## Engine/infra shipped this session (reusable)
- Limit-order entries: `Signal.limit`/`ttl_bars`, gap-through@open, strict trade-through@limit,
  touch ≠ fill, TTL cancel, maker cost model (`passive_maker=True` in `run_portfolio`).
- End-of-data mark-to-market close (`reason_out="end_of_data"`) — fixes slow-strategy censoring.
- Warmup-aware walk-forward driver (`scripts/run_step4_wf.py`), month-clustered MC pattern.
- Execution layer: `src/execution/alpaca_broker.py` (OrderPlan, paper-only),
  `src/execution/protocol.py` (pure planning, unit-tested), `scripts/paper_loop.py`.
- 159 tests green, `ruff` clean. All work on branch `step4-edge-search` → **PR #13**.

## Known warts / first-review items
- Exit fill prices: `lot_close` journals the exit order id; realized-R needs an order lookup
  join at first review (noted in `paper_review.py`).
- yfinance daily sometimes returns a NaN/partial trailing row (dropped defensively) and can lag
  a session pre-open; the loop is designed for post-close runs.
- TOM sizing in the loop is equal-notional equity/8 per ETF (no stop in spec); IBS sizing is
  risk-based. Both match what was backtested, but a shared-capital risk layer (Step 6 proper)
  is still unbuilt.
- IBS and TOM can hold the same symbol; lots are system-tagged in the journal.

## Backlog (queued, in priority order)
1. Daily paper ops + first fill review (extend `paper_review.py` with realized-R once fills exist).
2. Mining (user mandate, zero spend): **PEAD / earnings drift** (added 2026-06-11 — event
   family, swing horizon, decades documented, third orthogonal mechanism vs IBS/TOM; earnings
   dates + reaction via yfinance; pre-register before reading), crypto momentum (Alpaca, mind
   25bps taker / maker option), overnight structures on 1m archive. Gap-fade: CLOSED
   2026-06-11 (structural cost pre-verdict, see plan doc).
3. ICT Phase E walk-forward on burned years (comparison baseline; no holdout).
4. Step 6 proper: shared-capital risk layer, portfolio heat, automated scheduling of the loop.
5. India: blocked on data/broker (user has neither yet).

## User context (do not re-ask)
- Capital $10–20K; US markets; day+swing wherever edge is; PDT-aware (swing ETFs are safe).
- Decisions on record: pivot from ICT (E later), no credit spend, no holdout spend,
  paper-trade + keep mining existing data.
- Memory files: `step4-edge-search-status`, `ibs-etf-limit-best-candidate` (auto-loaded).
