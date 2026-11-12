"""Project configuration: paths, category columns and sanity-check figures.

Everything here that is an assumption rather than a verified fact is marked as such.
"""
from pathlib import Path

# Repository root (src/evolve/config.py -> parents[2]); keeps all paths relative to the repo.
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "EV_data" / "New"
OUTPUT_DIR = REPO_ROOT / "outputs"
# Directory the pipeline must never write into.
PROTECTED_DIR = REPO_ROOT / "EV_data"

YEARS = tuple(range(2020, 2026))  # 2020-2025 inclusive; 2025 is a full calendar year.
FILE_PATTERN = "ev_{year}.csv"

# The five vehicle-category columns in each CSV. Their sum must equal `total`.
CATEGORY_COLUMNS = ("two_wheeler", "three_wheeler", "car", "bus", "goods_other")

# ASSUMPTION (unverified): which VAHAN vehicle classes were grouped into each category
# when the CSVs were exported. This is the author's grouping; it has not been checked
# against VAHAN's own legend of vehicle-class codes.
_UNVERIFIED = "author's assumption, not verified against VAHAN's legend"
CATEGORY_GROUPING_ASSUMPTION = {
    "two_wheeler": f"2WIC + 2WN + 2WT ({_UNVERIFIED})",
    "three_wheeler": f"3WIC + 3WN + 3WT ({_UNVERIFIED})",
    "car": f"LMV + LPV + 4WIC ({_UNVERIFIED})",
    "bus": f"HPV + MPV + MMV + HMV ({_UNVERIFIED})",
    "goods_other": f"HGV + LGV + MGV + OTH ({_UNVERIFIED})",
}

NUMERIC_COLUMNS = CATEGORY_COLUMNS + ("total", "bov_total", "pure_total")
FLAG_COLUMNS = ("in_bov_export", "in_pure_export")
REQUIRED_COLUMNS = ("state", "year") + NUMERIC_COLUMNS + FLAG_COLUMNS

EXPECTED_STATE_COUNT = 36

# National sums of VAHAN EV registrations (fuel ELECTRIC(BOV) + PURE EV), computed from
# these same CSVs. This check guards against accidental edits to the files or the code,
# not against an export that was wrong in the first place (see README, External cross-checks).
EXPECTED_NATIONAL_TOTALS = {
    2020: 126_027,
    2021: 341_233,
    2022: 1_059_534,
    2023: 1_582_828,
    2024: 2_026_397,
    2025: 2_356_901,
}

# ---------------------------------------------------------------------------
# Phase 2: forecasting. All of these are fixed before any backtest is run.
# ---------------------------------------------------------------------------
# Categories modelled per state; the other two are low-volume and get only baselines
# at state level plus a national-level trend.
TARGET_CATEGORIES = ("two_wheeler", "three_wheeler", "car")
LOW_VOLUME_CATEGORIES = ("bus", "goods_other")

# Expanding-window backtest: (first training year, last training year, test year).
BACKTEST_FOLDS = ((2020, 2023, 2024), (2020, 2024, 2025))
FORECAST_YEARS = tuple(range(2026, 2031))

# MAPE is computed only on state-category rows whose actual is at least this value.
MAPE_MIN_ACTUAL = 100

# The legacy notebook's fixed growth rate, kept as a baseline.
BASELINE_GROWTH = 0.30

# Candidate shrinkage strengths (lambda). 0 = each state's own slope; inf = pooled slope.
SHRINKAGE_GRID = (0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, float("inf"))
# Inner one-step-ahead folds need at least this many earlier years to fit on.
SHRINKAGE_MIN_INNER_TRAIN_YEARS = 3

# Label used for national-level rows in forecast outputs.
NATIONAL_LABEL = "All India"
