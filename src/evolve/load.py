"""Read the per-year VAHAN EV CSV exports and reshape them to tidy long format."""
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config
from .states import UnknownStateError, normalise


class SchemaError(ValueError):
    """Raised when a CSV is missing required columns."""


@dataclass
class LoadResult:
    frame: pd.DataFrame
    missing_files: list = field(default_factory=list)  # paths that did not exist


def _parse_flag(series: pd.Series) -> pd.Series:
    mapping = {"true": True, "false": False, "1": True, "0": False}
    return series.astype(str).str.strip().str.lower().map(mapping).astype("boolean")


def _safe_normalise(name):
    try:
        return normalise(name)
    except UnknownStateError:
        return pd.NA


def load_year(path, file_year=None) -> pd.DataFrame:
    """Load one year's CSV.

    Returns the wide frame with `state` replaced by the canonical name (NA if unknown),
    the original spelling kept in `state_raw`, and `file_year` taken from the argument.
    Values that are not numeric become NA so the validator can report them.
    """
    path = Path(path)
    df = pd.read_csv(path, dtype={"state": str})
    missing = [c for c in config.REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"{path.name}: missing required columns {missing}")

    df = df[list(config.REQUIRED_COLUMNS)].copy()
    df.insert(0, "state_raw", df["state"])
    df["state"] = df["state_raw"].map(_safe_normalise)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    for col in config.NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in config.FLAG_COLUMNS:
        df[col] = _parse_flag(df[col])
    df["file_year"] = file_year
    df["source_file"] = path.name
    return df


def load_all(data_dir=config.DATA_DIR, years=config.YEARS) -> LoadResult:
    """Load every year's CSV from `data_dir`. Missing files are returned, not skipped silently."""
    data_dir = Path(data_dir)
    frames, missing = [], []
    for year in years:
        path = data_dir / config.FILE_PATTERN.format(year=year)
        if not path.exists():
            missing.append(path)
            continue
        frames.append(load_year(path, file_year=year))
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return LoadResult(frame=frame, missing_files=missing)


def to_long(wide: pd.DataFrame) -> pd.DataFrame:
    """Tidy long format: one row per (state, year, category) with its registration count.

    `zero_filled` is True when the state was absent from both the BOV and Pure EV exports
    that year, so its counts are zeros by construction rather than observed zeros.
    Rows whose state could not be normalised are excluded here; the validator reports them.
    """
    known = wide[wide["state"].notna()].copy()
    known["zero_filled"] = (
        ~known["in_bov_export"].fillna(True) & ~known["in_pure_export"].fillna(True)
    ).astype(bool)
    long = known.melt(
        id_vars=["state", "year", "zero_filled"],
        value_vars=list(config.CATEGORY_COLUMNS),
        var_name="category",
        value_name="count",
    )
    long = long[["state", "year", "category", "count", "zero_filled"]]
    return long.sort_values(["year", "state", "category"]).reset_index(drop=True)
