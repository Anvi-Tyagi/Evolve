# EVolve

EVolve loads state-wise electric-vehicle (EV) registration data for India from VAHAN exports (2020–2025), maps state names onto one canonical list, checks the data, and writes a tidy dataset plus a validation report.

This phase covers loading and validation only. There is no forecasting, modelling or charger-demand code yet. The original Colab notebook (`EVolve`) and the raw data in `EV_data/` are kept unchanged as the legacy version.

## Quick start

Requires Python 3.9+. Works on Windows, macOS and Linux. All paths are relative to the repository root.

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate    Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py      # writes outputs/
pytest             # runs the test suite
```

`run.py` exits with code 1 if any validation error is found, and 0 otherwise. Options: `--data-dir DIR` (default `EV_data/New`) and `--out-dir DIR` (default `outputs`). It refuses to write anywhere inside `EV_data/`.

## Input

`EV_data/New/ev_<year>.csv` for 2020–2025. There is one file per calendar year, with one row for each of the 36 states/UTs. 2025 is a full year; there is no 2026 data. `EV_data/Old/` holds superseded `.xlsx` exports and is not read.

| Column | Meaning |
|---|---|
| `state`, `year` | State/UT name as exported; calendar year |
| `two_wheeler`, `three_wheeler`, `car`, `bus`, `goods_other` | EV registrations by vehicle category |
| `total` | Sum of the five categories |
| `bov_total`, `pure_total` | Registrations with fuel type ELECTRIC(BOV) and PURE EV; `total = bov_total + pure_total` |
| `in_bov_export`, `in_pure_export` | Whether the state appeared in each VAHAN export. When it did not, its values are zero-filled |

Each count is BOV and Pure EV summed.

## Output (`outputs/`, not tracked by git)

- `ev_registrations_long.csv`: tidy long format with columns `state, year, category, count`. It has 36 states × 6 years × 5 categories = 1,080 rows. `state` uses the canonical names in `src/evolve/states.py`.
- `validation_report.md`: a per-year summary (state count, national total against the expected figure, BOV/Pure EV split) and every error, dropped row, missing file or state, zero-filled row and partially exported row, plus the category-grouping assumption.

## Code layout

| Path | What it does |
|---|---|
| `src/evolve/config.py` | Paths, years, column names, the assumed category grouping, and the expected national totals used as sanity checks |
| `src/evolve/states.py` | `CANONICAL_STATES` (28 states + 8 UTs) and `normalise(name)`. Matching ignores case, `&`/`and` and punctuation, and handles known variants (e.g. "NCT of Delhi", "UT OF DNH AND DD", "Andaman & Nicobar Island", "Orissa", "Pondicherry"). Unknown names raise `UnknownStateError`; nothing is guessed |
| `src/evolve/load.py` | `load_year`, `load_all` (missing files are reported, not skipped) and `to_long`. The original state spelling is kept in `state_raw` |
| `src/evolve/validate.py` | Per-year checks: 36 states, no duplicates, no unknown states, year column matches the file, numeric and non-negative values, `total` = sum of categories = `bov_total + pure_total`, export flags consistent with counts, and national total matches config. `render_report` builds the markdown report |
| `run.py` | Entry point: load → validate → write outputs |
| `tests/` | pytest tests for states, loading, validation and the end-to-end run |

The two former UTs "Dadra and Nagar Haveli" and "Daman and Diu" (merged in January 2020) both normalise to the merged UT. A dataset that lists them separately will produce two rows for it, which the validator flags as a duplicate and the caller must aggregate.

### Sanity-check totals

These are the national sums of VAHAN EV registrations (ELECTRIC(BOV) + PURE EV), supplied by the project owner. They live in `config.EXPECTED_NATIONAL_TOTALS`, and the current data matches all of them.

| 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| 126,027 | 341,233 | 1,059,534 | 1,582,828 | 2,026,397 | 2,356,901 |

## Limitations

- **Telangana appears only in the BOV figures.** It is absent from the Pure EV export in every year, so any Pure EV registrations there are not captured.
- **Ladakh has no 2025 row in the BOV export.** Its 2025 figure (3 registrations) comes only from the Pure EV export. Ladakh is also absent from both exports in 2020, so its 2020 row is zero-filled.
- **Sikkim is absent from both exports in 2020–2023.** Those rows are zero-filled, not observed zeros.
- **Pure EV is almost unused before 2024.** It has 28, 0, 6 and 15 registrations nationally in 2020–2023, then 493,268 in 2024 and 1,565,794 in 2025. Using BOV alone would badly undercount 2024–25, which is why both are summed.
- **Registrations are a proxy for fleet size.** They count new registrations per year, not vehicles on the road. Scrappage, re-registration and inter-state transfers are not accounted for.
- **No charger data yet.** Nothing here measures charging infrastructure.
- **The category grouping is an assumption.** How VAHAN vehicle classes were grouped into the five categories (e.g. car = LMV + LPV + 4WIC) has not been verified. It is recorded in `src/evolve/config.py` (`CATEGORY_GROUPING_ASSUMPTION`). Only the `car` grouping is documented there; the others are marked as undocumented.
