import math

import numpy as np
import pandas as pd
import pytest

from evolve.models import (FixedGrowth, Naive, Pooled, Shrinkage, ShrinkageCV, mape,
                           shrink_weights, training_rows, wape)


def synthetic(rates, levels, years=range(2020, 2026)):
    """count + 1 = level * (1 + rate)^(year - 2020), exactly log-linear on log1p scale."""
    rows = []
    for state, (r, lvl) in enumerate(zip(rates, levels)):
        for y in years:
            rows.append({"state": f"S{state}", "year": y,
                         "count": lvl * (1 + r) ** (y - 2020) - 1, "zero_filled": False})
    return pd.DataFrame(rows)


def test_pooled_recovers_known_growth():
    df = synthetic([0.25] * 4, [10, 500, 2_000, 80_000])
    m = Pooled().fit(df)
    assert m.growth_rate() == pytest.approx(0.25, abs=1e-9)
    pred = m.predict(["S1"], [2027])["forecast"].item()
    assert pred == pytest.approx(500 * 1.25 ** 7 - 1, rel=1e-9)


@pytest.mark.parametrize("lam", [0.0, 1.0, 50.0, float("inf")])
def test_shrinkage_recovers_known_growth_when_states_agree(lam):
    df = synthetic([0.25] * 3, [10, 1_000, 50_000])
    m = Shrinkage(lam).fit(df)
    for s in ("S0", "S1", "S2"):
        assert m.growth_rate(s) == pytest.approx(0.25, abs=1e-9)


def test_shrinkage_extremes():
    df = synthetic([0.10, 0.50], [100, 100])
    own = Shrinkage(0.0).fit(df)
    assert own.growth_rate("S0") == pytest.approx(0.10, abs=1e-9)
    assert own.growth_rate("S1") == pytest.approx(0.50, abs=1e-9)
    pooled = Pooled().fit(df)
    full = Shrinkage(float("inf")).fit(df)
    for s in ("S0", "S1"):
        assert full.slope_[s] == pytest.approx(pooled.slope_[s])
    mid = Shrinkage(17.5).fit(df)  # Sxx = 17.5 for six years -> w = 0.5
    assert mid.weights_["S0"] == pytest.approx(0.5)
    assert mid.slope_["S0"] == pytest.approx((math.log(1.1) + pooled.pooled_slope_) / 2)


def test_more_data_less_shrinkage():
    sxx = pd.Series({"short": 2.0, "long": 17.5})
    w = shrink_weights(sxx, 5.0)
    assert w["long"] > w["short"]


def test_single_point_state_uses_pooled_slope():
    df = pd.concat([synthetic([0.3, 0.3], [100, 1000]),
                    pd.DataFrame([{"state": "ONE", "year": 2025, "count": 50.0, "zero_filled": False}])])
    for m in (Shrinkage(0.0).fit(df), Shrinkage(5.0).fit(df), Pooled().fit(df)):
        assert m.growth_rate("ONE") == pytest.approx(0.3, abs=1e-9)
        assert m.predict(["ONE"], [2025])["forecast"].item() == pytest.approx(50.0)


def test_baselines():
    df = pd.DataFrame({"state": ["A", "A"], "year": [2023, 2024], "count": [80.0, 100.0]})
    assert Naive().fit(df).predict(["A"], [2025, 2027])["forecast"].tolist() == [100.0, 100.0]
    g = FixedGrowth(0.30).fit(df).predict(["A"], [2025, 2026])["forecast"].tolist()
    assert g == pytest.approx([130.0, 169.0])
    assert FixedGrowth(0.30).name == "growth30"


def test_unknown_state_predicts_nan():
    df = synthetic([0.2], [100])
    for m in (Naive().fit(df), Pooled().fit(df), Shrinkage(1).fit(df)):
        assert np.isnan(m.predict(["NOPE"], [2026])["forecast"].item())


def test_zero_filled_rows_not_used_for_training():
    df = synthetic([0.2], [100])
    junk = df.copy()
    junk.loc[junk["year"] <= 2022, "count"] = 0.0
    junk.loc[junk["year"] <= 2022, "zero_filled"] = True
    clean = df[df["year"] > 2022]
    for cls in (Naive, Pooled, lambda: Shrinkage(2.0), ShrinkageCV):
        a = cls().fit(junk).predict(["S0"], [2026])
        b = cls().fit(clean).predict(["S0"], [2026])
        pd.testing.assert_frame_equal(a, b)
    assert len(training_rows(junk)) == 3


def test_wape_and_mape():
    actual, pred = [100, 200, 50, 0], [110, 180, 75, 5]
    assert wape(actual, pred) == pytest.approx((10 + 20 + 25 + 5) / 350)
    m, n = mape(actual, pred, min_actual=100)
    assert n == 2
    assert m == pytest.approx((0.10 + 0.10) / 2)
    assert mape(actual, pred, min_actual=1_000) == (pytest.approx(float("nan"), nan_ok=True), 0)
    assert math.isnan(wape([0, 0], [1, 2]))


def test_shrinkage_cv_picks_lambda_from_training_only_and_is_deterministic():
    df = synthetic([0.1, 0.4, 0.25], [100, 5_000, 900])
    a, b = ShrinkageCV().fit(df), ShrinkageCV().fit(df)
    assert a.lam == b.lam
    assert a.inner_years_ == [2023, 2024, 2025]
    pd.testing.assert_frame_equal(a.predict(["S0", "S1"], [2027]), b.predict(["S0", "S1"], [2027]))
    # Per-state growth differs and is exact, so lam = 0 (own slopes) should win.
    assert a.lam == 0.0


def test_shrinkage_cv_no_inner_fold_falls_back_to_pooled():
    df = synthetic([0.1, 0.4], [100, 100], years=range(2020, 2023))
    m = ShrinkageCV().fit(df)
    assert m.inner_years_ == [] and math.isinf(m.lam)
