# ICT Hardening — Research & Plan

*Written 2026-06-05, after the `ict_2022` flagship was wired and validated on real data.*

## TL;DR
Mechanical `ict_2022` (first-touch-OTE) has **no robust post-cost edge** on SPY/QQQ 5m across
2021–2024 (validated IS/OOS — see [the finding](#0-the-finding-that-triggered-this)). Independent
research agrees: *"the framework itself is not an edge"* — edge comes from **the right instrument,
time precision, selectivity, HTF/SMT context, and R:R**, not from the SMC labels. This document
captures that research and the phased plan (**A→B→C→D→E, built in order**) to turn the wired-but-flat
model into something with a measurable, honest edge — or to disprove it for good.

---

## 0. The finding that triggered this
Calibrated on 2023 (in-sample), validated on untouched 2021/2022/2024 (OOS), via Alpaca IEX 5m:
- Win rate 22–39% across regimes; **shorts lose in every regime, including the 2022 bear.**
- MFE diagnosis: setups reach +1R only ~43–66% of the time, 2R only ~24–34%, while targets sat at
  ~2.3R → win rate sits *just below* the cost-adjusted breakeven at every R:R.
- The 2023 "winner" (`displacement_atr_mult=2.0`, +1417) **overfit** — lost −2970 in 2022 OOS.
- Exit management (`target_rr=1.0`) lifted win 31%→48% as predicted but stayed net-negative.
- **Binding constraint:** directional edge ≈ noise; transaction costs are a large fraction of the
  tight 5m R → reliably net-negative. (Diagnostics: `scripts/diag_ict_2022.py`, `diag_mfe.py`,
  `exp_ict.py`, `exp_validate.py`.)

This is the truth machine working as designed. The fix is **more model, not more tuning.**

---

## 1. Why ICT fits futures/FX, not equities or options
ICT models *institutional liquidity engineering* on a centralized order book. Instrument
microstructure decides whether that model has anything to bite on:

| | Index **futures** (ES/NQ, micros MES/MNQ) | **SPY/QQQ** equity/ETF | Equity **options (F&O)** |
|---|---|---|---|
| Liquidity | One centralized book → clean, real liquidity pools to sweep | Fragmented across venues | Liquidity is in the underlying, not the contract |
| Session | **23h** — Asian/London/NY killzones genuinely exist | RTH only → half the ICT model can't run | RTH only |
| R / cost | Large R per tick → **costs are a small % of R** | Tight 5m stops → **costs are a large % of R** (killed our edge) | Greeks (IV/θ) dominate — orthogonal to ICT |

**Conclusion:** ICT is a directional, liquidity-structure method best expressed on **index futures**.
Options are the wrong vehicle (you'd express an ICT signal via futures/shares, never via Greeks).
SPY/QQQ are usable **RTH proxies** of ES/NQ but with worse hours and worse retail cost-per-R.

**The unlock:** Robinhood now offers **futures** — Micro E-minis **MES, MNQ, M2K, MYM**, plus
MCL (oil), MGC (gold), BTC — commission-free (only ~$0.32–1.28 CME fees/contract), 23h/day. The
instrument ICT was designed for is now tradeable in the user's account.

## 2. What actually works in ICT (research consensus)
- Realistic killzone win rates are **50–65%**, not the 70–80% claimed; mechanical SMC alone is not
  an edge — selectivity + HTF bias + time precision + R:R≥2:1 are.
- **Time precision** is a major lever we under-use: **Silver Bullet** (10–11 AM ET) and **NY AM
  Macro** (~9:50–10:10 ET) tight windows beat broad 2-hour killzone blocks.
- **SMT divergence** (ES higher-high while NQ doesn't = institutional divergence) is a core,
  high-signal concept we haven't built — and it **needs two correlated symbols at once**.
- Treat rosy third-party backtest numbers (e.g. "61% win, 2.17 PF") as unverified marketing; our
  job is to verify with walk-forward + Monte Carlo, not believe.

### ICT concept coverage
- **Built:** sweep, MSS, displacement, FVG, OTE, premium/discount, breaker, IFVG, inducement,
  persistent daily bias, liquidity levels.
- **Missing / thin:** SMT divergence; tight Silver-Bullet/Macro time windows; specific liquidity
  draws (PDH/PDL, PWH/PWL, prior-session H/L, NWOG/NDOG); HTF "Power of 3" narrative; partial
  scaling / breakeven exit management (needs engine support).

## 3. News / events — two distinct layers (incl. the yen-carry point)
- **(a) Scheduled macro events** (FOMC, NFP, CPI) → an **intraday filter/catalyst**. Schedule is
  public ahead (forward-safe); the *result* is look-ahead until release (hard rule). Use: stand
  down ±N min around high-impact prints, or trade the post-release liquidity sweep as a catalyst.
- **(b) Macro *regime* shifts** (the Aug-2024 **yen-carry unwind**) → **not a calendar event**; a
  cross-market **risk-regime gate** (VIX regime, DXY, JPY, rates). Contextualizes/vetoes trades.

Both live in the (expanded) events layer — **calendar filter + macro-regime gate**.

## 4. Futures data sources (decision)
Alpaca's free feed is **equities + crypto, not futures**, so true 23h ICT needs a futures source:

| Source | Free-to-try | Coverage | Fit |
|---|---|---|---|
| **Databento** (`GLBX.MDP3`) | **$125 signup credits**, usage-based historical | All CME micros (MES/MNQ/M2K/MYM…), OHLCV→tick, clean Python API | **Primary** — sealable behind one `DataProvider` |
| **FirstRateData** | 1 month free updates, then ~$99.95/yr | 7–15 yr intraday MES/MNQ/ES/NQ (1/5/30/60m + tick), bulk download | **Cheap fallback** for a one-time bulk pull |
| Portara / CME DataMine | trial unavailable / enterprise | Official CME | Overkill for now |
| **SPY/QQQ proxy (Alpaca)** | already working | RTH only | **Last resort** / fast iteration on the NY-killzone slice |

**Plan:** start Phase A on the **SPY/QQQ RTH proxy** (zero friction, already cached) to test the
*economics* hypothesis, then onboard **Databento free credits** as a sealed futures `DataProvider`
to confirm on real **MNQ/MES** with the full 23h session before trusting any session/killzone result.

---

## 5. Phased plan — built **A → B → C → D → E, in order**

### Phase A — Instrument & cost reality *(foundational)* — ✅ DONE (verdict: cost ≠ the problem)
Added a **futures asset class** (`us_futures()` cost preset: tick spread + ATR slippage + $0 broker
commission + per-contract CME/NFA fee, ~$2.24 round-turn/MNQ) and a CME micro registry
(`src/backtest/instruments.py`: MES/MNQ/M2K/MYM/MGC, point value + tick + ETF→index proxy factor).
Fixed a latent simulator P&L bug (gross/net now scale by `InstrumentSpec.multiplier`).
**Hypothesis test** (`scripts/exp_futures.py`): `ict_2022` is scale-invariant, so rescaling the
SPY/QQQ RTH proxy into index-point space with **matched leverage** fires identical trades →
isolates cost. Result across 2021–2024:
- Futures economics **roughly halve cost** (equity $14,651 → futures $8,163, −44%). ✅
- But **gross P&L is −$3,997 before any cost** — the directional edge is negative, not marginally
  positive. Cheaper costs cut the loss (−18,649 → −13,160) but cannot flip it. ❌
- **Conclusion:** the problem is the **signal**, not the instrument. Futures is carried forward as
  the cheaper *execution* vehicle; edge must come from Phase B (selectivity) + Phase C (SMT).
*Done:* `src/backtest/costs/presets/us.py`, `src/backtest/instruments.py`, `src/backtest/simulator.py`,
`tests/test_costs_futures.py`, `scripts/exp_futures.py`. *(Deferred: real MNQ/MES via Databento —
the RTH proxy is sufficient to reject the cost hypothesis.)*

### Phase B — Time precision & selectivity *(cheap, high-leverage)*
Replace broad 2-hour killzones with **Silver Bullet** (10–11 ET) and **NY AM Macro** (~9:50–10:10
ET) windows; tighten setup selectivity (displacement authenticity, single-shot per killzone,
liquidity-draw targeting). Measure edge (reach-1R, expectancy) not just PnL.
*Touches:* `src/strategies/common.py` (time windows), `ict_2022/_strategy.py`.

### Phase C — SMT divergence *(architectural)*
Extend the engine so `MarketContext` can expose a **correlated reference symbol** (NQ↔ES or
QQQ↔SPY). Implement an **SMT divergence** primitive (one index sweeps a liquidity level, the
correlated one does not) and wire it as a confluence filter/trigger.
*Touches:* `src/backtest/clock.py` + `engine.py` (multi-symbol context), `src/core/types.py`
(`MarketContext.ref(symbol)`), new `ict_2022/_smt.py`.

### Phase D — News/Events + Macro regime *(the expanded Step 2.8)*
Country-grouped economic calendar (causal schedule-vs-result) **+** macro-regime gate (VIX/DXY/JPY
risk-off detector). ICT consumes both as filter (stand down near releases / risk-off) and catalyst
(post-news sweep). Builds on `docs/COMPONENT_DESIGN.md §9`.
*Touches:* `src/events/` (new), `MarketContext.events_within()/recent_news()`, regime helper.

### Phase E — Honest validation *(Step 3)*
Walk-forward + Monte Carlo + overfit/cost guards on the upgraded multi-instrument model, against the
**reserved 2025 + 2026 holdout** (2021/22/24 are now burned as OOS). Accept or reject on
OOS post-cost expectancy with a trade-count floor and a cost-fragility check.
*Touches:* `src/validation/` (new).

---

## 6. Open decisions / risks
- **Databento signup** required to get real futures data (else stay on SPY/QQQ proxy). Free credits
  should cover historical OHLCV backtesting comfortably.
- **Multi-symbol engine (Phase C)** is the one real architectural change; everything before it is
  single-symbol-compatible.
- **Overfitting discipline:** 2021/22/24 are burned; only 2025+2026 remain clean. Phases A–D form
  hypotheses on mechanism (not PnL grid-search); Phase E is the one clean final test.
- Robinhood futures = **no options on futures, no ag/rates** — fine, we only need index micros.
