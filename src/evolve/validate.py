"""Per-year validation checks and the markdown validation report.

Nothing is dropped silently: every row excluded from the tidy output, every missing
state or file, and every zero-filled or partially exported row is listed as an Issue.
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import config
from .states import CANONICAL_STATES

ERROR, WARNING, INFO = "error", "warning", "info"


@dataclass(frozen=True)
class Issue:
    level: str
    year: Optional[int]
    state: Optional[str]
    check: str
    detail: str


def _state_label(row) -> str:
    return row["state"] if pd.notna(row["state"]) else f"{row['state_raw']!r} (unrecognised)"


def validate_year(df: pd.DataFrame, year: int, expected_total=None) -> list:
    """Run all checks on one year's wide frame (as returned by load.load_year)."""
    issues = []

    def add(level, check, detail, state=None):
        issues.append(Issue(level, year, state, check, detail))

    # Unknown state names: these rows are dropped from the tidy output.
    for _, row in df[df["state"].isna()].iterrows():
        add(ERROR, "unknown_state",
            f"State name {row['state_raw']!r} is not recognised; row excluded from tidy output.")

    known = df[df["state"].notna()]
    dupes = known[known["state"].duplicated(keep=False)]
    for state, g in dupes.groupby("state"):
        add(ERROR, "duplicate_state",
            f"{len(g)} rows map to this state (raw names: {sorted(g['state_raw'])}).", state)

    present = set(known["state"])
    for state in sorted(set(CANONICAL_STATES) - present):
        add(ERROR, "missing_state", "No row for this state/UT.", state)
    if len(df) != config.EXPECTED_STATE_COUNT:
        add(ERROR, "row_count", f"{len(df)} rows; expected {config.EXPECTED_STATE_COUNT}.")

    if "year" in df:
        bad_year = df[df["year"].isna() | (df["year"] != year)]
        for _, row in bad_year.iterrows():
            add(ERROR, "year_mismatch",
                f"year column is {row['year']}, file is for {year}.", _state_label(row))

    for col in config.NUMERIC_COLUMNS:
        for _, row in df[df[col].isna()].iterrows():
            add(ERROR, "non_numeric", f"{col} is missing or not numeric.", _state_label(row))
        for _, row in df[df[col] < 0].iterrows():
            add(ERROR, "negative", f"{col} = {row[col]}.", _state_label(row))

    cat_sum = df[list(config.CATEGORY_COLUMNS)].sum(axis=1, min_count=len(config.CATEGORY_COLUMNS))
    for i in df.index[(cat_sum != df["total"]).fillna(False)]:
        row = df.loc[i]
        add(ERROR, "total_vs_categories",
            f"total = {row['total']} but categories sum to {cat_sum[i]}.", _state_label(row))
    bp = df["bov_total"] + df["pure_total"]
    for i in df.index[(bp != df["total"]).fillna(False)]:
        row = df.loc[i]
        add(ERROR, "total_vs_bov_pure",
            f"total = {row['total']} but bov_total + pure_total = {bp[i]}.", _state_label(row))

    # Export-presence flags.
    for _, row in df.iterrows():
        label = _state_label(row)
        in_bov, in_pure = row["in_bov_export"], row["in_pure_export"]
        if pd.isna(in_bov) or pd.isna(in_pure):
            add(ERROR, "bad_flag", "in_bov_export / in_pure_export not parseable as True/False.", label)
            continue
        if not in_bov and pd.notna(row["bov_total"]) and row["bov_total"] != 0:
            add(ERROR, "flag_inconsistent", f"Not in BOV export but bov_total = {row['bov_total']}.", label)
        if not in_pure and pd.notna(row["pure_total"]) and row["pure_total"] != 0:
            add(ERROR, "flag_inconsistent", f"Not in Pure EV export but pure_total = {row['pure_total']}.", label)
        if not in_bov and not in_pure:
            add(INFO, "zero_filled", "Absent from both BOV and Pure EV exports; all counts zero-filled.", label)
        elif not in_bov:
            add(INFO, "missing_from_bov", f"Absent from BOV export (zero-filled); Pure EV total = {row['pure_total']}.", label)
        elif not in_pure:
            add(INFO, "missing_from_pure", f"Absent from Pure EV export (zero-filled); BOV total = {row['bov_total']}.", label)

    national = int(df["total"].sum())
    if expected_total is None:
        add(WARNING, "national_total", f"No expected national total configured; observed {national:,}.")
    elif national != expected_total:
        add(ERROR, "national_total", f"Observed {national:,}; expected {expected_total:,} (diff {national - expected_total:+,}).")
    return issues


def validate_all(result) -> list:
    """Validate a load.LoadResult: missing files plus per-year checks."""
    issues = [Issue(ERROR, None, None, "missing_file", f"{p} not found; year not loaded.")
              for p in result.missing_files]
    if result.frame.empty:
        return issues
    for year, g in result.frame.groupby("file_year"):
        issues += validate_year(g, int(year), config.EXPECTED_NATIONAL_TOTALS.get(int(year)))
    return issues


def has_errors(issues) -> bool:
    return any(i.level == ERROR for i in issues)


def _table(rows, headers) -> str:
    if not rows:
        return "_None._\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def render_report(issues, wide: pd.DataFrame, long_rows: int) -> str:
    """Markdown report summarising every check, exclusion and zero-fill."""
    lines = ["# EV registrations validation report", ""]
    status = "FAILED" if has_errors(issues) else "PASSED"
    n_err = sum(i.level == ERROR for i in issues)
    lines += [f"**Status: {status}** ({n_err} error(s)). Tidy output rows written: {long_rows:,}.", ""]

    lines += ["## Per-year summary", ""]
    rows = []
    if not wide.empty:
        for year, g in wide.groupby("file_year"):
            exp = config.EXPECTED_NATIONAL_TOTALS.get(int(year))
            obs = int(g["total"].sum())
            year_err = sum(i.level == ERROR and i.year == year for i in issues)
            rows.append([int(year), g["state"].notna().sum(), f"{obs:,}",
                         f"{exp:,}" if exp is not None else "n/a",
                         f"{int(g['bov_total'].sum()):,}", f"{int(g['pure_total'].sum()):,}",
                         "OK" if year_err == 0 else f"{year_err} error(s)"])
    lines.append(_table(rows, ["Year", "States", "National total", "Expected", "BOV", "Pure EV", "Checks"]))

    def section(title, checks, note=""):
        sel = [i for i in issues if i.check in checks]
        lines.extend([f"## {title}", ""] + ([note, ""] if note else []))
        lines.append(_table([[i.year if i.year is not None else "-", i.state or "-", i.check, i.detail] for i in sel],
                            ["Year", "State", "Check", "Detail"]))

    section("Errors", {i.check for i in issues if i.level == ERROR})
    section("Dropped rows", {"unknown_state"},
            "Rows excluded from the tidy output (unrecognised state names).")
    section("Missing files and states", {"missing_file", "missing_state"})
    section("Zero-filled rows", {"zero_filled"},
            "State/UT absent from both exports for that year; counts are zero by construction, not observed zeros.")
    section("Partially exported rows", {"missing_from_bov", "missing_from_pure"},
            "State/UT absent from one export; that export's contribution is zero-filled.")
    section("Warnings", {i.check for i in issues if i.level == WARNING})

    lines += ["## Category grouping (assumption)", "",
              "The mapping of VAHAN vehicle classes to categories is unverified:", ""]
    lines += [f"- `{k}`: {v}" for k, v in config.CATEGORY_GROUPING_ASSUMPTION.items()]
    lines.append("")
    return "\n".join(lines)
