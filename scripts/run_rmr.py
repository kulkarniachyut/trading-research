"""RMR (Robust Median Reversion) — the NYU-Stern paper's 0.96-Sharpe algo, tested with REAL costs.

The paper (Glucksman/Stern) reports RMR Sharpe 0.96 on NASDAQ-100 1998-2010 but FRICTIONLESS and
in-sample. RMR rebalances the whole book DAILY (huge turnover), so the only real question is whether
the edge survives transaction costs out-of-sample. This implements RMR exactly (Huang et al. 2013)
and sweeps cost levels on a cross-asset ETF basket, with an OOS split the paper never saw.

RMR mechanics:
  1. L1-median (geometric median, Weiszfeld) of the last w PRICE vectors -> robust predicted price.
  2. predicted price-relative x_tilde = median / today_price  (dumped names -> >1 -> expect bounce).
  3. passive-aggressive update (OLMAR form): b += lam*(x_tilde - mean(x_tilde)),
     lam = max(0, (eps - b.x_tilde)/||x_tilde-mean||^2); then Euclidean-project onto the simplex.
  4. rebalance daily. Long-only, fully invested.

Cost: per-day turnover (sum |b_target - b_drifted|) * cost_per_side. Reports frictionless + net at
several cost levels, Sharpe/CAGR/maxDD vs equal-weight buy&hold, DESIGN vs OOS.

Universe: cross-asset ETFs (no survivorship bias; dispersion across equity/bond/commodity/intl).
Usage: run_rmr.py [--w 5] [--eps 10] [--start 2007] [--oos 2017]
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from src.core.types import TimeFrame
from src.data.yfinance_provider import YFinanceProvider

UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP",
            "XLI", "XLU", "XLB", "EFA", "EEM", "GLD", "TLT", "IEF", "SLV", "DBC"]


def _opt(flag, d, cast=float):
    a = sys.argv[1:]
    return cast(a[a.index(flag) + 1]) if flag in a else d


def l1_median(points: np.ndarray, iters: int = 20, eps: float = 1e-8) -> np.ndarray:
    """Geometric median (Weiszfeld) of rows in `points` (w x m)."""
    mu = points.mean(axis=0)
    for _ in range(iters):
        d = np.linalg.norm(points - mu, axis=1)
        d = np.where(d < eps, eps, d)
        w = 1.0 / d
        mu_new = (points * w[:, None]).sum(axis=0) / w.sum()
        if np.linalg.norm(mu_new - mu) < eps:
            break
        mu = mu_new
    return mu


def simplex_project(v: np.ndarray) -> np.ndarray:
    """Euclidean projection onto the probability simplex (long-only, sums to 1)."""
    u = np.sort(v)[::-1]
    css = np.cumsum(u)
    rho = np.nonzero(u * np.arange(1, len(u) + 1) > (css - 1))[0][-1]
    theta = (css[rho] - 1) / (rho + 1.0)
    return np.maximum(v - theta, 0)


def rmr_backtest(prices: pd.DataFrame, w: int, eps: float, cost_side: float):
    """Return (gross_daily, net_daily) portfolio return Series. prices: T x m (adjusted closes)."""
    P = prices.values
    T, m = P.shape
    b = np.ones(m) / m
    gross, net = {}, {}
    idx = prices.index
    for t in range(w, T - 1):
        window = P[t - w + 1:t + 1]            # last w price vectors (causal, through today t)
        med = l1_median(window)
        x_tilde = med / P[t]                   # predicted next-day price relative
        x_bar = x_tilde.mean()
        denom = np.sum((x_tilde - x_bar) ** 2)
        lam = 0.0 if denom < 1e-12 else max(0.0, (eps - b @ x_tilde) / denom)
        b_new = simplex_project(b + lam * (x_tilde - x_bar))
        # realized next-day return
        x_real = P[t + 1] / P[t]
        # weights drift intraday-of-holding from b_new; turnover measured vs previous drifted book
        drift = b * x_real / (b @ x_real)
        turnover = np.sum(np.abs(b_new - drift))
        port_ret = b_new @ x_real - 1.0
        gross[idx[t + 1]] = port_ret
        net[idx[t + 1]] = port_ret - turnover * cost_side
        b = b_new
    return pd.Series(gross), pd.Series(net)


def _stats(label, r):
    if not len(r):
        print(f"  {label}: no data"); return
    ann = (1 + r.mean()) ** 252 - 1
    sharpe = (r.mean() - 0.05 / 252) / r.std() * np.sqrt(252) if r.std() else 0
    curve = (1 + r).cumprod()
    dd = (curve / curve.cummax() - 1).min()
    print(f"  {label:22s} CAGR {ann*100:+7.1f}%  Sharpe {sharpe:+5.2f}  maxDD {dd*100:6.1f}%  "
          f"final {curve.iloc[-1]:6.2f}x")


def main():
    w = _opt("--w", 5, int); eps = _opt("--eps", 10.0); y0 = _opt("--start", 2007, int)
    oos = _opt("--oos", 2017, int)
    prov = YFinanceProvider()
    start = pd.Timestamp(f"{y0}-01-01", tz="America/New_York")
    end = pd.Timestamp("2026-06-13", tz="America/New_York")
    cols = {}
    for s in UNIVERSE:
        try:
            d = prov.get_bars(s, TimeFrame.D1, start, end)
            if d is not None and len(d) > 250:
                cols[s] = d["close"]
        except Exception as exc:  # noqa: BLE001
            print(f"  {s}: {exc}")
    px = pd.DataFrame(cols).dropna()
    print(f"=== RMR (Robust Median Reversion)  w={w} eps={eps}  univ={px.shape[1]} ETFs  "
          f"{px.index[0].date()}..{px.index[-1].date()} ===")
    bh = px.pct_change().mean(axis=1).dropna()  # equal-weight buy&hold

    for cost_bps in [0.0, 2.0, 5.0, 10.0]:
        g, n = rmr_backtest(px, w, eps, cost_bps / 1e4)
        tag = "FRICTIONLESS" if cost_bps == 0 else f"cost {cost_bps:.0f}bp/side"
        print(f"\n  --- {tag} ---")
        _stats("RMR full", n)
        for label, mask in [("RMR DESIGN<%d" % oos, n.index.year < oos),
                            ("RMR OOS>=%d" % oos, n.index.year >= oos)]:
            _stats(label, n[mask])
    print()
    _stats("Buy&Hold (EW) full", bh)
    print("  NOTE: turnover cost is the whole question -- RMR rebalances the full book daily.")


if __name__ == "__main__":
    main()
