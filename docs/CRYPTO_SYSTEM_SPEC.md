# Crypto Trading System — FINALIZED SPEC (v1, 2026-06-13)

_The finalized output of the $100K campaign's research phase. One validated edge, frozen, with a
regime trigger, sizing rules, and a standing paper operation. Branch `crypto-100k`. Full audit
trail: `docs/CRYPTO_100K_CAMPAIGN.md`._

## What survived (the only thing that did)
After ~50 strategy variants tested with OOS discipline (carry, vol, daily + intraday momentum /
reversion / cross-sectional, all timeframes, maker costs, regime gates), **exactly one edge is
real, safe, and tradeable on the user's Binance account: delta-neutral FUNDING CARRY.** Everything
directional/reverting is either dead or a decayed in-sample mirage. Vol is real but tail-unsafe.

## THE SYSTEM (frozen — do not tune)
**Sleeve 1 — Funding Carry (delta-neutral, the only live sleeve)**
- **Universe:** 9 liquid Binance USDT perps — BTC ETH SOL XRP DOGE ADA AVAX LINK LTC (BNB excluded).
- **Position:** per coin, long spot + short perp, equal notional → price-neutral; harvest funding.
- **Entry/exit rule (frozen):** hold continuously; flatten a coin when its causal rolling-7d mean
  funding < 0; re-enter when ≥ 0. (Optional selectivity: only deploy coins with funding ann ≥ 10%.)
- **Evidence:** IS 2021-2024 basis-aware **+7.4% net APY, Sharpe ~7, maxDD −0.4%, 9/9 coins +,
  positive every year incl 2022 bear.** Honest, rigor-tested (basis P&L included — it halved the
  naive +14.9%).
- **Sizing:** ≤ **2-3x cross-margin** (user cap). Delta-neutral ⇒ account risk is the BASIS move,
  not price, so cross-margin at 2-3x is safe. At 3x, ~7.4% → ~15-22% APY when the regime is live.
- **Swift-exit triggers (user mandate):** flatten on (a) rolling-7d funding < 0, (b) basis blowout
  beyond N×ATR, (c) any leg fill failure. Never hold a leg naked.

## THE DEPLOY TRIGGER (why it's parked NOW)
Carry is **REGIME-DEPENDENT on the funding level.** OOS 2025/26 was +0.8% (vs +7.4% IS) because
mid-2026 is a low-funding regime. **Deploy only when funding is fat:**
- **Tool:** `scripts/carry_regime_monitor.py` (live) → DEPLOY if basket ann funding ≥ 10%, else
  STAND ASIDE. **Today: +3.4% → STAND ASIDE.**
- Independent corroboration: 3M dated basis also ~2.5% now (BIS-documented carry, also compressed).

## STANDING PAPER OPERATION (live, honors "paper trade until then")
- **`scripts/carry_paper.py --equity 10000 --leverage 2.5`** — run daily. Logs the deploy/stand-
  aside decision + would-be delta-neutral book + paper-equity to `data/crypto_paper_journal.jsonl`.
  SAFE: places no orders. Currently logging STAND ASIDE, paper-equity flat $10,000 (correct).
- **Daily runbook:** `uv run python scripts/carry_regime_monitor.py` then
  `uv run python scripts/carry_paper.py`. (Schedule it, or run weekly while the regime is dead.)

## GO-LIVE CRITERIA (before any real capital)
1. Monitor flips to DEPLOY (funding ann ≥ 10%, sustained ≥ 1 week).
2. Paper operation shows ≥ 30 days of positive net carry matching backtest (within −1σ).
3. Then deploy SMALL real on Binance at 2x, manual-approval, swift-exit rules armed.

## HONEST EXPECTATION vs the $100K goal
- This system: ~15-22% APY **when the carry regime is live**, ~flat when dead. Survivable, real.
- It does NOT 10x in a year. $10K→$100K (10x) is a CYCLE/DIRECTIONAL bet (catching a bull run with
  alt exposure) — high-variance, not a systematic edge; can equally go to $3K. Documented as
  "Path B" in the campaign doc — pursue only with survivable position sizing, eyes open.
- **The system's job is to compound safely and be READY when crypto volatility/funding returns**
  (next bull leg), where the parked edges (carry, and historically intraday momentum) reactivate.

## OPEN R&D (could add uncorrelated return; each is a major, no-guarantee effort)
Novel signals (L2 order-flow, on-chain flows), defined-risk vol harvesting, ML on engineered
features. High overfit risk; the prior (every simple edge decayed) is sobering. Pursue only with
strict walk-forward + the timeframe-consistency check that caught the intraday-momentum fluke.
