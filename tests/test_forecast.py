import pandas as pd
import pytest

from evolve import config
from evolve.backtest import run_backtest, select_models
from evolve.forecast import FORECAST_COLUMNS, render_section, run_forecast
from evolve.load import load_all, to_long


@pytest.fixture(scope="module")
def long():
    return to_long(load_all().frame)


@pytest.fixture(scope="module")
def fc(long):
    selection = select_models(run_backtest(long).results)
    return selection, *run_forecast(long, selection)


def test_schema_and_years(fc):
    _, out, _ = fc
    assert list(out.columns) == FORECAST_COLUMNS
    assert sorted(out["year"].unique()) == list(config.FORECAST_YEARS)
    assert out["forecast"].notna().all() and (out["forecast"] >= 0).all()


def test_selected_model_and_baselines_present(fc):
    selection, out, _ = fc
    for cat in config.TARGET_CATEGORIES:
        sub = out[out["category"] == cat]
        assert set(sub.loc[sub["selected"], "model"]) == {selection[(cat, "state")]}
        assert {"naive", "growth30"} <= set(sub["model"])
        assert sub.loc[sub["selected"], "state"].nunique() == 36
        assert not sub["low_volume"].any()


def test_low_volume_rows(fc):
    selection, out, _ = fc
    for cat in config.LOW_VOLUME_CATEGORIES:
        sub = out[out["category"] == cat]
        assert sub["low_volume"].all()
        assert set(sub.loc[sub["state"] != config.NATIONAL_LABEL, "model"]) == {"naive", "growth30"}
        nat = sub[sub["state"] == config.NATIONAL_LABEL]
        assert set(nat["model"]) == {"national_trend", "naive", "growth30"}
        assert set(nat.loc[nat["selected"], "model"]) == {selection[(cat, "national")]}


def test_baseline_arithmetic(fc, long):
    _, out, _ = fc
    last = long[(long["year"] == 2025) & (long["category"] == "car")].set_index("state")["count"]
    g = out[(out["category"] == "car") & (out["model"] == "growth30")].set_index(["state", "year"])["forecast"]
    n = out[(out["category"] == "car") & (out["model"] == "naive")].set_index(["state", "year"])["forecast"]
    assert g[("Kerala", 2027)] == pytest.approx(last["Kerala"] * 1.3 ** 2)
    assert n[("Kerala", 2030)] == pytest.approx(last["Kerala"])


def test_refuses_overlapping_years(long):
    with pytest.raises(ValueError):
        run_forecast(long, {}, years=[2025, 2026])


def test_render_section(fc):
    _, out, notes = fc
    text = render_section(out, notes)
    assert "## Forecast run" in text and "2030" in text
