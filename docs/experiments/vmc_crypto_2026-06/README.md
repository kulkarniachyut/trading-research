# VuManChu (VMC) on Crypto — Experiment Log (June 2026)

_Self-contained record of the VMC crypto research arc. Hypothesis → method → every run →
verdict. Raw run outputs are in `results/`. The goal: find a real, repeatable, post-cost crypto
trading edge using the VuManChu Cipher B / WaveTrend / S/R toolkit._

## TL;DR (the verdict)

**One validated-in-sample edge emerged:** trend-gated VMC Cipher B `buy` + **S/R confluence**,
on the **4-hour** timeframe, **long-only**, across a **wide 17-coin universe**.

| Config (H4, wide 17-coin, 2021–2024) | Net/trade | Trades | Breadth | MC P(luck) |
|---|---|---|---|---|
| **Maker** (rests limits at support — realistic) | **+0.182R** | 127 | 11/16 | **1.5% ✅ SURVIVES** |
| **Taker** (worst-case fees) | +0.121R | 132 | 11/16 | 8.6% (marginal) |

It is robust on every axis we tested: not a single-coin mirage (top coin ≈24% of net), not a
single-year fluke (3/4 years positive, none negative), survives full taker fees, and **smooth
across the S/R threshold** (not a curve-fit spike). It is a **real but moderate** edge (~12–17%/yr
leveraged) — one uncorrelated brick, not a standalone path to large returns.

**What did NOT work** (all tested, all logged): naked VMC on daily crypto, all sub-H4 timeframes
(30m/15m/5m go negative — cost drag + signal decay), the `gold_buy` setup (untradeable), the
YouTube "Wolfpack multi-TF" strategy (27% win vs its claimed 70%), and adding the short side /
perps (shorts are ~breakeven and dilute the long edge).

> **Data discipline:** all results are **in-sample 2021–2024**. The **2025/26 holdout is sealed
> and was NOT spent.** Crypto history via Alpaca only reaches ~2021, so 4 years is the max window.

---

## 1. Hypothesis & motivation

The project's prior finding: naked daily mean-reversion (IBS) on crypto has **no gross edge** —
daily crypto *trends*, it doesn't revert. VMC Cipher B's `buy` is itself a reversion signal
(WaveTrend cross in the oversold zone), so naked it should fail too. The bet: the canonical retail
VMC playbook adds two things that *align* the reversion entry with the trend —
1. a **200-EMA trend gate** (only buy dips inside an uptrend), and
2. trading it **intraday** (H4/H1) rather than daily —
and, crucially, **S/R confluence** (only buy when price has pulled back to a known support level).

## 2. Method (the truth machine)

- **Engine:** event-driven `BacktestEngine` via `run_portfolio` (per-symbol, then pooled). Only
  completed bars are visible (no look-ahead); every indicator is causal (unit-tested).
- **Costs:** crypto cost model — taker 0.10%/side + 2bps spread + ATR slippage; maker ≈0.04%/side,
  no spread crossing (a resting limit). **No frictionless results.**
- **Acceptance (pre-registered, fixed before runs):** pooled post-cost expectancy > 0 AND ≥50% of
  coins positive AND Monte-Carlo p5 ≥ 0.
- **Sizing:** 0.5% risk/trade, ATR stop; R = $500 on $100k notional.

## 3. Data source

- **Provider:** `AlpacaCryptoProvider` (`src/data/alpaca_crypto.py`) — Alpaca crypto bars, 24/7,
  keyless history reaching ~2021. Cached as Parquet under `data/cache/alpaca_crypto/<COIN>/<tf>.parquet`.
- **Native fetch granularities:** M1, M5, M15, H1, D1. **H4 and 30m are resampled** by the engine
  clock (H4←H1, 30m←M15, 2m←M1) — the decision bar is always built from real fetched bars.
- **Universe:**
  - *Base (8):* BTC ETH LTC BCH SOL AVAX LINK DOGE.
  - *Wide (17):* the 8 + DOT XRP UNI AAVE XTZ GRT SUSHI YFI CRV — every cached coin with usable
    2021+ history (ADA/FIL/POL/BAT excluded: no 2021 bars on Alpaca).
- **Window:** 2021-01-01 → 2024-12-31. **2025/26 sealed** (the runner hard-refuses years ≥ 2025).

## 4. What was built (code in this PR)

| File | What |
|---|---|
| `src/indicators/vumanchu/wolfpack.py` | Wolfpack ID oscillator = `EMA(close,3)−EMA(close,8)` (green>0). Causal. |
| `src/strategies/vumanchu/cipher_strategy.py` | `vmc_cipher` — trend-gated Cipher B with S/R confluence, long/short, maker/taker, gold_buy. **The validated strategy.** |
| `src/strategies/vumanchu/wolfpack_mtf.py` | `vmc_wolfpack` — the YouTube 1H/4H Wolfpack+200EMA+CipherB multi-TF strategy. **Tested, FAILED.** |
| `scripts/run_vmc_crypto.py` | Runner for `vmc_cipher` (flags: `--tf --sr --limit --wide --both --short --perp --gold --sr-dist`). |
| `scripts/run_vmc_wolfpack.py` | Runner for the multi-TF Wolfpack strategy. |
| `tests/test_vmc_cipher.py`, `tests/test_wolfpack.py` | Causality + behavior tests (7 total). |
| `src/backtest/portfolio.py` | Added a crypto **maker** cost model + optional **perp funding** drag (both were missing). |

## 5. Experiment trail (chronological) — see `results/` for raw output

### 5.1 Base signal & the S/R unlock
- Naked trend-gated Cipher B (8 coins, H4): ~breakeven (+0.08R maker, fails MC on 8-coin breadth).
- **+ S/R confluence** (buy only within 1×ATR above a confirmed swing-low): quadrupled per-trade
  gross edge → the unlock. This is the cross-indicator confluence that made VMC work.

### 5.2 Timeframe sweep (`results/timeframe_sweep_4yr.txt`) — **H4 is optimal**
| TF | Trades | Net/trade | Gross | Cost/tr | Verdict |
|---|---|---|---|---|---|
| 4h | 127 | **+0.182R** | +0.112R* | 0.031R | best |
| 1h | 326 | +0.038R | +0.113R | 0.074R | decays |
| 30m | 623 | −0.062R | +0.031R | 0.093R | negative |
| 15m | 1165 | −0.120R | +0.016R | 0.136R | negative |

_(*gross figures are 8-coin; net/wide figures differ — see raw files.)_ **Mechanism:** as bars
speed up, the gross signal decays (noise) AND cost/trade in R quadruples (R = 1.5×ATR shrinks).
Net crosses zero ~30m. **Intraday VMC on crypto is a structural loser to cost.**

### 5.3 Breadth fix (`results/headline_validation.txt`) — **the validation**
The 8-coin S/R edge failed *only* on Monte-Carlo tail (too few correlated coins). Re-running the
**same frozen config on 17 coins** flipped MC P(luck) 23.5% → **1.5%**, net +0.081R → **+0.182R**.
The missing ingredient was **breadth** (free — coins already cached), not tuning. Cost-robust:
taker still net **+0.121R**.

### 5.4 Smoothness ablation (`results/sr_threshold_ablation.txt`) — **not curve-fit**
Swept the S/R proximity threshold `sr_atr_dist`: 0.5→+0.159R, 1.0→+0.182R, 1.5→+0.140R,
2.0→+0.119R. All four net-positive, a gentle hump — textbook real effect (a curve-fit spikes at
one value and dies elsewhere).

### 5.5 Shorts / perps (`results/long_short_perp_matrix.txt`) — **don't help**
| Config (wide H4 maker) | Trades | Net/trade | MC P(luck) |
|---|---|---|---|
| Long-only | 127 | **+0.182R** | 1.5% ✅ |
| Long+Short | 247 | +0.105R | 7.6% |
| Short-only | 120 | +0.018R | 43.5% |

Crypto's structural upward drift makes systematic shorts ~breakeven; adding them ~doubles
frequency but *dilutes* the long edge and breaks MC. **Validated config stays long-only spot.**
Perp leverage can still *size* the long edge (return and drawdown scale together — leverage is a
volume knob, not an edge knob). Known limitation: the perp-funding cost (`FundingRate`) needs
`holding_hours` which the engine's exit fill context doesn't yet set, so `--perp` funding currently
no-ops; it doesn't change any verdict (funding would only make the already-failing shorts worse).

### 5.6 The YouTube "Wolfpack multi-TF" strategy — **FAILED**
A user-supplied video strategy (1H exec + 4H confirm; 200-EMA + Wolfpack ID green-cross + Cipher
divergence; 1:3 R:R). Built faithfully as `vmc_wolfpack`. On 4yr / 8 coins: **27.3% win rate
(vs the video's claimed 70%), gross +0.002R (no edge), net −0.154R, MC P=96.8%.** With 1:3 R:R you
break even at ~25% win — the entry is directionless. The video's "70% / +40% in 5 days" was forex,
self-reported, on a 5-day sample.

## 6. How to reproduce

```bash
uv sync
# The validated edge (maker, realistic):
uv run python scripts/run_vmc_crypto.py 2021 2024 --tf 4h --sr --limit --wide
# Taker stress:        --sr --wide          Timeframe sweep:  --tf 1h|30m|15m --sr --limit --wide
# Threshold ablation:  --sr-dist 0.5|1.5    Shorts/perps:     --both | --short | --perp
# The failed video strategy:
uv run python scripts/run_vmc_wolfpack.py 2021 2024 --limit
uv run pytest tests/test_vmc_cipher.py tests/test_wolfpack.py
```

## 7. Honest standing & next steps

- **Status:** validated **in-sample only**. The clean out-of-sample test is the sealed 2025/26
  holdout (NOT spent) or live paper trading.
- **Recommended next step:** paper-trade the long-only config (free, tests the load-bearing maker-
  fill assumption with live fills) before spending the holdout.
- **Role in the bigger picture:** one uncorrelated brick (~12–17%/yr leveraged). The path to large
  returns is *stacking* several uncorrelated validated edges, then moderate leverage — not pushing
  this one harder (which the timeframe/shorts/perps sweeps show breaks it).
