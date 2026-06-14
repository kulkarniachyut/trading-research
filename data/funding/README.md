# Binance funding-rate archive (durable, committed)

Pulled once from the **free public Binance USDⓈ-M API** by the crypto-$100K campaign and committed
so no session re-fetches (the API is rate-limited). Reused offline by all carry scripts.

## Contents
- `<SYMBOL>.parquet` — 8h funding-rate history, 2021-01-01 → 2024-12-31 (e.g., `BTCUSDT.parquet`).
- `<SYMBOL>_spot_8h.parquet` / `<SYMBOL>_perp_8h.parquet` — 8h close prices (spot via `api.binance.com`,
  perp via `fapi.binance.com`) for the same window — used to compute the real spot-perp **basis P&L**.
- `<SYMBOL>_*_oos.parquet` — the **2025/26 OOS holdout** pull (funding + spot + perp), used once by
  `validate_carry_oos.py`.

## Universe (9-coin basket, ex-BNB)
BTC ETH SOL XRP DOGE ADA AVAX LINK LTC USDT pairs (BNB excluded — anomalous funding).

## Regenerate (if ever needed)
`uv run python scripts/diag_funding_carry.py --refresh` (funding) — klines re-fetch automatically
via `run_funding_carry_basis.py` / `validate_carry_oos.py`.

## Provenance / caveats
Source: Binance public REST (no key). Funding is the perp funding rate longs pay shorts (8h cadence).
Binance is a data proxy; a user trades on their own venue (funding tracks closely across major CEXs).
