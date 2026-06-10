# Step 4 — Edge Search: strategy families beyond ICT

_Created 2026-06-10. Decision: pivot from ICT (Phase E deferred as a comparison baseline) to
strategy families with documented academic/practitioner edge. Goal: ONE strategy with a real,
post-cost, out-of-sample edge that a $10–20K account can actually trade._

## Constraints (from the user, 2026-06-10)
- **Capital:** $10–20K. Both day and swing — wherever the edge is.
- **Markets:** US only for now (no India data/broker yet).
- **PDT:** account < $25K ⇒ max 3 US-equity day trades / 5 days. Futures (micros) and crypto
  are PDT-exempt → intraday research targets **micro futures** (MES/MNQ/M2K/MYM, MGC, micro FX),
  swing research targets **equities/ETFs + futures daily**.
- **Data on hand (zero marginal cost):** committed Databento archive — canonical 1m, NY-tz,
  2017–2024 reference + sealed 2025/26 holdout — for ES NQ RTY YM GC 6A 6B 6E 6J. Alpaca IEX
  equities 5m back to 2021; Alpaca crypto 24/7.

## Why these families (priors first, code second)
The ICT campaign's core lesson: a popular discretionary framework, made mechanical, was
~breakeven everywhere — and no amount of conditioning (time, SMT, news, regime) lifted it.
So Step 4 starts from families with *published, replicated* evidence of post-cost edge, in
priority order of (documented edge × fit to our data × fit to $10–20K):

| # | Family | Style | Instruments | Prior |
|---|--------|-------|-------------|-------|
| 1 | **Opening-range breakout (ORB)** | intraday, day | MNQ/MES (1m/5m) | Zarattini & Aziz (2023): 5m ORB on QQQ/TQQQ, large documented post-cost edge 2016–2023; momentum-day anatomy is well replicated |
| 2 | **Time-series momentum / trend** | daily, swing (days–weeks) | all 9 futures | Moskowitz–Ooi–Pedersen (2012) + 200 yrs of replications (AQR, "trend everywhere"); strongest prior of any retail-accessible family |
| 3 | **Short-term mean reversion** | daily, swing (1–5 d) | SPY/QQQ + liquid ETFs | RSI-2 / IBS family; documented on equity indices since the 1990s, weaker but persistent post-2010 |
| 4 | **Overnight / session effects** | session-level | ES/NQ (24h data!) | Equity index drift concentrates overnight (Cooper et al.); our 23h futures data measures it cleanly without proxy issues |

Crypto momentum stays a backlog item (B.5 showed crypto needs its own session/cost treatment).

## Discipline (carried over — non-negotiable)
- Engine + cost model only; no vectorized shortcut backtests for verdicts. Diagnostics
  (pure measurement, no trade simulation) may use pandas directly.
- **Data split for the futures archive:**
  - **Design/IS years: 2017–2022.** Diagnostics and all design iteration read these only.
  - **OOS years: 2023–2024.** Touched only by the walk-forward harness as test folds —
    never by eyeballs during design.
  - **Holdout: 2025/26, sealed** (`allow_holdout=True` only for the one final readout).
- A family passes a stage gate only with: positive post-cost expectancy in OOS folds,
  100+ pooled trades, cross-sectional consistency (not one symbol/year carrying it),
  Monte-Carlo p5 ≥ breakeven. Same criterion as Phase E — no goalpost-moving.
- Parameters: prefer theory-fixed defaults; `param_space` exists for ablation, not curve-fit.
  A real edge varies *smoothly* with a threshold; a lucky fit spikes at one value.

## Sequence
1. **Diagnostic: session anatomy of ES/NQ** (`scripts/diag_session_anatomy.py`, 2017–2022):
   overnight vs RTH return split, opening-range width vs rest-of-day drift, day-of-week,
   vol-regime conditioning. Base rates that inform families 1, 2 and 4. No trades simulated.
2. **ORB strategy** (`src/strategies/momentum/orb/`): long/short break of first N-min range,
   stop at opposite extreme (or fraction), EOD flat (Signal "flat" before close), R-multiple
   target vs trail ablation. IS 2017–2022 first; engine + futures cost model.
3. **TSMOM strategy** (`src/strategies/momentum/tsmom/`): daily bars, k-month lookback sign
   (or MA crossover band), ATR stop (engine requires a stop), weekly rebalance cadence,
   9-future basket via `run_portfolio`.
4. **Mean reversion** (`src/strategies/meanrev/`): IBS/RSI-2 on SPY/QQQ daily (Alpaca),
   long-only first (shorting single-leg equities overnight on $10–20K is poor practice).
5. **Walk-forward + Monte Carlo** (existing `src/validation/`) on anything that survives IS.
6. **One** sealed 2025/26 holdout readout for the survivor(s) — alongside ICT Phase E as the
   comparison baseline. Verdicts recorded in CLAUDE.md build status.

## Stage gates (stop-loss on research time)
- A family that is clearly net-negative on IS years after the theory-default config + one
  ablation pass is **retired**, not tuned. (ICT lesson: more tuning ≠ more edge.)
- Record every run's verdict in this doc's log (below) — negative results are deliverables.

## IBS breadth scale-up (approved by user 2026-06-10)
IBS replicated on 5 futures but is sub-scale. Widen the SAME frozen rule (0.2/0.8/MA200,
long-only, 5d time exit, 3-ATR stop — zero changes) to 16 US equity ETFs on yfinance daily
(decades of history; instruments and pre-2017 years are fresh evidence).
**PRE-REGISTERED (before the run):** one run, 2000–2024, frozen params. PASS = pooled
expectancy > 0 post-cost AND breadth ≥ 60% AND MC p5 ≥ 0 AND the pre-2017 era alone is
positive (the era least correlated with how we picked IBS). Era report: 2000–08 / 09–16 /
17–22 / 23–24. Caveats accepted: unadjusted prices (dividend drag biases longs *down* —
conservative) and 0.05×daily-ATR slippage (overstated for liquid ETFs — conservative).

## Run log
- **2026-06-10 · limit-entry execution (user-approved friction work).** Engine extended with
  causal resting-limit entries (`Signal.limit`/`ttl_bars`): gap-through fills at open, strict
  trade-through at the limit, touch ≠ fill, TTL cancel; passive fills maker-costed (no taker
  spread/slippage, fees remain); exits stay taker. 6 unit tests. IBS gets `limit_entry`
  (limit = signal-day close — dip-buying is the natural passive fill).
  - **IS 2017–22:** +0.038R vs +0.028R market (+36%), fill rate 94% (596/635), cost
    0.010→0.006R, all 5 symbols positive, 2022 improves −0.106→−0.040R.
  - **2023/24 re-read (QUALIFIED — second look at burned years; signal frozen, only entry
    tactic changed):** **+0.034R** vs +0.026R, 2024 flips −0.001→+0.020R, MC p5 −1.5R,
    P(≤0) 7.6% (was 9.9%) → **still FAILS the p5 gate**.
  → Verdict: the execution lift is real, consistent and mechanically explained, and it
  compounds with any future scale-up — but it does not change the category: IBS-on-micros is
  *probably real (≈92%), still sub-scale on 5 instruments*. Clearing the bar needs breadth
  (more instruments = the only honest variance reducer left) or live/paper evidence.
- **2026-06-10 · run_ibs_etf (16 ETFs, frozen rule, 2000–2024, one shot): FAIL.**
  Pooled +0.004R net (7,805 tr), breadth 8/16 = 50% ✗, MC pooled P(≤0)=20.6% ✗,
  **pre-2017 ≈ coin flip (P(≤0)=45.1%)** ✗. Era split: 2000–08 −0.004R, 2009–16 +0.005R,
  2017–22 **+0.027R**, 2023–24 −0.033R. Two readings, both important:
  1. *The gross signal exists on ETFs too* (+0.044R/tr) — but the conservative equity cost
     model charges 0.040R (0.05×daily-ATR slippage ≈ 15bps RT vs futures' 0.010R). Same rule,
     same gross, 4× the friction → net zero. **Friction, not signal, decides this family.**
  2. *The era pattern is damning for stability*: the effect concentrates in 2017–22 — exactly
     the era we selected on — and is absent pre-2017 across 5,000+ trades. The futures
     replication (2023/24) is adjacent-era, not independent-era, evidence. IBS looks like a
     **regime-era effect, not a 25-year anomaly**.
  → IBS-ETF parks. The IBS-futures card (P(real)≈90%) stays the best single result but its
  prior is now weaker. Honest cross-search synthesis: every gross edge found so far
  (ORB +0.04–0.11R, IBS +0.03–0.04R) is microstructure-scale and lives or dies on friction;
  paths that change the game are (a) execution realism for dip-buying (limit/MOC entries — IBS
  buys weakness, ideal for passive fills; our market-at-next-open assumption is worst-case),
  (b) bigger-gross families (events/earnings, overnight gap structure, crypto), (c) breadth
  TSMOM can't reach with 9 markets.
- **2026-06-10 · diag_session_anatomy (ES/NQ 1m, 2017–2022, reference only).** Findings:
  1. *Overnight drift* exists (+2.7/+3.7 bps/night ES/NQ, hit 56–57%) but weak (t≈1.2–1.5
     pooled, sign-flips in 2022) — too small vs costs to trade standalone; useful as context.
  2. *ORB raw material is real but modest*: first-5m-direction → close = **+0.13/+0.15 R**
     per day (R = first-5m range), hit ~50% with positive skew (winners > losers, classic
     breakout asymmetry), t≈1.5. Year-to-year unstable (2017 ES, 2021 both negative).
     Construction (tight stop, EOD exit, leverage) is where the published edge lives.
  3. *Breakout asymmetry by side*: upside OR15 breaks follow through (P(close beyond)≈55%,
     +0.07–0.11 ORw); **downside breaks do not** (45–46%, ~0 extension). Index long-bias
     reaches intraday → test ORB long-only vs symmetric.
  4. *Gap behaviour*: large overnight gaps continue (~56%); small ES gaps **fade**
     (43.8% continuation, t=−2.02) — a mean-reversion pocket, backlog for family 3.
  5. *Conditioning traps*: OR-width regime flips sign between ES and NQ; day-of-week
     inconsistent across symbols → **do not condition on either** (overfit bait).
  → Proceed to ORB strategy build with: 5m opening range, asymmetric-side ablation,
    EOD flat, engine + futures cost model.
- **2026-06-10 · run_orb (ES/NQ/RTY/YM micros, engine + futures costs, 2017–2022).**
  Paper spec (5m OR, first-bar-dir, stop=opposite extreme, 10R target, EOD flat):
  **pooled −0.014R net** (gross +0.090R, cost 0.104R/tr) over 5,856 trades; year sign-flips
  (2017 −0.10, 2020 −0.10, 2022 +0.06). Predeclared ablations:
  - `long_only`: **+0.005R net (gross +0.110R, cost 0.105R)** — the diag §3 asymmetry is real,
    but costs eat ~95% of gross. The disease is structural: tight 5m-range stop ⇒ large size ⇒
    cost share ∝ 1/stop-width. Same lesson as ICT Phase A.
  - `rr=2`: −0.063R — truncating the right tail destroys the skew; far target is load-bearing.
  - 15m OR range-break: +0.005R (cost halves to 0.054R as predicted — but gross halves too).
  - 15m range-break long-only: −0.003R; 15m first-bar-dir long-only: −0.034R.
  **VERDICT: ORB retired.** Gross edge exists in every construction (+0.04–0.11R) but no
  predeclared variant clears costs on micros (all within ±0.005R of breakeven). Matches the
  published critiques of the ORB paper's cost assumptions. Re-open only if trading costs change
  category (e.g. exchange-member rates), not for more tuning.
- **2026-06-10 · run_tsmom (9-future micro basket, H1 base/D1 decisions, 2017–2022,
  lookback=252).** **Pooled +0.018R net** (gross +0.032R, cost 0.014R/tr — slow trading is
  cheap), 285 trades, avg hold ~26 days. BUT: 2021 (+0.57R) carries it; 2020 is −0.16R
  (sign-rule whipsaw through the COVID V); per-symbol spread wide (GC/NQ/ES +, 6B/6J/YM −).
  Smooth-variation: 63d +0.007R / 126d +0.065R / 252d +0.018R — all positive (directionally
  consistent) but each carried by 1–2 lumpy years; implied t≈0.9. The literature's TSMOM Sharpe
  needs 50+ market breadth; we have 9. Weak but advances (not net-negative; theory-fixed).
- **2026-06-10 · run_ibs (5 index/metal micro futures, 2017–2022, defaults 0.2/0.8/MA200).**
  **Pooled +0.028R net** (gross +0.038R, cost 0.010R/tr), 635 trades, win 65.5%.
  **All 5 symbols positive**; GC control weakest (+0.013R) exactly as theory predicts (IBS is an
  equity-index effect). Losses concentrate in bear years (2018 −0.04, 2022 −0.106). Smooth
  variation: buy 0.15/0.2/0.3 → +0.022/+0.028/+0.017R; exit 0.7/0.8/0.9 → +0.027/+0.028/+0.043R;
  no-gate +0.017R (gate earns +0.011R). Never flips sign anywhere. **Advances.**
- **2026-06-10 · methodology finding (engine + WF).** Year-fold pooling censored slow strategies
  two ways: (1) the engine silently dropped open positions at end-of-data → fixed in
  `simulator.py` (mark-to-market close, reason `end_of_data`, unit-tested); (2) fold pooling
  counts only fresh-entry trades, excluding P&L of positions carried into a span — TSMOM's
  dry-run swung **−0.155R → +0.141R** on that attribution choice alone. Since Step-4 params are
  theory-fixed (no per-fold tuning), the OOS estimand is **one continuous 2023–24 span** with
  warm indicators and end-of-data MTM — live-replicable. IBS is insensitive to all this
  (5-day holds): +0.028R continuous vs +0.038R folds.
- **2026-06-10 · PRE-REGISTERED OOS criteria (written before the 2023/24 read).** One run per
  family, defaults frozen as above (IBS 0.2/0.8/MA200; TSMOM 252d/3ATR). PASS = pooled OOS
  expectancy > 0 post-cost AND 100+ trades (IBS) / 60+ (TSMOM, slower) AND breadth ≥ 60% AND
  MC p5 total ≥ 0. FAIL = anything else → family parks (no re-tuning against 2023/24; those
  years are then burned for these families). The 2025/26 holdout is touched only if OOS passes.
- **2026-06-10 · OOS 2023/24 one-shot verdicts (2023/24 now BURNED for IBS + TSMOM):**
  - **IBS: PARK — fails MC only.** Pooled **+0.026R** (vs +0.028R IS — the effect *replicates*
    in magnitude), 355 tr ✓, breadth 60% ✓, but MC p5 = −2.5R ✗ (P(≤0) = 9.9%). Failure mode is
    NOT "mirage" (ICT) — it's "real but too small to clear the luck bar at 95% on 5 instruments":
    ≈ +4.6R/yr pooled. 2024 was flat (−0.001R), 2023 carried (+0.057R).
  - **TSMOM: PARK — lumpy, narrow, luck-compatible.** Pooled +0.128R but breadth 44% ✗,
    MC p5 −14R ✗ (P(≤0)=21%), 2023 −0.27R / 2024 +0.96R, GC alone = 77% of net. 9 markets is
    not enough breadth for TSMOM, as the literature warns.
  - Honest summary across Step 4 so far: the truth machine is working — three families, three
    clean answers (retire / park / park). The one *replicated* effect (IBS) is real-looking but
    sub-scale. Remaining unexplored within our constraints: ES small-gap fade (diag §4,
    t=−2.02 IS), cross-sectional equity momentum (needs yfinance daily, decades available),
    crypto momentum (Alpaca 24/7), and combining anti-correlated weak edges (IBS×TSMOM — but
    any combined read on 2023/24 is now contaminated; a combo would go straight to the
    2025/26 holdout as its only clean test, which is a one-shot we should not spend lightly).
