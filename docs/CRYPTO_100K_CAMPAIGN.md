# Crypto $100K Campaign — $10K → $100K mandate (started 2026-06-13)

_Branch `crypto-100k`. Kept separate from `STEP4_EDGE_SEARCH_PLAN.md` (equity track, concurrently
edited). Same truth-machine discipline: pre-register criteria BEFORE looking, log negatives,
theory-fixed params, honest costs._

## THE TWO-PREMIUM FRAMEWORK (the honest foundation of a crypto book, 2026-06-13)
After mapping the whole landscape, crypto offers exactly TWO harvestable, retail-accessible
systematic premiums — and they are uncorrelated to each other (the basis of real diversification):
1. **CARRY premium** (cost of leverage to chronically-long retail) — expressed via perp funding,
   dated basis, cross-venue spread (all corr ~0.66+, ONE premium). Validated: IS +7.4% net. **State:
   PARKED, regime-compressed** (OOS +0.8%; monitor says STAND ASIDE). Redeploys when funding fattens.
2. **VOLATILITY premium** (variance-risk premium — implied vol > realized vol). Diagnostic confirms
   it EXISTS: Deribit BTC DVOL mean 43.7% vs RV30 39.2% ⇒ **+4.5 vol pts IV-RV**, ~400d. Uncorrelated
   to carry. **RIGOR PASS (short-variance daily P&L, 700d): premium is real (77% win-days, standalone
   Sharpe ~1.05) BUT TAIL-DOMINATED — the single worst day wipes ~278 days of premium.** ⇒ naked
   short-vol is UNINVESTABLE (one spike = ruin; the user has prior losses). **State: real but must be
   harvested via DEFINED-RISK structures only** (iron condors / credit spreads, capped max loss +
   tail hedge) — caps the steamroller, shrinks the premium. Needs Deribit options-chain infra +
   structure/Greeks sim. A careful build, NOT naked straddles.
Everything DIRECTIONAL (momentum/reversion) is dead. **A real crypto book = CARRY + VOL, each
regime/vol-gated, sized ≤2-3x, stacked when both are live.** That's the survivable-aggressive
machine — not 10x, but a genuine two-engine system. Next build: the VOL sleeve (backlog #3).

## GO-WIDE research synthesis (2026-06-13) — the crypto edge landscape
Hard research pass across exchanges/tickers/strategies (X, quant blogs, BIS WP1087 "Crypto carry",
2026 venue reports). Cross-referenced with our own backtests. The picture is consistent:

| Edge | Mechanism | Documented | OUR finding / current regime |
|---|---|---|---|
| Perp funding carry | market-neutral, harvest funding | >10%, to 40% | IS +7.4%, **OOS 2025/26 +0.8% (compressed)** |
| Dated-futures basis | market-neutral cash-and-carry | Sharpe ~4.84, to 50% | **3M basis 2.5% as of Mar-2026 (compressed)** — same regime |
| Cross-venue funding spread | market-neutral, venue divergence | 3-12% majors / 20-60% long-tail | **majors ~3-5% gross, < net after sign-flip fees** (measured Binance v Bybit) |
| Implied-realized vol | options, dynamic hedge | Sharpe ~2.4 | untested — needs Deribit/options infra (big lift) |
| Directional (momentum/MR) | price prediction | weak | **DEAD** (4 momentum deaths; reversion sub-fee at every horizon) |

**STRATEGIC VERDICT: crypto's only monetizable edges are market-neutral CARRIES, and mid-2026 is a
LOW-CARRY REGIME** — perp funding ~0.6%, dated basis ~2.5%, cross-venue thin on majors. The fat
versions (basis 40%, cross-venue 20-60%) need either a high-funding bull regime OR illiquid
long-tail perps (liquidity/exchange/delist risk — where retail loses). Independent 2026 data
corroborates our OOS decay. **The disciplined play: do NOT force carry now (low reward, the way
accounts bleed). Build the carry/basis/cross-venue monitors + execution now; DEPLOY when the carry
regime fattens (redeploy trigger = basket funding/basis back to elevated). Keep go-wide research as
an ongoing program.** This is regime patience, not inaction — exactly the discipline a prior-losses
trader needs.

## Go-wide backlog (prioritized, evidence-ranked) — UPDATED after the basis diagnostic
1. ✅ **Carry regime monitor** (`carry_regime_monitor.py`) — DONE. Live deploy/stand-aside alarm;
   today STAND ASIDE (basket funding +3.7%/yr). Un-parks carry when the regime fattens.
2. ~~Dated-futures basis backtest~~ → **DIAGNOSED, NOT a new sleeve.** Binance continuous-quarter
   basis vs spot 2021-2024: same regime as perp funding (2021 +2.2% / 2022 +0.1% / 2024 +1.5% raw),
   **corr to perp funding +0.66** → it is the SAME carry premium in a different instrument, not a
   diversifier. Keep only as an ALTERNATIVE carry execution (hold-to-convergence, lower liquidation
   risk) for when carry is fat — no separate edge. Currently compressed (raw ~0.1%).
3. **Vol-selling / implied-realized (variance-risk premium)** — NOW THE TOP uncorrelated candidate:
   a genuinely different premium from carry (vol risk vs leverage cost), the only thing likely
   uncorrelated to the carry family. Needs Deribit options/DVOL data + infra. Sharpe ~2.4 documented.
4. **Cross-venue on long-tail perps** — where the 20-60% lives; gated on liquidity/exchange-risk
   diligence (majors measured too thin: ~3-5% gross, < net after sign-flip fees).
5. **Live build** — Binance carry executor (2-3x cross-margin, flatten-when-funding<0, swift exits)
   — build the plumbing during the low regime so it's ready when the monitor flips to DEPLOY.

**Sharpened go-wide reality:** the entire carry FAMILY (perp funding, dated basis, cross-venue) is
ONE correlated premium (cost of leverage to longs) — corr ~0.66+ — currently compressed. Stacking
within the family does NOT diversify. Genuine diversification requires a DIFFERENT premium: vol
(variance-risk) is the leading untested one. Until a 2nd uncorrelated premium is found, the crypto
book is effectively a single regime-gated carry bet — which is why the goal needs patience for the
regime, not more carry variants.

## The goal, stated honestly
User goal: **$10K → $100K in 1 year = 10x / +900%.** This is pursued hard, but the math is fixed:
- The project's *own* validated north star (handoff 2026-06-13) is that clearing even **25-30%/yr
  survivably** needs ~8-14 uncorrelated edges + moderate leverage. 900%/yr is two orders of
  magnitude past that.
- No risk-managed *systematic* strategy delivers 10x/yr survivably. The only things that do are
  (a) extreme leverage (≈ certain ruin if repeated — return & drawdown scale lock-step), or
  (b) a once-per-cycle alt/memecoin moonshot (a lottery, not an edge).
- **Why crypto is still the right venue:** highest-vol liquid 24/7 market, PDT-exempt, fattest
  tails, and it has genuine crypto-native edges (funding carry) that don't exist in equities.
  So crypto is where the most aggressive *honest* return lives.

**Reframed target (the survivable-aggressive plan):** a stacked crypto portfolio —
1. **Funding-carry core** (high-Sharpe, low-vol, ~10-18% net APY) — the stable engine.
2. **Regime-gated directional/trend sleeve** (the BTC>MA gate kept from brick 1) — convex upside
   in bull cycles, cash in bears.
3. Further uncorrelated bricks (intraday MR, basis, vol) as found.
Sized for *maximum survivable aggression* (leverage on the carry core, which has the DD headroom),
realistic stretch ~30-60%/yr with eyes open on a real drawdown — NOT a fantasy 900%.

## Edge backlog (crypto-native, non-momentum — momentum is DEAD, see verdicts)
1. **Funding-rate carry** (delta-neutral) — IN PROGRESS. Highest prior; diagnostic strong.
2. **Intraday mean-reversion** — crypto trends *daily* but may revert *intraday* (untested).
3. **Spot-perp basis / cash-and-carry term structure** — adjacent to funding carry.
4. **Cross-exchange / venue funding spread** — funding differs across venues (Binance vs Hyperliquid).
5. **Vol-targeting overlay** — sizing edge, not a signal; lifts realized Sharpe.

## Verdicts log
- **2026-06-13 · crypto XSEC-momentum + BTC regime gate (IS 2021-2023): FAIL — momentum-breadth
  wall, 4th time.** `run_xsec_crypto.py`, 18/32 coins had 2021 history (wide memecoin universe only
  exists 2024+ → full-cycle wide breadth structurally untestable). Top-5, 12-1wk, maker: net Sharpe
  **+0.81 < EW buy&hold +0.88** → does not beat beta (same as equity xsec). MC P(≤0) 7% (passes luck
  bar) but fails Sharpe & drawdown gates. **KEEPER sub-finding: the BTC>10wk-MA regime gate is real**
  — lifts Sharpe +0.49→+0.81, MC P(≤0) 20%→7%, tames 2022 (no-gate Sharpe −1.31; gated −52% vs B&H
  −71%). Reusable as a directional-sleeve component. OOS 2024 NOT spent (failed IS). Net: momentum
  is dead in crypto too (4 constructions, same wall) → pivot to non-momentum mechanisms.
- **2026-06-13 · funding-carry DIAGNOSTIC (`diag_funding_carry.py`, Binance 8h, 2021-2024):
  STRONG base rates.** Funding positive 77-91% of intervals on majors; collect-when-positive
  basket +16.7%/yr gross; regime 2021 +40% / 2022 +4.9% / 2023 +8.8% / 2024 +13% (always-on 2022
  is −3.7% → the flatten-on-negative rule is load-bearing in bears). Sharpe ~11 is fake-precise
  (gross of fees/basis/churn/liquidation) but the *structure* (retail long-leverage → persistent
  positive funding, non-directional, breadth-independent) is real and explains why it dodges the
  momentum wall. → strategy brick next.
- **2026-06-13 · funding-carry STRATEGY (`run_funding_carry.py`, 2021-2024): VALIDATED — passes
  every pre-registered gate. FIRST validated crypto edge in the project.** Delta-neutral, hold
  continuously, flatten when causal rolling-7d mean funding < 0, 0.10% round-trip fee, 9-coin
  basket. Net basket **+14.9% APY**, Sharpe ~10 (by-construction high — delta-neutral), maxDD
  **−0.4%**. **9/9 coins net-positive ✓; every year positive including the 2022 bear (+2.1%) ✓**
  (the flatten rule is load-bearing — always-on 2022 was −3.7%). Fee-robust: +14.6% even at 0.20%
  RT. Causality fixed (regime decision uses funding through i-1; immaterial vs the look-ahead
  version, now clean per the no-look-ahead rule). Caveats restated: carry-only (basis noise &
  short-leg liquidation not modeled — would shave the Sharpe, not the sign); needs a perp venue.
  NOTE: this +14.9% was CARRY-ONLY (optimistic) — see the rigor pass below, which is the real number.
- **2026-06-13 · funding-carry RIGOR PASS (`run_funding_carry_basis.py`, full delta-neutral incl
  real spot+perp 8h prices): edge SURVIVES at HALF the headline → +7.4% net, the honest number.**
  Adding the basis/price-leg P&L (funding + spot_ret − perp_ret − fees, real Binance klines) cuts
  basket net **+14.9% → +7.4% APY**, Sharpe ~7, maxDD **−0.22%**. **9/9 coins still net-positive;
  every year positive incl 2022 bear (+0.3%).** The ~half cut is CONSISTENT across all 9 coins →
  not a bug, it's the no-arbitrage truth: funding-collected and basis-convergence partially offset,
  and the **~7.4% residual is the real risk premium for providing leverage to chronically-long
  retail.** The naive funding-sum double-counted. Liquidation view: delta-neutral ⇒ account risk is
  the BASIS move, not the price move (long-spot offsets short-perp), so 2-3x is safe with CROSS
  margin (the +177% single-bar "adverse move" is a thin early-listing kline artifact, moot for a
  delta-neutral book). **CORE engine, corrected: ~7.4% unlevered / ~0% DD / Sharpe ~7.**

- **2026-06-13 · crypto intraday hourly reversion DIAGNOSTIC: PARKED (sub-fee).** H1 2021-2024,
  6 coins: mean lag-1 autocorr −0.027 (barely reverting); strongest next-hour signal SOL +8bp /
  DOGE +4.5bp after a down hour — dwarfed by 10-20bp crypto round-trip taker fees (ORB lesson
  again). Reversion concentrates in alts (DOGE −0.088) vs majors (BTC ≈ 0). No build.
- **2026-06-13 · funding-as-contrarian-signal DIAGNOSTIC: NO EDGE (it's pro-momentum).** Bucketed
  forward-24h perp return by funding quintile, 9 coins: high funding → HIGHER forward return
  (+178bp vs +49bp low) — the opposite of the fade thesis. Positioning is momentum, not reversion.
  Reinforces the theme: crypto trends in every dimension; only the market-neutral CARRY monetizes
  it. No build.
- **THEME (2026-06-13): crypto resists mean-reversion at every horizon/dimension tested** (daily
  IBS, intraday hourly, funding-fade — all dead) AND **trend can't be traded** (breadth+fees, 4
  deaths). The ONE monetizable edge is market-neutral funding CARRY (+7.4%). Go-wide in crypto =
  carry variants + sizing/risk overlays, NOT more directional/reversion signals.

- **2026-06-13 · funding-carry OOS HOLDOUT (`validate_carry_oos.py`, 2025-01-01..2026-06-13,
  user-authorized one-shot): DECAYED — regime-gated on the funding LEVEL.** Basis-aware net basket
  **+0.8% APY** (2025 +1.4%, 2026 YTD −0.4%) vs IS +7.4% → ~85% decay; 7/9 coins barely positive
  (SOL/AVAX negative). Cause: funding compressed in the current neutral/low-leverage regime (BTC
  funding now annualizes ~0.6% vs the 2021-24 mean). The +7.4% was earned in high-funding eras
  (2021 euphoria, 2024 recovery). **VERDICT: carry is REAL but REGIME-DEPENDENT; do NOT deploy
  capital now (+0.8% × 2-3x ≈ 2%/yr, not worth the op risk). PARKED per user.** Redeploy TRIGGER:
  basket funding back to elevated levels (a funding-LEVEL gate is the natural refinement — only run
  carry when funding is fat; stand aside otherwise). The truth machine prevented a live deploy into
  a dead regime. 2025/26 funding now spent for carry (OOS one-shot).

## Realistic target math (CORRECTED with the basis-aware number)
- Carry core unlevered: **~7.4% APY, ~0% DD, Sharpe ~7** (was naively ~15%).
- Carry core at user's 2-3x cap: **~15-22% APY**, DD still small (basis-bounded, not price).
- + regime-gated directional sleeve (brick-1 keeper): convex upside in bull cycles, cash in bears.
- **Honest stretch: a great (bull) year maybe ~30-50% (carry-levered + directional), a bear year
  ~flat (carry carries it). NOT 10x, and even ~30%+ leans on the directional sleeve firing.**
- IMPLICATION: at ~7% unlevered the carry core ALONE can't carry the goal — this makes the GO-WIDE
  mandate (stack more uncorrelated crypto sleeves: intraday MR, basis term-structure, vol) the
  real path, with carry as the safe, leverageable anchor rather than the whole answer.

## Data discipline
- Binance/Bybit funding APIs reachable from here; funding history cached to `data/funding/*.parquet`
  (pull-once, reuse). 2021-2024 pulled; **2025/26 NOT pulled** (sealed-holdout discipline mirrored).
- Crypto spot via Alpaca (existing). Coin universe: 36 USD pairs, ~32 ex-stablecoins.

## Execution-reality flags (must resolve before any real money)
- Funding carry needs a **perp venue**. Binance perps are not US-accessible; realistic US route is
  **Hyperliquid** (DEX perp, accessible, funding tracks closely) or dYdX — both need new wallet +
  broker infra (Step 6 scope). Alpaca paper cannot trade perps.
- The validated equity systems (IBS-limit + TOM) remain live on Alpaca paper — unaffected.
