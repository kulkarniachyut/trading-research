# Crypto $100K Campaign — Experiment Index & Handoff

_Branch: `crypto-100k-campaign` (PR #21). Goal framing: turn $10K → $100K in crypto (later widened
to all asset classes). This folder is the master index — every strategy tested, its verdict, how to
re-run it, and the data archived. Nothing here should be lost; another session can resume from main._

## TL;DR — what to know in 60 seconds
- **One real, validated edge: funding-rate carry** (delta-neutral, crypto perps). +7.4% net APY
  basis-aware (IS 2021-24), Sharpe ~7 *when the funding regime is live* — but **OOS 2025/26 decayed
  to +0.8%** (regime-compressed). **PARKED** with a live deploy trigger (`carry_regime_monitor.py`).
- **Everything directional is dead** in crypto: momentum (4 ways), reversion (decays OOS), ORB,
  ICT/FVG (look-ahead artifact), cross-sectional intraday. Crypto trends; only market-neutral carry pays.
- **Cross-domain extension (RMR, equities):** the NYU-Stern OPS algo — real frictionless (Sharpe
  0.65) but cost-fragile (dies by 5bp/side) and drawdown-heavy. Same "real-but-small" bucket as IBS/TOM.
- **Best realistically-deployable Sharpe in the whole project: ~0.45 live (IBS+TOM) → ~0.8 backtested
  3-sleeve.** No turnkey 25%+ edge exists; the path is stacking small uncorrelated edges + leverage.
- **Biggest methodology win:** caught an MTF-FVG backtest showing 78% win / +0.89R that was 100%
  look-ahead (causally −0.15R). The exact bug that blows up live accounts. Distrust spectacular results.

## Verdict table (all causal, OOS-split, post-cost unless noted)
| Strategy | Script | Verdict |
|---|---|---|
| **Funding carry** (delta-neutral) | `run_funding_carry_basis.py` | ✅ **VALIDATED** +7.4% IS / Sharpe ~7; OOS decayed → PARKED, regime-gated |
| Crypto xsec momentum + BTC regime | `run_xsec_crypto.py` | ❌ Sharpe 0.81 < buy&hold 0.88 (4th momentum death). Regime gate is a keeper. |
| Crypto IBS / daily reversion | (`run_ibs_crypto.py`, prior) | ❌ gross −0.012R — crypto doesn't mean-revert daily |
| Intraday momentum (1h/15m) | `run_intraday_momo.py` | ❌ great IS, fails OOS; vol-gate flips 1h+ but 15m contradicts → fluke |
| Intraday mean-reversion | `run_intraday_momo.py --revert` | ❌ real IS (Sharpe 3.0!) but decays OOS; calm-gate doesn't save |
| Intraday cross-sectional L/S | `run_xsec_intraday.py` | ❌ negative IS *and* OOS (rotation cost > dispersion) |
| ORB (UTC opening range) | `run_crypto_orb.py` | ❌ negative all variants (breakouts whipsaw) |
| MTF FVG (+bias +killzone) | `run_mtf_fvg.py` | ❌ look-ahead artifact; causal negative; killzones don't fit 24/7 crypto |
| **RMR (Robust Median Reversion)** | `run_rmr.py` | ⚠️ equity: frictionless Sharpe 0.65, ~0.4 net @2bp, dies @5bp — real-but-marginal |
| Vol / variance-risk premium | (diagnostics in campaign doc) | ⚠️ real (+4.5 vol-pts) but tail-unsafe; defined-risk doesn't pay |
| Dated basis / cross-venue spread | (diagnostics in campaign doc) | ⚠️ same premium as funding (corr +0.66) / too thin on majors |

## Scripts — what each does & how to run
All run with `uv run python scripts/<name>.py`. Data auto-fetches+caches on first run (then offline).
- **`diag_funding_carry.py`** — base-rate diagnostic of perp funding (positive 77-91% of intervals).
- **`run_funding_carry.py`** — carry strategy, carry-only P&L (optimistic +14.9%).
- **`run_funding_carry_basis.py`** — carry with REAL spot-perp basis P&L (honest +7.4%). ← the truth.
- **`validate_carry_oos.py`** — one-shot OOS holdout (2025/26): decayed to +0.8%.
- **`carry_regime_monitor.py`** — LIVE "deploy carry now?" alarm (DEPLOY if basket funding ≥10% ann).
- **`carry_paper.py`** — SAFE paper-trading harness (no real orders) → `data/crypto_paper_journal.jsonl`.
- **`run_xsec_crypto.py`** — cross-sectional momentum + BTC regime gate (failed; gate is reusable).
- **`diag_crypto_intraday.py`** — intraday base rates (conditional reversion, hour-of-day, breakout).
- **`run_intraday_momo.py`** — intraday momentum/reversion, `--tf`/`--revert`/`--vol-gate`/`--calm-gate`.
- **`run_xsec_intraday.py`** — intraday cross-sectional long-short.
- **`run_mtf_fvg.py`** — multi-TF Fair Value Gap + `--bias-gate`/`--killzone` (the look-ahead lesson).
- **`run_crypto_orb.py`** — UTC-day opening-range breakout.
- **`run_rmr.py`** — RMR on a cross-asset ETF basket with a cost sweep (the cross-domain test).

## Data archived (committed — pull-once, reuse offline)
- **`data/funding/`** (2.4M) — Binance USDⓈ-M funding rates (8h) + spot + perp 8h closes, 2021-2024,
  plus `_oos` files for 2025/26. Backs the carry edge. Source: free public Binance API.
- **`data/intraday/`** (37M) — Binance 15m & 1h OHLC for the 9-coin basket, 2023-2026. Backs all
  intraday tests. Pull-once (Binance rate-limited); reused by every intraday script.
- **`data/crypto_paper_journal.jsonl`** — standing carry paper-trade log (currently STAND ASIDE).

## Key docs
- **`docs/CRYPTO_100K_CAMPAIGN.md`** — full chronological audit trail + two-premium framework + the
  honest $10K→$100K reality (10x = cycle/directional bet, not a systematic edge).
- **`docs/CRYPTO_SYSTEM_SPEC.md`** — finalized deployable system spec: frozen carry params, regime
  trigger, sizing (≤2-3x), go-live criteria, paper runbook.
- **`HANDOFF.md`** (this folder) — next-session pickup notes.

## Methodology lessons (reusable across the whole repo)
1. **Distrust spectacular backtests — hunt the bug.** The MTF-FVG 78%-win was pure look-ahead
   (pandas left-labels HTF bars; entries fired before the bar closed). Fixed → edge vanished.
2. **Frictionless ≠ tradeable.** OPS algos (CWMR 1590×!), the viral KAMA (5394%), AI-agent repos —
   all collapse under real costs/OOS. The honest post-cost edge is always small (Sharpe 0.4-0.8).
3. **Domain decides mean-reversion:** lives on cheap dispersed equity baskets, dies on 24/7 crypto.
4. **An edge is never a repo/paper you download** — it's a validated inefficiency. The rigor is the alpha.

## Open threads / next steps (for whoever picks this up)
- **RMR on individual stocks** (more dispersion than ETFs → paper's 0.96) with realistic stock costs + OOS.
- **Build the combined folio:** IBS + TOM + RMR-on-ETFs + carry, risk-sized, report combined Sharpe/DD.
- **Carry executor** (`task #8`): thin Binance/Bybit execution layer for the carry system, deploy when
  `carry_regime_monitor.py` flips to DEPLOY (testnet first, manual-approval, ≤2-3x).
- Deterministic news/sentiment signal (the only testable thread from the LLM-agent repos).
- Regime filter on RMR to cut its −55% drawdown.
