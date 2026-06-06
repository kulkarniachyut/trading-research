"""Walk-forward validation — the OOS spine for Phase E.

A real edge survives being measured on data it was never chosen on. Walk-forward enforces that:
each fold has a *train* span and a strictly-later *test* span; the strategy's test result counts
only on the test span. Because the ICT-2022 defaults are theory-led (not fit to a price series),
the train step is *optional* — by default we measure the fixed full setup and the train span is
informational only. When ``select`` is supplied, it may pick params from ``candidates`` using the
train PortfolioResult, but the chosen params are then judged solely on the held-out test span.

No-look-ahead by construction: a fold's ``test_start`` is always ``>= train_end`` (assert-checked),
folds are built only from *completed* calendar years, and the pooled OOS metric concatenates the
per-fold *test* trades — never the train trades. Calls ``run_portfolio`` once per span, so the cost
model, per-symbol isolation, and breadth aggregation are inherited unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from src.backtest.portfolio import PortfolioResult, UniverseItem, run_portfolio
from src.core.types import Trade
from src.strategies.base import BaseStrategy

NY = "America/New_York"


@dataclass(frozen=True, slots=True)
class Fold:
    """One train→test split. Spans are inclusive ``[start, end]`` timestamps."""

    label: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    def __post_init__(self) -> None:
        # The single invariant that makes this a *walk-forward*: test never precedes train.
        if self.test_start < self.train_end:
            raise ValueError(
                f"fold {self.label!r} leaks: test_start {self.test_start} < train_end {self.train_end}"
            )


@dataclass
class FoldResult:
    fold: Fold
    params: dict           # params used on the test span (fixed default, or picked on train)
    test: PortfolioResult
    train: Optional[PortfolioResult] = None  # None when no tuning was done

    @property
    def test_expectancy_r(self) -> float:
        return self.test.expectancy_r

    @property
    def test_trade_count(self) -> int:
        return self.test.trade_count


@dataclass
class WalkForwardResult:
    """All folds plus pooled out-of-sample metrics (the headline Phase-E read)."""

    folds: list[FoldResult]
    risk_pct: float
    initial_equity: float

    # --- pooled OOS: concatenate every fold's TEST trades (never train) -------
    @property
    def tagged_test_trades(self) -> list[tuple[str, Trade]]:
        out = [(sym, t) for fr in self.folds for sym, t in fr.test.tagged_trades]
        out.sort(key=lambda st: st[1].exit_ts)
        return out

    def _all(self) -> list[Trade]:
        return [t for _, t in self.tagged_test_trades]

    @property
    def trade_count(self) -> int:
        return len(self._all())

    @property
    def win_rate(self) -> float:
        ts = self._all()
        return sum(1 for t in ts if t.net_pnl > 0) / len(ts) * 100 if ts else 0.0

    @property
    def total_net(self) -> float:
        return sum(t.net_pnl for t in self._all())

    @property
    def _risk_denom(self) -> float:
        return self.risk_pct * self.initial_equity

    @property
    def expectancy_dollars(self) -> float:
        ts = self._all()
        return self.total_net / len(ts) if ts else 0.0

    @property
    def expectancy_r(self) -> float:
        return self.expectancy_dollars / self._risk_denom if self._risk_denom else 0.0

    @property
    def returns_r(self) -> list[float]:
        """Per-trade net R across all pooled OOS trades — the input to Monte-Carlo."""
        denom = self._risk_denom
        return [t.net_pnl / denom for t in self._all()] if denom else []

    def per_symbol(self) -> list[tuple[str, int, float, float]]:
        """Pooled-OOS (symbol, n, win%, net$) across all folds, sorted by net descending."""
        agg: dict[str, list[Trade]] = {}
        for sym, t in self.tagged_test_trades:
            agg.setdefault(sym, []).append(t)
        rows = []
        for sym, ts in agg.items():
            n = len(ts)
            win = sum(1 for t in ts if t.net_pnl > 0) / n * 100 if n else 0.0
            rows.append((sym, n, win, sum(t.net_pnl for t in ts)))
        rows.sort(key=lambda x: x[3], reverse=True)
        return rows

    @property
    def breadth_positive(self) -> float:
        """Fraction of traded symbols with positive pooled-OOS net — the anti
        "one symbol carries the edge" check. 1.0 = every symbol contributes, 0.0 = none."""
        rows = [r for r in self.per_symbol() if r[1] > 0]
        return sum(1 for r in rows if r[3] > 0) / len(rows) if rows else 0.0


def year_span(year: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calendar-year span as NY timestamps (``Jan 1 .. Dec 31``), inclusive."""
    return (pd.Timestamp(f"{year}-01-01", tz=NY), pd.Timestamp(f"{year}-12-31", tz=NY))


def make_folds(years: list[int], *, scheme: str = "anchored", train_size: int = 1) -> list[Fold]:
    """Build per-year train→test folds from *sorted, completed* years.

    ``anchored`` (default): test year[i], train on *all* prior years (growing window) — the
    standard WF that uses every past observation. ``rolling``: train on the preceding
    ``train_size`` years only (fixed window). Either way each later year is tested exactly once,
    so pooling the test trades double-counts nothing.
    """
    ys = sorted(set(years))
    if len(ys) < 2:
        raise ValueError(f"need >= 2 years to walk forward, got {ys}")
    folds: list[Fold] = []
    for i in range(1, len(ys)):
        if scheme == "anchored":
            train_years = ys[:i]
        elif scheme == "rolling":
            train_years = ys[max(0, i - train_size):i]
        else:
            raise ValueError(f"unknown scheme {scheme!r} (anchored|rolling)")
        train_start, _ = year_span(train_years[0])
        _, train_end = year_span(train_years[-1])
        test_start, test_end = year_span(ys[i])
        folds.append(Fold(
            label=f"train {train_years[0]}-{train_years[-1]} → test {ys[i]}",
            train_start=train_start, train_end=train_end,
            test_start=test_start, test_end=test_end,
        ))
    return folds


def walk_forward(
    make_strategy: Callable[..., BaseStrategy],
    universe: list[UniverseItem],
    folds: list[Fold],
    *,
    candidates: Optional[dict[str, dict]] = None,
    select: Optional[Callable[[dict[str, PortfolioResult]], str]] = None,
    run_fn: Callable[..., PortfolioResult] = run_portfolio,
    risk_pct: float = 0.005,
    initial_equity: float = 100_000.0,
    **run_kwargs,
) -> WalkForwardResult:
    """Run a portfolio backtest per fold and aggregate the *test* spans.

    ``make_strategy`` is a factory taking optional ``params`` (so a fold can inject tuned params);
    called with no args it must yield the fixed full-setup strategy. With ``candidates`` + ``select``
    supplied, each fold runs every candidate on its *train* span, ``select`` picks a key from the
    train results, and only that param set is run on the *test* span — never the reverse. With no
    selector (the Phase-E default) the train span is skipped entirely and the fixed setup is tested.

    ``run_fn`` is injectable so the WF logic is unit-testable without live data. Extra ``run_kwargs``
    (``provider``, ``crypto_provider``, ``references``, ``base_tf`` …) pass straight to ``run_fn``.
    """
    tuning = candidates is not None and select is not None
    fold_results: list[FoldResult] = []
    for fold in folds:
        train_res: Optional[PortfolioResult] = None
        chosen_params: dict = {}
        if tuning:
            trained = {
                name: run_fn(lambda p=params: make_strategy(p), universe,
                             fold.train_start, fold.train_end,
                             risk_pct=risk_pct, initial_equity=initial_equity, **run_kwargs)
                for name, params in candidates.items()
            }
            key = select(trained)
            chosen_params = candidates[key]
            train_res = trained[key]
        test_res = run_fn(lambda p=chosen_params: make_strategy(p), universe,
                          fold.test_start, fold.test_end,
                          risk_pct=risk_pct, initial_equity=initial_equity, **run_kwargs)
        fold_results.append(FoldResult(fold=fold, params=chosen_params, test=test_res,
                                       train=train_res))
    return WalkForwardResult(folds=fold_results, risk_pct=risk_pct, initial_equity=initial_equity)
