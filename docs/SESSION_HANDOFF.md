# Session handoff — Step 4 edge search → live paper operation

_Last updated 2026-06-13. Read this first, then `docs/STEP4_EDGE_SEARCH_PLAN.md` (full audit
trail) and CLAUDE.md build status. Live-experiment record committed at
`data/paper_journal.jsonl`._

## TL;DR — where we are
**Two validated systems are LIVE in Alpaca paper trading since 2026-06-10** + a full 3-sleeve
~20% portfolio is DESIGNED (backtested) with its risk layer built. Week 1: 5/6 IBS entries
filled, all 5 green (**+1.25% account, unrealized**), but **ZERO closed round-trips** — gates
judge *realized* results at 60/120 trades (~3 / ~6 months). Daily loop runs each post-close.

## Session 2026-06-13 output — the COMPLETE constructed strategy (6 PRs off main)
The honest answer to the user's 25-30% bar, built this session. Branches/PRs (none merged yet):

| PR | Branch | Result |
|----|--------|--------|
| #14 | `xsec-momentum` | cross-sectional momentum — FAIL (just beta / breadth) |
| #15 | `fomc-drift` | pre-holiday effect — FAIL (arbitraged away post-2000) |
| #16 | `portfolio-frontier` | **2-edge frontier: CAGR ceiling ~13% at any leverage** (proven) |
| #17 | `vix-term-structure` | **VIX short-vol carry: Sharpe 0.77, +31% — but 64% DD, −35% days** |
| #18 | `trend-overlay` | **trend crisis-hedge → 3-sleeve book Sharpe 0.81, ~20-24% target** |
| #19 | `step6-allocator` | **risk layer: sleeve allocator (weights/leverage cap/DD breaker), 7 tests** |

**THE CONSTRUCTED STRATEGY (3 sleeves, run as one risk-sized book via `src/execution/allocator.py`):**
1. **Mean-reversion core** = IBS-limit + turn-of-month. VALIDATED (25yr, P(luck) 0.0%/2.5%), LIVE PAPER.
   The reliable base. Standalone ceiling ~13% CAGR (PR #16).
2. **VIX-carry sleeve** = short VIXY when VIX<VIX3M (contango). Sharpe 0.77, the return engine —
   BUT carries crash risk (64% DD, −35% single days; XIV/volmageddon mechanism). Backtested only.
3. **Trend sleeve** = 12-1 TSMOM on diversified ETF basket (SPY/EFA/EEM/TLT/IEF/GLD/DBC/UUP).
   Weak standalone (Sharpe 0.07) but the CRISIS HEDGE: −0.05/−0.15 corr to MR/VIX, green every
   crash month — pays for the VIX tail. Backtested only.
- Combined (30% VIX + 60% trend on the MR core): **Sharpe 0.81, ~16.6% CAGR @ 0.5% base, 31% DD**;
  with leverage to ~50% DD → **~20-24% CAGR**. Scripts: `run_portfolio_frontier.py`,
  `run_vix_carry.py`, `run_trend_sleeve.py`.

**HONEST GAP TO "PROVEN 25-30%" (neither closeable by code in one session):**
- (a) **Live validation, calendar-bound**: only the MR core is live; VIX+trend need the same
  paper gauntlet (months). No code compresses this.
- (b) **User risk decision**: ~20% REQUIRES carrying crash risk (~50% DD, VIX −35% days). Do NOT
  add the VIX sleeve to the live/paper book without the user explicitly opting into that risk.
- Realistic post-degradation target ~15-20%; true 25-30% needs more uncorrelated edges still.
- **META-FINDING:** momentum dies on breadth (3×: futures/crypto/xsec); mean-rev + calendar +
  carry + trend-as-hedge work on small universes. Aim future edge-hunts there, not momentum.

## ⚠️ THE STRATEGIC REALITY (decided with the user 2026-06-13 — read before doing more)
The validated edge is **real but small in dollars**: ~4.8%/yr at 0.5% risk/trade (~6 trades/wk,
59.8% win, +$15.58/trade expectancy, Sharpe ≈ 0.45, ~23% max drawdown). **The user's bar is
25-30%/yr** (below that, an Indian FD at ~7% / their advisor's 15-18% wins).

**Honest verdict on how to clear that bar — this is the project's north star now:**
- You CANNOT get there by leverage on these 2 edges: return and drawdown scale lock-step
  (2% risk → ~19%/yr but ~75% DD; 2.5% → wipeout). 10× return = 10× drawdown = blow-up.
- The ONLY legitimate path is **raising the combined Sharpe by stacking UNCORRELATED edges**,
  THEN moderate leverage. Sharpe ≈ 0.45·√(N edges). To hit ~25-28%/yr at a survivable ~35-45%
  max drawdown needs roughly **8-14 genuinely uncorrelated validated edges** + leverage +
  tolerating big drawdowns. This is a months-to-years build, not a setup tweak.
- "One amazing setup does 25%" is a fantasy that must be resisted; the machine that produces
  25-30% is a *portfolio of mediocre uncorrelated edges*, which is exactly what every serious
  quant shop runs.
- **Mandate going forward: GO WIDE.** Validate many uncorrelated edges with this same truth
  machine; keep the survivors; combine + size by risk. Next bricks (each pre-registered, zero
  spend on existing data): crypto mean-reversion (24/7, uncorrelated market — user explicitly
  asked for BTC/ETH; mind ~10-25bps taker fees, use maker/limit), PEAD/earnings drift
  (event-driven), cross-sectional momentum (negatively correlated to mean-reversion =
  high diversification value in crashes), pairs/stat-arb, overnight-gap structure, FX/futures carry.

## Trader's metrics (the scoreboard — improve THESE, in priority order)
1. **Sharpe ratio** (~0.45) — return per unit risk; THE metric. Raise it via uncorrelated edges,
   not a better entry. Each independent edge lifts combined Sharpe ~√N.
2. **Expectancy** (+$15.58/trade = +0.031R) — avg profit/trade. Limit-fills already cut cost 10×.
3. **Win rate × win/loss** (59.8% × 0.79) — decompose every change into "moved win-rate or win-size?"
4. **Max drawdown & MAR** (return ÷ maxDD; ours ~0.2) — caps safe leverage.
5. **Profit factor, % time in market** — capital efficiency.

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

## Live paper state (as of 2026-06-13, week 1)
- 5 open lots (all IBS): SPY 21@732.91, DIA 29@506.67, XLI 61@173.58, IWM 32@284.08, XLB 195@49.96.
  Each has a GTC 3-ATR disaster stop resting. XLV expired unfilled twice (no chase — by design).
- Unrealized ≈ +1.25% account (recovered from −0.53% on day 1 — textbook reversion path).
- Realized round-trips: **0** (positions on day ~3-4 of the 5-session max hold; exits resolve
  by IBS≥0.8 / day-5 / stop). Fill rate 71-83% (inside the 81-94% backtest band).
- Known op wart: Alpaca paper REST POSTs intermittently drop overnight (maintenance window);
  reads work. Morning/again retries clear it — the loop is idempotent so re-runs are safe.

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

## Backlog (queued, in priority order — the GO-WIDE mandate)
_Goal: reach ~8-14 uncorrelated validated edges so combined Sharpe + leverage can target the
user's 25-30%/yr bar (see Strategic Reality above). Each candidate: pre-register pass criteria
BEFORE looking, run through the truth machine, keep survivors, log negatives._
1. Daily paper ops + first fill review (extend `paper_review.py` with realized-R once fills exist).
2. **Crypto: TESTED 2026-06-13 (`scripts/run_ibs_crypto.py`).** IBS reversion FAILS (gross
   −0.012R — no signal; crypto trends, doesn't revert). Momentum (TSMOM) direction CONFIRMED
   (+0.038R) but MC P(luck) 27-47% — breadth-starved on 8 correlated coins × 4yr. No validated
   crypto edge yet; blocker is breadth (needs more uncorrelated coins / longer history, or
   intraday to multiply trade count). Crypto's character now known: TRENDING. Don't re-test
   reversion; if revisiting, do momentum with more coins or an intraday horizon.
3. **PEAD / earnings drift** — event-driven, swing horizon, decades documented, orthogonal
   mechanism. Earnings dates + reaction via yfinance; pre-register.
4. **Cross-sectional momentum** — *negatively* correlated to mean-reversion (best diversifier
   in crashes). Daily, equities/ETFs.
5. Pairs / stat-arb; overnight-gap structure; FX/futures carry — further uncorrelated bricks.
6. ICT Phase E: DONE 2026-06-11 (FAIL, P=49% — falsified, holdout not spent). Gap-fade: CLOSED.
7. Step 6 proper: shared-capital risk layer, portfolio heat, leverage sizing, automated
   scheduling of the loop (the thing that turns N edges into one risk-sized portfolio).
5. India: blocked on data/broker (user has neither yet).

## User context (do not re-ask)
- Capital $10–20K; US markets; day+swing wherever edge is; PDT-aware (swing ETFs are safe).
- Decisions on record: pivot from ICT (E later), no credit spend, no holdout spend,
  paper-trade + keep mining existing data.
- Memory files: `step4-edge-search-status`, `ibs-etf-limit-best-candidate` (auto-loaded).
