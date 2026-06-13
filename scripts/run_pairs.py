"""Pairs / statistical-arbitrage — go-wide brick #8, the MARKET-NEUTRAL diversifier.

Unlike the VIX sleeve (which raises return by taking crash risk), pairs trading is dollar- and
beta-neutral: long the cheap leg / short the rich leg of an economically-related ETF pair when
their spread is stretched, exit on mean-reversion. If it works, it raises the *safe* return
ceiling (no crash beta) — the missing piece the 2-edge frontier needs. Honest prior: classic
pairs edges have largely decayed post-2010 (heavily arbitraged); a clean null is expected-fine.

Method (theory-typical, not tuned): rolling hedge ratio beta (OLS, `win` days); spread =
logP1 - beta*logP2; z = rolling z-score(spread). Enter when |z| >= Z_ENTER (short spread if z>0),
exit when |z| <= Z_EXIT, stop when |z| >= Z_STOP. Dollar-neutral ($1 leg1 / $beta leg2). Cost
~3 bps/side on both legs. No look-ahead (z from data through t, P&L earned t+1).

Pre-registered in docs/STEP4_EDGE_SEARCH_PLAN.md.

Usage: run_pairs.py [START_YEAR END_YEAR]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.core.types import TimeFrame
from src.data.yfinance_provider import YFinanceProvider
from src.validation import monte_carlo

PAIRS = [("XLF", "XLK"), ("XLE", "XOP"), ("GLD", "SLV"), ("SPY", "QQQ"),
         ("IEF", "TLT"), ("EFA", "EEM"), ("XLP", "XLU")]
WIN, Z_ENTER, Z_EXIT, Z_STOP = 60, 2.0, 0.5, 3.5
COST = 0.0003


def closes(prov, sym, y0, y1):
    s = pd.Timestamp(f"{y0 - 1}-01-01", tz="America/New_York")
    e = pd.Timestamp(f"{y1}-12-31", tz="America/New_York")
    d = prov.get_bars(sym, TimeFrame.D1, s, e)
    return d["close"].dropna() if d is not None and len(d) else pd.Series(dtype=float)


def pair_daily(p1: pd.Series, p2: pd.Series, y0: int, y1: int) -> pd.Series:
    df = pd.DataFrame({"a": p1, "b": p2}).dropna()
    la, lb = np.log(df["a"]), np.log(df["b"])
    beta = (la.rolling(WIN).cov(lb) / lb.rolling(WIN).var())
    spread = la - beta * lb
    z = (spread - spread.rolling(WIN).mean()) / spread.rolling(WIN).std()
    ra, rb = df["a"].pct_change(), df["b"].pct_change()
    pos = 0.0
    out: dict[pd.Timestamp, float] = {}
    zz = z.values
    for i in range(WIN + 1, len(df) - 1):
        zi = zz[i]
        if np.isnan(zi):
            continue
        # update position on today's z (acts on next day's spread return)
        if pos == 0.0:
            if zi >= Z_ENTER:
                pos = -1.0  # spread rich -> short spread (short a, long b)
            elif zi <= -Z_ENTER:
                pos = +1.0
        else:
            if abs(zi) <= Z_EXIT or abs(zi) >= Z_STOP:
                pos = 0.0
        nxt = df.index[i + 1]
        if pos != 0.0 and y0 <= nxt.year <= y1:
            b = beta.iloc[i] if not np.isnan(beta.iloc[i]) else 1.0
            spread_ret = ra.iloc[i + 1] - b * rb.iloc[i + 1]
            gross = (1 + abs(b))
            # cost only when position changed this step is approximated by per-bar holding;
            # charge a round-trip on entry/exit days
            chg = 1.0 if (i > 0 and ((pos != 0) != (out.get(df.index[i], None) is not None))) else 0.0
            out[nxt] = pos * spread_ret / gross - chg * 2 * COST
    return pd.Series(out)


def _stats(label, r):
    if not len(r) or r.std() == 0:
        print(f"  {label:14s} n={len(r)}  (no edge / flat)")
        return None
    sh = r.mean() / r.std() * np.sqrt(252)
    ann = (1 + r).prod() ** (252 / len(r)) - 1
    print(f"  {label:14s} days-in {len(r):4d}  ann {ann * 100:+6.1f}%  Sharpe {sh:+.2f}  "
          f"win {(r > 0).mean() * 100:3.0f}%")
    return sh


def main() -> None:
    args = [a for a in sys.argv[1:] if a.isdigit() and len(a) == 4]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else (2010, 2024)
    prov = YFinanceProvider()
    print(f"=== pairs / stat-arb  {y0}-{y1}  ({len(PAIRS)} pairs, z={Z_ENTER}/{Z_EXIT}/{Z_STOP}, "
          f"win={WIN}) ===")
    all_days: list[pd.Series] = []
    for a, b in PAIRS:
        r = pair_daily(closes(prov, a, y0, y1), closes(prov, b, y0, y1), y0, y1)
        _stats(f"{a}/{b}", r)
        if len(r):
            all_days.append(r)
    if not all_days:
        print("  no trades")
        return
    book = pd.concat(all_days, axis=1).fillna(0).mean(axis=1)  # equal-weight across pairs, daily
    book = book[(book.index.year >= y0) & (book.index.year <= y1)]
    print("  ---")
    sh = _stats("POOLED book", book)
    spy = closes(prov, "SPY", y0, y1).pct_change().reindex(book.index).fillna(0)
    print(f"  market-neutrality: corr(book, SPY) = {np.corrcoef(book, spy)[0, 1]:+.2f}")
    mc = monte_carlo(list(book), n_resamples=2000, seed=42)
    print(f"  MC: p5 total {mc.p5_total_r * 100:+.0f}%  P(<=0) {mc.prob_total_r_le_0 * 100:.1f}%  "
          f"-> {'SURVIVES' if mc.survives else 'FAILS'}")
    half = book[book.index.year <= (y0 + y1) // 2]
    if len(half) and half.std():
        mc2 = monte_carlo(list(half), n_resamples=2000, seed=42)
        print(f"  MC first-half: P(<=0) {mc2.prob_total_r_le_0 * 100:.1f}%  -> "
              f"{'SURVIVES' if mc2.survives else 'FAILS'}")


if __name__ == "__main__":
    main()
