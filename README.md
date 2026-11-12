# EVolve

EVolve loads state-wise electric-vehicle (EV) registration data for India from VAHAN exports (2020–2025), maps state names onto one canonical list, checks the data, and writes a tidy dataset plus a validation report. With `--forecast`, it also backtests simple statistical growth models against two naive baselines and writes base forecasts of annual registrations for 2026–2030.

The forecasting is statistical growth modelling (curve fitting), not machine learning. There is no charger-demand code, no scenarios beyond a single base case, and no uncertainty bands yet. The original Colab notebook (`EVolve`) and the raw data in `EV_data/` are kept unchanged as the legacy version.

## Quick start

Requires Python 3.9+. Works on Windows, macOS and Linux. All paths are relative to the repository root.

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate    Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py               # load + validate; writes outputs/
python run.py --forecast    # also backtest and forecast 2026-2030
pytest                      # runs the test suite
```

`run.py` exits with code 1 if any validation error is found, and 0 otherwise. With `--forecast`, it refuses to forecast if validation fails. Options: `--data-dir DIR` (default `EV_data/New`) and `--out-dir DIR` (default `outputs`). It refuses to write anywhere inside `EV_data/`. All code is deterministic: it uses no randomness, so two runs produce byte-identical outputs.

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

- `ev_registrations_long.csv`: tidy long format with columns `state, year, category, count, zero_filled`. It has 36 states × 6 years × 5 categories = 1,080 rows. `state` uses the canonical names in `src/evolve/states.py`. `zero_filled` is `True` when the state was absent from both the BOV and Pure EV exports that year, so its counts are zeros by construction rather than observed zeros. In the current data that applies to Sikkim 2020–2023 and Ladakh 2020. Rows absent from only one export are `False`.
- `validation_report.md`: a per-year summary (state count, national total against the expected figure, BOV/Pure EV split) It lists every error, dropped row, missing file or state, zero-filled row, and row missing from the BOV export. States missing only from the Pure EV export are shown as one count per year. The report ends with the category-grouping assumption.

Written only with `--forecast`:

- `backtest_results.csv`: one row per fold, category, level (`state` or `national`) and model. Columns: `fold, train_start, train_end, test_year, category, level, model, n_rows, wape, mape, mape_rows, national_pct_error`.
- `backtest_report.md`: the side-by-side results, the selected model per category with a plain statement of whether the fitted models beat the baselines, the shrinkage strength chosen in each fold, excluded rows, the national growth note and a summary of the forecast run.
- `forecast_registrations.csv`: `state, category, year, forecast, model, selected, low_volume` for 2026–2030. For every category it contains the selected model and both baselines. `selected` marks the model chosen by the backtest, and `low_volume` marks bus and goods_other. Low-volume categories also have national rows with `state = "All India"`.

## Code layout

| Path | What it does |
|---|---|
| `src/evolve/config.py` | Paths, years, column names, the assumed category grouping, and the expected national totals used as sanity checks |
| `src/evolve/states.py` | `CANONICAL_STATES` (28 states + 8 UTs) and `normalise(name)`. Matching ignores case, `&`/`and` and punctuation, and handles known variants (e.g. "NCT of Delhi", "UT OF DNH AND DD", "Andaman & Nicobar Island", "Orissa", "Pondicherry"). Unknown names raise `UnknownStateError`; nothing is guessed |
| `src/evolve/load.py` | `load_year`, `load_all` (missing files are reported, not skipped) and `to_long`. The original state spelling is kept in `state_raw` |
| `src/evolve/validate.py` | Per-year checks: 36 states, no duplicates, no unknown states, year column matches the file, numeric and non-negative values, `total` = sum of categories = `bov_total + pure_total`, export flags consistent with counts, and national total matches config. `render_report` builds the markdown report |
| `src/evolve/models.py` | Growth models (pooled, shrinkage), baselines (naive, growth30) and the WAPE/MAPE metrics |
| `src/evolve/backtest.py` | Expanding-window backtest, the selection rule and the backtest report |
| `src/evolve/forecast.py` | Refits the selected model per category on 2020–2025 and forecasts 2026–2030 |
| `src/evolve/report.py` | Markdown table helper shared by the reports |
| `run.py` | Entry point: load → validate → write outputs; with `--forecast`, backtest → forecast |
| `tests/` | pytest tests for states, loading, validation, models, backtest, forecast and the end-to-end run |

The two former UTs "Dadra and Nagar Haveli" and "Daman and Diu" (merged in January 2020) both normalise to the merged UT. A dataset that lists them separately will produce two rows for it, which the validator flags as a duplicate and the caller must aggregate.

### Sanity-check totals

`config.EXPECTED_NATIONAL_TOTALS` holds the national sum for each year (ELECTRIC(BOV) + PURE EV). These figures are sums of these same CSVs, so the check guards against accidental edits to the files or the code. It does not guard against an export that was wrong in the first place; for that, see the external cross-checks below.

| 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|
| 126,027 | 341,233 | 1,059,534 | 1,582,828 | 2,026,397 | 2,356,901 |

## External cross-checks

These are approximate comparisons with published figures. They are not automated tests. Published figures vary by source, by date of extraction and by how vehicle categories are defined, so small differences are expected.

| Measure | This data | Published | Source |
|---|---|---|---|
| 2024 electric cars | 105,598 | 106,122 | [EVreporter, India electric car sales report CY 2024](https://evreporter.com/india-electric-car-sales-report-cy-2024-excerpts/) |
| 2024 electric two-wheelers | 1,214,778 | 1,204,926 | [JMK Research, EV ARC CY2024](https://jmkresearch.com/wp-content/uploads/2025/01/EV-ARC-CY2024-1.pdf) |
| 2025 all EVs | 2,356,901 | about 2.3 million | [Free Press Journal, citing Vahan](https://www.freepressjournal.in/amp/business/indias-ev-sales-touch-23-million-in-2025-as-market-share-rises-to-8-per-cent) |

## Methodology (forecasting)

All settings below are in `src/evolve/config.py` and were fixed before any backtest was run.

**Data.** The input is the tidy long table: annual new EV registrations per state and category, BOV and Pure EV summed. Rows flagged `zero_filled` are not observations. They are excluded from model fitting and from every error metric.

**Targets.** Two-wheelers, three-wheelers and cars are modelled per state. Bus and goods_other are flagged low volume. At state level they get only the two baselines, and at national level a log-linear trend fitted to the national total series is compared against the same baselines.

**Models.** Each category is fitted separately on y = log1p(count) against the calendar year:

- **pooled**: y = a_s + b·year. Each state has its own intercept a_s, and all states share one slope b, estimated by within-state least squares.
- **shrinkage**: each state's own least-squares slope b_s is pulled toward the shared slope: b̂_s = w_s·b_s + (1 − w_s)·b, with w_s = Sxx_s / (Sxx_s + λ). Sxx_s is the sum of squared year deviations for that state, so a state with more years of data keeps more of its own slope. A state with one year of data uses the shared slope. λ is chosen from a fixed grid (0 to ∞) using only the training years: every training year with at least three earlier years is predicted one step ahead from those earlier years, and the λ with the lowest mean WAPE is kept. Ties go to the larger λ. λ = ∞ is the same as pooled.
- **naive** baseline: same as the last observed year.
- **growth30** baseline: the last observed year grown 30% a year, the legacy notebook's rule.
- A **logistic S-curve is not included**. It needs a saturation ceiling, none has been supplied as an explicit assumption, and six annual points cannot identify one.

**Backtest.** The backtest uses an expanding window. Fold 1 trains on 2020–2023 and predicts 2024; fold 2 trains on 2020–2024 and predicts 2025. Models only ever see years before the test year: the code checks this, and a test confirms that corrupting data for the test year and later leaves the predictions unchanged. A state with no observed training years can't be forecast by any model; it is excluded from every model's score for that fold, and the report lists it. In the current data that is Sikkim in fold 1.

**Metrics** (per category and fold):

- WAPE = Σ|forecast − actual| / Σ actual. This is the headline metric.
- MAPE, computed only on rows with actual ≥ 100. The number of rows used is reported.
- National % error = (Σ forecast − Σ actual) / Σ actual.

**Selection rule.** For each category, the candidate with the lowest mean WAPE across the two folds is used for the forecast, even if it is a baseline. For state-level target categories the candidates are pooled, shrinkage, naive and growth30. For low-volume categories they are the two baselines at state level, and national_trend plus the baselines at national level.

**Forecast.** The selected model is refitted on all observed years (2020–2025) and projected for 2026–2030. Both baselines are always written alongside it. There are no uncertainty bands.

### Backtest results (from `python run.py --forecast` on the current data)

These figures are mean WAPE across the two folds, copied from `outputs/backtest_report.md`. The report has the full tables.

| Category (state level) | pooled | shrinkage | naive | growth30 | Selected |
|---|---|---|---|---|---|
| two_wheeler | 252.9% | 252.9% | 20.9% | 19.8% | growth30 |
| three_wheeler | 106.8% | 108.1% | 17.2% | 21.5% | naive |
| car | 113.3% | 113.5% | 33.7% | 25.6% | growth30 |

**The fitted log-linear models did not beat either baseline in any category or fold.** A single log-linear trend over 2020–2023 or 2020–2024 is dominated by the 2020–2022 take-off. National registrations grew 170.8% in 2021 and 210.5% in 2022, but only 28.0% in 2024 and 16.3% in 2025. Carried forward, that trend predicts far too much. For example, fitted on 2020–2023, the pooled two-wheeler slope implies 213.8% annual growth and overshoots 2024 nationally by 220.6%. Implied growth for every fold and category is in the report.

Because of the slowdown, the fixed 30% rule is already above observed national growth in both test years. It still has the lowest mean WAPE for two-wheelers (19.8% vs 20.9% for naive, although naive was better in the 2025 fold: 12.8% vs 19.9%) and for cars (25.6% vs 33.7%). Two folds are very little evidence for that choice. Forecasts that grow 30% a year to 2030 should be read as the legacy assumption carried forward, not as a validated projection.

For bus (state and national) and goods_other (state), growth30 was selected. For goods_other at national level, national_trend was selected (mean WAPE 20.5% vs 34.7% for growth30).

## Limitations

- **Telangana appears only in the BOV figures.** It is absent from the Pure EV export in every year, so any Pure EV registrations there are not captured.
- **Ladakh has no 2025 row in the BOV export.** Its 2025 figure (3 registrations) comes only from the Pure EV export. Ladakh is also absent from both exports in 2020, so its 2020 row is zero-filled.
- **Sikkim is absent from both exports in 2020–2023.** Those rows are zero-filled, not observed zeros.
- **Pure EV is almost unused before 2024.** It has 28, 0, 6 and 15 registrations nationally in 2020–2023, then 493,268 in 2024 and 1,565,794 in 2025. Using BOV alone would badly undercount 2024–25, which is why both are summed.
- **Registrations are a proxy for fleet size.** They count new registrations per year, not vehicles on the road. Scrappage, re-registration and inter-state transfers are not accounted for.
- **Very little history for forecasting.** There are only six annual points per state (2020–2025), and fewer where rows are zero-filled.
- **Only two backtest folds.** Model selection rests on two test years (2024 and 2025), so the ranking could easily change with more data.
- **Small states are noisy.** States with very few registrations swing by large percentages from year to year. They count little towards WAPE, which weights by volume, but their own forecasts are unreliable.
- **The 2024 fuel-label change.** VAHAN's shift from ELECTRIC(BOV) to PURE EV is handled by summing both labels. Any registrations recorded under neither label are not captured.
- **No 2026 actuals.** None of the 2026–2030 forecasts can be checked against real data yet.
- **No charger data yet.** Nothing here measures charging infrastructure.
- **The category grouping is an assumption.** The grouping of VAHAN vehicle classes into the five categories is the author's own and has not been checked against VAHAN's legend. It is recorded in `src/evolve/config.py` (`CATEGORY_GROUPING_ASSUMPTION`) and repeated in the validation report:

  | Category | VAHAN classes (assumed) |
  |---|---|
  | `two_wheeler` | 2WIC + 2WN + 2WT |
  | `three_wheeler` | 3WIC + 3WN + 3WT |
  | `car` | LMV + LPV + 4WIC |
  | `bus` | HPV + MPV + MMV + HMV |
  | `goods_other` | HGV + LGV + MGV + OTH |
