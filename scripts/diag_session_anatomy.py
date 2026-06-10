"""Step 4, diagnostic 1 — session anatomy of ES/NQ (design years 2017-2022 ONLY).

Pure measurement, no trades simulated: establishes the base rates that the ORB (family 1),
TSMOM (family 2) and overnight (family 4) designs build on — so strategy specs are chosen from
*our* data's anatomy, not from a paper's market. Reads the committed Databento archive
(reference scope only — the 2023/24 OOS years and 2025/26 holdout stay untouched).

Measures, per symbol (pooled + per-year):
  1. session split    — overnight (16:00 -> next 09:30) vs RTH (09:30 -> 16:00) drift
  2. ORB base rate    — first-5m-bar direction -> follow-through to RTH close, in bps and in
                        units of the first-5m range (the natural ORB risk unit)
  3. OR(15m) breakout — which side of the opening range breaks first, and where the day closes
  4. gap behaviour    — overnight gap size terciles -> continuation vs fade intraday
  5. conditioning     — ORB follow-through by day-of-week and by OR-width regime
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.data import archive

NY = "America/New_York"
SYMBOLS = ["ES.c.0", "NQ.c.0"]
DESIGN_YEARS = (2017, 2022)  # inclusive — 2023/24 are OOS folds, 2025/26 sealed holdout


# --- per-day frame -----------------------------------------------------------


def daily_frame(m1: pd.DataFrame) -> pd.DataFrame:
    """One row per trading day with the session landmarks the diagnostics need."""
    rth = m1.between_time("09:30", "15:59")
    g = rth.groupby(rth.index.date)

    d = pd.DataFrame({
        "open_930": g["open"].first(),
        "close_1600": g["close"].last(),
        "rth_high": g["high"].max(),
        "rth_low": g["low"].min(),
        "n_bars": g["close"].size(),
    })

    first5 = rth.between_time("09:30", "09:34")
    g5 = first5.groupby(first5.index.date)
    d["f5_open"] = g5["open"].first()
    d["f5_close"] = g5["close"].last()
    d["f5_high"] = g5["high"].max()
    d["f5_low"] = g5["low"].min()

    or15 = rth.between_time("09:30", "09:44")
    g15 = or15.groupby(or15.index.date)
    d["or15_high"] = g15["high"].max()
    d["or15_low"] = g15["low"].min()

    # rest-of-day after the 15m opening range, for first-break detection
    rod = rth.between_time("09:45", "15:59")
    d["rod_first_break"] = _first_break(rod, d)

    # entry reference for ORB follow-through: open of the 09:35 bar
    e = rth.between_time("09:35", "09:35")
    d["entry_935"] = e["open"].groupby(e.index.date).first()

    d = d[d["n_bars"] >= 300]  # drop half days / bad days
    d.index = pd.to_datetime(d.index)

    d["overnight"] = d["open_930"] / d["close_1600"].shift(1) - 1
    d["intraday"] = d["close_1600"] / d["open_930"] - 1
    d["f5_dir"] = np.sign(d["f5_close"] - d["f5_open"])
    d["f5_range"] = d["f5_high"] - d["f5_low"]
    d["or15_width"] = d["or15_high"] - d["or15_low"]
    # ORB follow-through: enter at 09:35 open in the first-5m direction, mark at RTH close.
    d["orb_move"] = (d["close_1600"] - d["entry_935"]) * d["f5_dir"]
    d["orb_bps"] = d["orb_move"] / d["entry_935"] * 1e4
    d["orb_r"] = d["orb_move"] / d["f5_range"].replace(0.0, np.nan)
    return d


def _first_break(rod: pd.DataFrame, d: pd.DataFrame) -> pd.Series:
    """Which side of the 15m opening range trades first after 09:45 ('up'/'down'/'none')."""
    out: dict = {}
    hi, lo = d["or15_high"], d["or15_low"]
    for day, bars in rod.groupby(rod.index.date):
        if day not in hi.index or pd.isna(hi.loc[day]):
            out[day] = "none"
            continue
        up = bars.index[bars["high"] > hi.loc[day]]
        dn = bars.index[bars["low"] < lo.loc[day]]
        t_up = up[0] if len(up) else None
        t_dn = dn[0] if len(dn) else None
        if t_up is None and t_dn is None:
            out[day] = "none"
        elif t_dn is None or (t_up is not None and t_up < t_dn):
            out[day] = "up"
        else:
            out[day] = "down"
    return pd.Series(out)


# --- reporting helpers -------------------------------------------------------


def _t(x: pd.Series) -> float:
    x = x.dropna()
    if len(x) < 3 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def _line(label: str, x: pd.Series, unit: str = "bps", scale: float = 1e4) -> None:
    x = x.dropna()
    if not len(x):
        print(f"    {label:24s} n=0")
        return
    win = (x > 0).mean() * 100
    print(f"    {label:24s} n={len(x):5d}  mean={x.mean() * scale:+7.2f} {unit}  "
          f"hit={win:4.1f}%  t={_t(x):+5.2f}")


# --- main --------------------------------------------------------------------


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    y0, y1 = (int(args[0]), int(args[1])) if len(args) >= 2 else DESIGN_YEARS
    if y1 >= archive.HOLDOUT_START_YEAR:
        raise SystemExit("refusing to read holdout years in a diagnostic")
    if y1 > DESIGN_YEARS[1]:
        print(f"  !! WARNING: {y1} > design window {DESIGN_YEARS} — touching OOS years burns them")

    for sym in SYMBOLS:
        m1 = archive.read_1m(sym)  # reference scope only — holdout invisible
        m1 = m1[(m1.index.year >= y0) & (m1.index.year <= y1)]
        d = daily_frame(m1)
        print(f"\n=== {sym}  {y0}-{y1}  ({len(d)} full trading days) ===")

        print("  1. session split (log-drift per session):")
        _line("overnight 16:00->09:30", d["overnight"])
        _line("RTH 09:30->16:00", d["intraday"])
        for yr, dy in d.groupby(d.index.year):
            _line(f"  {yr} overnight", dy["overnight"])
            _line(f"  {yr} RTH", dy["intraday"])

        print("  2. ORB base rate (enter 09:35 open in first-5m direction, mark at close):")
        _line("all days (bps)", d["orb_bps"], scale=1.0)
        _line("all days (R=f5 range)", d["orb_r"], unit="R", scale=1.0)
        for yr, dy in d.groupby(d.index.year):
            _line(f"  {yr} (R)", dy["orb_r"], unit="R", scale=1.0)

        print("  3. OR(15m) first break -> day close beyond that side:")
        for side, sgn in (("up", 1), ("down", -1)):
            sub = d[d["rod_first_break"] == side]
            if not len(sub):
                continue
            lvl = sub["or15_high"] if side == "up" else sub["or15_low"]
            closed_beyond = (np.sign(sub["close_1600"] - lvl) == sgn).mean() * 100
            width = sub["or15_width"].replace(0.0, np.nan)
            ext = ((sub["close_1600"] - lvl) * sgn / width).dropna()
            print(f"    first break {side:5s}  n={len(sub):5d}  P(close beyond)={closed_beyond:4.1f}%  "
                  f"mean ext={ext.mean():+.2f} ORw  t={_t(ext):+5.2f}")

        print("  4. overnight gap terciles -> intraday continuation:")
        gap = d["overnight"].dropna()
        terc = pd.qcut(gap.abs(), 3, labels=["small", "mid", "large"])
        for b in ("small", "mid", "large"):
            days = gap.index[terc == b]
            cont = (np.sign(d.loc[days, "intraday"]) == np.sign(d.loc[days, "overnight"])).mean() * 100
            aligned = d.loc[days, "intraday"] * np.sign(d.loc[days, "overnight"])
            print(f"    |gap| {b:5s}  n={len(days):5d}  P(continue)={cont:4.1f}%  "
                  f"mean gap-aligned intraday={aligned.mean() * 1e4:+6.2f} bps  t={_t(aligned):+5.2f}")

        print("  5a. ORB follow-through (R) by day-of-week:")
        for dow, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"]):
            _line(f"{name}", d[d.index.dayofweek == dow]["orb_r"], unit="R", scale=1.0)

        print("  5b. ORB follow-through (R) by OR-width regime (vs 20d median):")
        med = d["or15_width"].rolling(20).median()
        _line("narrow OR (< median)", d[d["or15_width"] < med]["orb_r"], unit="R", scale=1.0)
        _line("wide OR  (>= median)", d[d["or15_width"] >= med]["orb_r"], unit="R", scale=1.0)


if __name__ == "__main__":
    main()
