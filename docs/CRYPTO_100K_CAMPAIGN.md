# Crypto $100K Campaign — $10K → $100K mandate (started 2026-06-13)

_Branch `crypto-100k`. Kept separate from `STEP4_EDGE_SEARCH_PLAN.md` (equity track, concurrently
edited). Same truth-machine discipline: pre-register criteria BEFORE looking, log negatives,
theory-fixed params, honest costs._

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
