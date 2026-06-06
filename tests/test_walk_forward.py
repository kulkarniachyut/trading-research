"""Phase E — walk-forward harness: folds never leak (test >= train), pooling counts only the
*test* spans, and per-symbol breadth / param-selection wiring behave. Uses an injected ``run_fn``
so the WF logic is exercised without live data.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.portfolio import PortfolioResult, UniverseItem
from src.core.types import Result, Trade
from src.validation.walk_forward import Fold, make_folds, walk_forward

NY = "America/New_York"


def _trade(net: float, exit_ts) -> Trade:
    return Trade(symbol="SPY", side="long", entry_ts=exit_ts, exit_ts=exit_ts,
                 entry_px=100.0, exit_px=100.0 + net, qty=1.0, gross_pnl=net, costs=0.0,
                 net_pnl=net, return_pct=net / 100.0, bars_held=1)


def _portfolio(year: int, nets_by_symbol: dict[str, list[float]], risk_pct, equity) -> PortfolioResult:
    start = pd.Timestamp(f"{year}-01-01", tz=NY)
    end = pd.Timestamp(f"{year}-12-31", tz=NY)
    results = {}
    for sym, nets in nets_by_symbol.items():
        trades = [_trade(n, start + pd.Timedelta(days=i)) for i, n in enumerate(nets)]
        results[sym] = Result(strategy="ict_2022", symbol=sym, params={}, trades=trades,
                              equity_curve=pd.Series(dtype=float))
    return PortfolioResult(results=results, start=start, end=end, initial_equity=equity,
                           risk_pct=risk_pct, errors={})


# --- folds: causality (no look-ahead) -------------------------------------------------


def test_make_folds_anchored_grows_train_and_tests_each_later_year_once():
    folds = make_folds([2021, 2022, 2023, 2024], scheme="anchored")
    assert [f.test_start.year for f in folds] == [2022, 2023, 2024]   # each later year once
    # anchored = growing window: every fold trains from 2021, train_end advances.
    assert all(f.train_start.year == 2021 for f in folds)
    assert [f.train_end.year for f in folds] == [2021, 2022, 2023]
    # the walk-forward invariant: test never precedes train.
    assert all(f.test_start >= f.train_end for f in folds)


def test_make_folds_rolling_uses_fixed_window():
    folds = make_folds([2021, 2022, 2023, 2024], scheme="rolling", train_size=1)
    assert [(f.train_start.year, f.test_start.year) for f in folds] == \
        [(2021, 2022), (2022, 2023), (2023, 2024)]


def test_fold_rejects_leaky_split():
    with pytest.raises(ValueError, match="leaks"):
        Fold(label="bad",
             train_start=pd.Timestamp("2022-01-01", tz=NY),
             train_end=pd.Timestamp("2023-12-31", tz=NY),
             test_start=pd.Timestamp("2022-06-01", tz=NY),   # test starts before train ends
             test_end=pd.Timestamp("2022-12-31", tz=NY))


def test_make_folds_needs_two_years():
    with pytest.raises(ValueError, match="walk forward"):
        make_folds([2023])


# --- walk_forward: pooling uses only the test spans -----------------------------------


def test_pooled_oos_counts_test_trades_only():
    # run_fn returns trades keyed by the span's start year.
    nets = {2022: {"SPY": [2.0, -1.0]}, 2023: {"SPY": [3.0], "QQQ": [-2.0]}}

    def fake_run(make_strategy, universe, start, end, *, risk_pct, initial_equity, **kw):
        make_strategy()  # exercise the factory like the real runner does
        return _portfolio(start.year, nets.get(start.year, {}), risk_pct, initial_equity)

    folds = make_folds([2021, 2022, 2023], scheme="anchored")
    wf = walk_forward(lambda p=None: object(), [UniverseItem("SPY")], folds,
                      run_fn=fake_run, risk_pct=0.005, initial_equity=100_000.0)

    # pooled = test years 2022 (2 trades) + 2023 (2 trades) = 4; train span 2021 never pooled.
    assert wf.trade_count == 4
    assert wf.total_net == pytest.approx(2.0 - 1.0 + 3.0 - 2.0)
    # expectancy R = net / (risk_pct * equity) per trade; here denom = 500.
    assert wf.expectancy_r == pytest.approx((2.0) / 4 / 500.0)
    # per-symbol breadth: SPY net +4 (positive), QQQ net -2 (negative) → half the symbols positive.
    assert wf.breadth_positive == pytest.approx(0.5)


def test_tuning_selects_on_train_and_tests_chosen_params():
    calls: list[tuple[int, str]] = []

    def fake_run(make_strategy, universe, start, end, *, risk_pct, initial_equity, **kw):
        strat = make_strategy()
        calls.append((start.year, strat["tag"]))
        # train year 2021 produces signal so the selector can choose; test years produce 1 trade.
        nets = {"SPY": [5.0]} if start.year >= 2022 else {"SPY": [1.0]}
        return _portfolio(start.year, nets, risk_pct, initial_equity)

    candidates = {"a": {"tag": "a"}, "b": {"tag": "b"}}
    # selector always picks 'b'; assert 'b' is what reaches the test span.
    folds = make_folds([2021, 2022], scheme="anchored")
    wf = walk_forward(lambda p: p, [UniverseItem("SPY")], folds,
                      candidates=candidates, select=lambda trained: "b",
                      run_fn=fake_run, risk_pct=0.005, initial_equity=100_000.0)

    assert wf.folds[0].params == {"tag": "b"}
    # both candidates ran on the 2021 train span; only the chosen 'b' ran on the 2022 test span.
    assert (2021, "a") in calls and (2021, "b") in calls
    assert (2022, "b") in calls and (2022, "a") not in calls
