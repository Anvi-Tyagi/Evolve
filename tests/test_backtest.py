import numpy as np
import pandas as pd
import pytest

from evolve import config
from evolve.backtest import (national_growth, render_report, run_backtest, select_models,
                             split)
from evolve.load import load_all, to_long
from evolve.models import MODEL_NAMES, make_model


@pytest.fixture(scope="module")
def long():
    return to_long(load_all().frame)


@pytest.fixture(scope="module")
def bt(long):
    return run_backtest(long)


def test_split_refuses_overlapping_window(long):
    with pytest.raises(ValueError):
        split(long, 2020, 2024, 2024)


@pytest.mark.parametrize("start, end, test_year", config.BACKTEST_FOLDS)
@pytest.mark.parametrize("name", MODEL_NAMES)
def test_no_leakage(long, start, end, test_year, name):
    """Predictions for year T must not change when data for T and later is corrupted."""
    cat = long[long["category"] == "two_wheeler"]
    corrupted = cat.copy()
    future = corrupted["year"] >= test_year
    corrupted.loc[future, "count"] = corrupted.loc[future, "count"] * 1000 + 7

    train_a, test_a = split(cat, start, end, test_year)
    train_b, _ = split(corrupted, start, end, test_year)
    assert train_a["year"].max() < test_year
    pa = make_model(name).fit(train_a).predict(test_a["state"], [test_year])
    pb = make_model(name).fit(train_b).predict(test_a["state"], [test_year])
    pd.testing.assert_frame_equal(pa, pb)


def test_backtest_invariant_to_future_data(long):
    """Whole fold-1 backtest is unchanged if 2025 data is altered."""
    alt = long.copy()
    alt.loc[alt["year"] == 2025, "count"] = 1
    folds = config.BACKTEST_FOLDS[:1]
    a, b = run_backtest(long, folds), run_backtest(alt, folds)
    pd.testing.assert_frame_equal(a.results, b.results)
    assert a.lambdas == b.lambdas


def test_results_shape(bt):
    r = bt.results
    n_target = len(config.BACKTEST_FOLDS) * len(config.TARGET_CATEGORIES) * 4
    n_low_state = len(config.BACKTEST_FOLDS) * len(config.LOW_VOLUME_CATEGORIES) * 2
    n_low_nat = len(config.BACKTEST_FOLDS) * len(config.LOW_VOLUME_CATEGORIES) * 3
    assert len(r) == n_target + n_low_state + n_low_nat
    assert r["wape"].notna().all()


def test_sikkim_excluded_in_fold_1_only_and_identically(bt):
    ex = {(f, c, s) for f, c, s, _ in bt.excluded}
    for cat in config.TARGET_CATEGORIES + config.LOW_VOLUME_CATEGORIES:
        assert (1, cat, "Sikkim") in ex
    assert {f for f, *_ in bt.excluded} == {1}
    state = bt.results[bt.results["level"] == "state"]
    for (fold, cat), g in state.groupby(["fold", "category"]):
        assert g["n_rows"].nunique() == 1  # every model scored on the same rows
        assert g["n_rows"].iloc[0] == (35 if fold == 1 else 36)


def test_zero_filled_excluded_from_scoring():
    rows = []
    for s, zf_year in (("A", None), ("B", 2024)):
        for y in range(2020, 2025):
            zf = y == zf_year
            rows.append({"state": s, "year": y, "category": "car", "count": 0 if zf else 100 + y - 2020,
                         "zero_filled": zf})
    df = pd.DataFrame(rows)
    for cat in config.CATEGORY_COLUMNS:
        if cat != "car":
            df = pd.concat([df, df[df["category"] == "car"].assign(category=cat)])
    res = run_backtest(df, folds=((2020, 2023, 2024),)).results
    car = res[(res["category"] == "car") & (res["level"] == "state")]
    assert (car["n_rows"] == 1).all()  # B's zero-filled 2024 row is not scored


def test_selection_rule():
    res = pd.DataFrame({
        "category": ["car"] * 4 + ["car"] * 4, "level": "state",
        "model": ["pooled", "shrinkage", "naive", "growth30"] * 2,
        "wape": [0.10, 0.12, 0.20, 0.30, 0.30, 0.12, 0.10, 0.40],
    })
    # means: pooled .20, shrinkage .12, naive .15, growth30 .35
    assert select_models(res) == {("car", "state"): "shrinkage"}


def test_national_growth_matches_totals(long):
    g = national_growth(long).set_index("year")
    t = config.EXPECTED_NATIONAL_TOTALS
    assert g.loc[2024, "growth"] == pytest.approx(t[2024] / t[2023] - 1)
    assert g.loc[2025, "growth"] == pytest.approx(t[2025] / t[2024] - 1)


def test_report_sections(bt, long):
    report = render_report(bt, select_models(bt.results), long)
    for heading in ("Implied annual growth", "National growth slowdown", "### two_wheeler", "### bus (low volume",
                    "Shrinkage strength", "Rows excluded", "Logistic S-curve"):
        assert heading in report
    assert report.count("**Selected:") == 3 + 2 * 2
