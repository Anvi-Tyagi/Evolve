import pandas as pd
import pytest

from evolve import config
from evolve.load import LoadResult, load_all, load_year, to_long
from evolve.validate import ERROR, has_errors, render_report, validate_all, validate_year


@pytest.fixture(scope="module")
def real():
    return load_all()


@pytest.fixture
def y2020():
    return load_year(config.DATA_DIR / "ev_2020.csv", file_year=2020)


def checks(issues, level=None):
    return {i.check for i in issues if level is None or i.level == level}


def test_real_data_has_no_errors(real):
    issues = validate_all(real)
    assert not has_errors(issues), [i for i in issues if i.level == ERROR]


def test_real_data_known_gaps_reported(real):
    issues = validate_all(real)
    found = {(i.check, i.year, i.state) for i in issues}
    for y in (2020, 2021, 2022, 2023):
        assert ("zero_filled", y, "Sikkim") in found
    assert ("zero_filled", 2020, "Ladakh") in found
    assert ("missing_from_bov", 2025, "Ladakh") in found
    assert ("missing_from_pure", 2025, "Telangana") in found


def test_national_totals_match(real):
    for year, g in real.frame.groupby("file_year"):
        assert int(g["total"].sum()) == config.EXPECTED_NATIONAL_TOTALS[year]


def test_negative(y2020):
    y2020.loc[1, ["car", "total", "bov_total"]] -= 1000
    assert "negative" in checks(validate_year(y2020, 2020), ERROR)


def test_missing_state(y2020):
    df = y2020[y2020["state"] != "Goa"]
    issues = validate_year(df, 2020)
    assert ("missing_state", "Goa") in {(i.check, i.state) for i in issues}
    assert "row_count" in checks(issues, ERROR)


def test_unknown_state(y2020):
    y2020.loc[0, "state"] = pd.NA
    y2020.loc[0, "state_raw"] = "Atlantis"
    issues = validate_year(y2020, 2020)
    assert {"unknown_state", "missing_state"} <= checks(issues, ERROR)


def test_duplicate_state(y2020):
    y2020.loc[0, "state"] = "Goa"
    assert "duplicate_state" in checks(validate_year(y2020, 2020), ERROR)


def test_total_vs_categories(y2020):
    y2020.loc[1, "car"] += 1
    assert "total_vs_categories" in checks(validate_year(y2020, 2020), ERROR)


def test_total_vs_bov_pure(y2020):
    y2020.loc[1, "pure_total"] += 1
    assert "total_vs_bov_pure" in checks(validate_year(y2020, 2020), ERROR)


def test_national_total_mismatch(y2020):
    assert "national_total" not in checks(validate_year(y2020, 2020, 126_027), ERROR)
    assert "national_total" in checks(validate_year(y2020, 2020, 126_028), ERROR)


def test_year_mismatch(y2020):
    y2020.loc[0, "year"] = 2019
    assert "year_mismatch" in checks(validate_year(y2020, 2020), ERROR)


def test_flag_inconsistent(y2020):
    y2020.loc[1, "in_bov_export"] = False
    assert "flag_inconsistent" in checks(validate_year(y2020, 2020), ERROR)


def test_missing_file_is_error(tmp_path):
    issues = validate_all(LoadResult(frame=pd.DataFrame(), missing_files=[tmp_path / "ev_2020.csv"]))
    assert checks(issues, ERROR) == {"missing_file"}


def test_report_lists_everything(real):
    issues = validate_all(real)
    report = render_report(issues, real.frame, len(to_long(real.frame)))
    assert "**Status: PASSED**" in report
    assert "Sikkim" in report and "Ladakh" in report
    assert "2,356,901" in report
    assert "LMV + LPV + 4WIC" in report


def test_report_collapses_missing_from_pure(real):
    issues = validate_all(real)
    report = render_report(issues, real.frame, len(to_long(real.frame)))
    assert "| missing_from_pure |" not in report  # no per-row listing
    section = report.split("## Missing from Pure EV export")[1].split("## ")[0]
    expected = {2020: 32, 2021: 35, 2022: 33, 2023: 29, 2024: 3, 2025: 1}
    for year, n in expected.items():
        assert f"| {year} | {n} |" in section
    # missing_from_bov and zero_filled stay listed per row.
    assert "| 2025 | Ladakh | missing_from_bov |" in report
    assert "| 2020 | Sikkim | zero_filled |" in report
