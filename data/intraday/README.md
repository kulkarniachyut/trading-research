# Binance intraday OHLC archive (durable, committed)

Pulled once from the **free public Binance spot API** (`api.binance.com/api/v3/klines`) by the
crypto-$100K campaign and committed (the API is rate-limited; full 15m history takes minutes).
Reused offline by every intraday script.

## Contents
- `<SYMBOL>_1h.parquet` — 1h close series, 2023-01-01 → 2026-06-13.
- `<SYMBOL>_15m.parquet` — 15m close series, same window.
- `<SYMBOL>_15m_ohlc.parquet` — 15m OHLC (open/high/low/close) — needed for FVG/ORB high-low logic.

## Universe
The 9-coin basket: BTC ETH SOL XRP DOGE ADA AVAX LINK LTC (USDT pairs). (ETH 15m occasionally thin.)

## Used by
`diag_crypto_intraday.py`, `run_intraday_momo.py`, `run_xsec_intraday.py`, `run_mtf_fvg.py`,
`run_crypto_orb.py`. All intraday tests **failed** OOS (see ../docs/experiments/crypto_100k/README.md)
— the data is kept so future intraday ideas can reuse it without re-fetching.

## Regenerate
Delete a file and re-run any consumer, or `fetch_klines(sym, tf, refresh=True)` in
`scripts/diag_crypto_intraday.py`.
