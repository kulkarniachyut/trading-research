"""data_pull.py — the ONE sanctioned online path to Databento. Everything else reads the archive.

Databento historical is metered against a finite free-credit balance, so spending is dangerous to do
implicitly. This script makes it explicit and cheap-to-repeat:

- **Canonical 1-minute only.** It pulls ``ohlcv-1m`` and banks it into ``src/data/archive.py``; every
  higher timeframe is derived locally at read time, so all timeframes are covered by one pull.
- **Cost guard / dry-run by default.** It first asks Databento for a cost *estimate* (no data moves)
  and prints a per-(symbol, year) table with the total. It downloads nothing unless you pass ``--yes``.
- **Idempotent.** Years already covered in the archive are skipped, so re-running is free and safe.
- **Holdout-aware.** Years >= 2025 route to the sealed ``holdout/`` scope automatically.

Usage:
    uv run python scripts/data_pull.py                         # dry-run: estimate cost for default universe, reference years
    uv run python scripts/data_pull.py --years 2021-2024       # estimate a year range
    uv run python scripts/data_pull.py --years 2021-2024 --yes # actually download + archive
    uv run python scripts/data_pull.py --symbols ES.c.0,NQ.c.0 --years 2022-2022 --yes
    uv run python scripts/data_pull.py --years 2025-2026 --yes # bank the sealed holdout (kept out of tuning)

Needs the ``data`` extra (``uv sync --extra data``) and ``DATABENTO_API_KEY`` in ``.env`` / env.
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from src.core.config import databento_api_key
from src.core.types import TimeFrame
from src.data import archive
from src.data.normalize import normalize_bars

_DATASET = "GLBX.MDP3"
_SCHEMA = "ohlcv-1m"

# The research universe: index micros/minis + FX + metal, continuous front-month (calendar-rolled).
# Specs (point value / tick) live with the backtest runner; the pull only needs the symbols.
DEFAULT_SYMBOLS = [
    "ES.c.0", "NQ.c.0", "RTY.c.0", "YM.c.0", "GC.c.0",   # equity index + gold
    "6E.c.0", "6B.c.0", "6J.c.0", "6A.c.0",              # FX: EUR / GBP / JPY / AUD
]


def _parse_years(spec: str) -> list[int]:
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(spec)]


def _covered(symbol: str, year: int) -> bool:
    """True if the whole calendar year is already inside the archived coverage for its scope."""
    scope = archive.scope_for_year(year)
    df = archive.read_1m(symbol, scope)
    if not len(df):
        return False
    yr_start = pd.Timestamp(f"{year}-01-01", tz=archive.NY_TZ)
    yr_end = pd.Timestamp(f"{year}-12-31 23:59", tz=archive.NY_TZ)
    return df.index[0] <= yr_start and df.index[-1] >= yr_end


def _client(api_key: str):
    import databento as db

    return db.Historical(api_key)


def _to_ohlcv(dbnstore) -> pd.DataFrame:
    """Databento ``DBNStore`` → raw OHLCV frame (UTC index). normalize_bars handles tz/sort/dedupe."""
    df = dbnstore.to_df()
    if df is None or len(df) == 0:
        return pd.DataFrame()
    cols = {c.lower(): c for c in df.columns}
    keep = {std: cols[std] for std in ("open", "high", "low", "close", "volume") if std in cols}
    out = df[list(keep.values())].rename(columns={v: k for k, v in keep.items()})
    if out.index.tz is None:
        out.index = out.index.tz_localize("UTC")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS),
                    help="comma-separated continuous symbols (default: full research universe)")
    ap.add_argument("--years", default="2021-2024",
                    help="year or YYYY-YYYY range (default 2021-2024; 2025+ routes to sealed holdout)")
    ap.add_argument("--yes", action="store_true", help="actually download (default: estimate only)")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    years = _parse_years(args.years)

    key = databento_api_key()
    if not key:
        sys.exit("DATABENTO_API_KEY not found (set it in .env or the environment).")

    client = _client(key)

    # 1. Plan: which (symbol, year) jobs are missing, and what each is estimated to cost.
    jobs: list[tuple[str, int, float]] = []
    skipped = 0
    print(f"Dataset {_DATASET}  schema {_SCHEMA}  (cost estimates — no data moves yet)\n")
    for sym in symbols:
        for yr in years:
            if _covered(sym, yr):
                skipped += 1
                continue
            start, end = f"{yr}-01-01", f"{yr + 1}-01-01"
            cost = client.metadata.get_cost(
                dataset=_DATASET, symbols=sym, schema=_SCHEMA,
                stype_in="continuous", start=start, end=end,
            )
            scope = archive.scope_for_year(yr)
            tag = "  [HOLDOUT]" if scope == archive.HOLDOUT else ""
            print(f"  {sym:8s} {yr}  ~${cost:7.4f}{tag}")
            jobs.append((sym, yr, float(cost)))

    total = sum(c for _, _, c in jobs)
    print(f"\n{len(jobs)} job(s) to fetch, {skipped} already archived.  "
          f"Estimated total: ${total:.4f}")

    if not jobs:
        print("Nothing to do — archive already covers the request.")
        return
    if not args.yes:
        print("\nDry run. Re-run with --yes to download and archive these.")
        return

    # 2. Download + bank, one (symbol, year) at a time (bounded memory; partial progress survives).
    print()
    for sym, yr, _cost in jobs:
        start, end = f"{yr}-01-01", f"{yr + 1}-01-01"
        store = client.timeseries.get_range(
            dataset=_DATASET, symbols=sym, schema=_SCHEMA,
            stype_in="continuous",
            start=pd.Timestamp(start, tz="UTC"), end=pd.Timestamp(end, tz="UTC"),
        )
        raw = _to_ohlcv(store)
        bars = normalize_bars(raw, TimeFrame.M1, include_forming=False, now=None, rth=False)
        scope = archive.scope_for_year(yr)
        total_rows = archive.write_1m(sym, bars, scope)
        print(f"  {sym:8s} {yr}  +{len(bars):>7,} bars  ({scope}, {total_rows:,} total)", flush=True)

    manifest = archive.write_manifest()
    n = sum(len(v) for v in manifest["coverage"].values())
    print(f"\nArchived. manifest.json updated ({n} symbol-scope series). Backtests now read offline.")


if __name__ == "__main__":
    main()
