# Crypto $100K Campaign — Handoff

_For the next session. Read `README.md` (this folder) first for the full index._

## State as of handoff (2026-06-14)
- **Research phase: complete and exhaustive.** ~55 strategy variants tested across crypto +
  equities, all causal, OOS-split, post-cost. One survivor (funding carry, parked/regime-gated);
  everything else dead, decayed, or look-ahead. See the verdict table in `README.md`.
- **Nothing is running.** No live capital, no automated loop. `carry_paper.py` is a manual paper
  harness (currently logs STAND ASIDE — the funding regime is compressed).
- **Best deployable Sharpe in the project:** ~0.45 live (IBS+TOM, on the equity track) → ~0.8 if the
  parallel 3-sleeve book holds. Carry is Sharpe ~7 *but dormant* (market-neutral + regime-gated).

## The honest conclusion (do not re-litigate without new info)
$10K→$100K in a year is NOT achievable via risk-managed systematic trading — it's a high-variance
cycle/directional bet (documented as "Path B" in `CRYPTO_100K_CAMPAIGN.md`). The legitimate path is
stacking small uncorrelated edges (carry + IBS + TOM + maybe RMR) and leveraging the combination
≤2-3x, targeting ~15-25% over a cycle. Resist "one giant-Sharpe strategy" — it's always an in-sample
mirage (proven repeatedly here: FVG look-ahead, OPS frictionless, viral KAMA).

## Immediate pickup options (pick one)
1. **Build the combined folio** (highest value): IBS + TOM + RMR-on-ETFs + carry into one risk-sized
   book; report combined Sharpe / CAGR / drawdown / correlation matrix. This is the real "folio".
2. **RMR on individual stocks** (`run_rmr.py` adapts easily — swap the ETF universe for ~40 liquid
   large-caps): more dispersion → test whether the paper's 0.96 survives ~3-5bp stock costs + OOS.
3. **Carry executor** (Step-6 plumbing): Binance/Bybit thin execution layer behind the Broker
   interface; deploy carry at ≤2-3x when `carry_regime_monitor.py` flips to DEPLOY. Testnet + manual-approval first.

## Branch / merge notes
- Work is on `crypto-100k-campaign` → PR #21. The campaign commits are `c1a9775..HEAD`.
- ⚠️ One pre-existing commit from a concurrent `pairs-statarb` workstream (`de4a1cc`) sits at the base
  (shared working tree — multiple agents). It's a completed pairs result, harmless; a squash-merge to
  main collapses it. Flagged for transparency.
- **Data is committed** (gitignore negations for `data/funding/**` and `data/intraday/**`) — durable,
  pull-once Binance archive. Do not delete; re-fetching is rate-limited.

## Cross-references
- Memory: `crypto-funding-carry-validated`, `step4-edge-search-status`, `vmc-cipher-crypto-result`.
- Related parallel work (other agents, this repo): VMC-cipher, pairs-statarb, trend-overlay,
  vix-term-structure, portfolio-frontier, step6-allocator — each on its own branch.
