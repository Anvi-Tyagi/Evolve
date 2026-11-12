import pandas as pd
import pytest

from evolve import config
from evolve.load import SchemaError, load_all, load_year, to_long
from evolve.states import CANONICAL_STATES


@pytest.fixture(scope="module")
def real():
    return load_all()


def test_all_files_present(real):
    assert real.missing_files == []
    assert len(real.frame) == 36 * len(config.YEARS)


def test_states_normalised(real):
    assert real.frame["state"].notna().all()
    for _, g in real.frame.groupby("year"):
        assert sorted(g["state"]) == sorted(CANONICAL_STATES)


def test_raw_name_kept(real):
    row = real.frame[real.frame["state"] == "Dadra and Nagar Haveli and Daman and Diu"].iloc[0]
    assert row["state_raw"] == "UT OF DNH AND DD"


def test_flags_are_boolean(real):
    for col in config.FLAG_COLUMNS:
        assert str(real.frame[col].dtype) == "boolean"


def test_long_format(real):
    long = to_long(real.frame)
    assert list(long.columns) == ["state", "year", "category", "count"]
    assert len(long) == 36 * len(config.YEARS) * len(config.CATEGORY_COLUMNS)
    assert set(long["category"]) == set(config.CATEGORY_COLUMNS)
    by_year = long.groupby("year")["count"].sum().to_dict()
    assert by_year == config.EXPECTED_NATIONAL_TOTALS


def test_missing_file_reported(tmp_path):
    result = load_all(tmp_path, years=(2020,))
    assert result.missing_files == [tmp_path / "ev_2020.csv"]
    assert result.frame.empty


def test_missing_column_raises(tmp_path):
    p = tmp_path / "ev_2020.csv"
    pd.DataFrame({"state": ["Goa"], "year": [2020]}).to_csv(p, index=False)
    with pytest.raises(SchemaError):
        load_year(p)


def test_unknown_state_kept_as_na(tmp_path):
    src = config.DATA_DIR / "ev_2020.csv"
    df = pd.read_csv(src)
    df.loc[0, "state"] = "Atlantis"
    p = tmp_path / "ev_2020.csv"
    df.to_csv(p, index=False)
    out = load_year(p, file_year=2020)
    assert out["state"].isna().sum() == 1
    assert out.loc[out["state"].isna(), "state_raw"].item() == "Atlantis"
    assert len(to_long(out)) == 35 * len(config.CATEGORY_COLUMNS)
