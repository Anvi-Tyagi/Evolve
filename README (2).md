# EVolve: EV Charging Infrastructure Requirement Estimation

A data-driven project that estimates state-wise electric-vehicle (EV) charging infrastructure requirements in India for future years (2026, 2028, 2030), based on state-level EV registration data and a throughput-based charger-demand calculation.

> **Note on scope vs. original plan:** This project was originally scoped to analyze EV registrations from **2020 to June 2025**. The dataset actually loaded and processed in the current notebook (`EVolve.ipynb`) is a **single-year (2024) state-wise vehicle snapshot**, not a multi-year time series. All descriptions below reflect what the code actually does with this single-year dataset. This is called out explicitly wherever it affects the methodology (see [Limitations](#limitations)).

---

## Introduction

India's electric vehicle (EV) adoption has grown rapidly across vehicle segments, driven by supportive government policy, falling EV costs, rising consumer interest, and expanding charging infrastructure. The government's **EV30@30** initiative is a key policy driver, aiming to accelerate the share of electric vehicles on Indian roads while encouraging parallel investment in charging infrastructure.

Key benefits associated with EV adoption include:

- Lower running and operating costs compared to internal combustion vehicles
- Reduced dependence on imported petrol and diesel
- Zero tailpipe emissions for battery-electric vehicles
- Potential reduction in overall carbon emissions
- State-level tax, registration, and purchase incentives

As EV numbers grow, the charging network needs to expand in step — both to avoid congestion at existing stations and to avoid over-building infrastructure that goes unused.

---

## Problem Statement

As EV ownership rises, charging infrastructure must scale accordingly. Under-provisioning leads to:

- Charging congestion and longer wait times
- Uneven infrastructure availability across states
- Reduced convenience and slower EV adoption

Over-provisioning, on the other hand, risks underutilized assets and inefficient capital investment.

**This project addresses:** given recent state-level EV registration figures, how many public chargers (fast and slow) may be needed by future target years (2026 / 2028 / 2030) to support a projected EV population, under an assumed growth rate and charging-behavior model?

This is a **data-driven planning and estimation exercise** based on simplifying assumptions — not a claim of the exact, optimal number of chargers required.

---

## Objectives

Based on what the notebook actually implements:

- Parse and clean a state-wise EV/vehicle registration snapshot obtained from a VAHAN-style report export.
- Normalize inconsistent state names and aggregate registration totals per state.
- Project future EV counts per state (2026, 2028, 2030) using a compound annual growth rate (CAGR) assumption.
- Estimate public charging demand (energy, sessions, and charger counts — split into fast and slow chargers) for each state and target year using a throughput-based model.
- Export projected EV counts and charger requirements as CSV files for further analysis.

**Not currently implemented** (despite being part of the original brief): multi-year trend analysis, machine-learning-based forecasting, exploratory visualizations, and comparison against current installed charging infrastructure. These are listed under [Future Scope](#future-scope).

---

## Literature / Context

For background, independent of this project's own calculations:

- As of August 1, 2025, India had approximately **29,277 operational public charging stations** (per government/press data).
- States such as Karnataka, Maharashtra, Uttar Pradesh, Delhi, Tamil Nadu, Rajasthan, Kerala, Gujarat, Madhya Pradesh, and Telangana host a substantial share of existing charging infrastructure, though distribution across India is uneven.
- Government guidelines have referenced charging stations roughly every 25 km on highways, and fast chargers roughly every 100 km for heavy vehicles, alongside grid-based planning norms for urban charging.
- The IEA and independent media reporting (e.g., coverage citing a requirement of around 39 lakh chargers by 2030) provide external, higher-level projections for India's future charging needs.

**These figures are external context only.** They are not inputs to, or outputs of, this project's code — the notebook does not fetch, parse, or reference these sources programmatically. Any charger-requirement numbers reported by this project come solely from the throughput calculation described in [Methodology](#methodology), using the assumptions documented there.

---

## Data Sources

### Primary Vehicle/EV Data (used in code)

- **Source (per project context):** VAHAN Parivahan dashboard — https://vahan.parivahan.gov.in/vahan4dashboard/vahan/view/reportview.xhtml
- **File actually loaded in the notebook:** a manually uploaded file named `reportTable.xlsx - reportTable.csv`, uploaded via Google Colab's file-upload widget at runtime (no dataset is bundled with the notebook itself).
- **Contents of the file, as parsed by the code:** a single table titled *"State Wise Vehicle Category Data For All State (2024)"*, with columns for state name, vehicle category totals broken out as `LMV` and `LPV`, and a `TOTAL` column, covering **31 Indian states/UTs for the year 2024**.
- **Important caveat:** the raw column headers do not explicitly say "electric" — the sheet is labeled as vehicle category data. The project assumes (based on how the export was generated from VAHAN) that these figures represent electric vehicle registrations, but this is not verifiable from the file's headers alone.
- The code does **not** load or process any 2020–June 2025 multi-year data; only this single 2024 snapshot is used.

### Charging Station Data (context only, not loaded in code)

- Referenced source: https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2086533
- This source is used only as background context in the [Literature](#literature--context) section above. The notebook does not read, scrape, or import any data from this source — there is no code that fetches current installed-charger counts.

### External Projection / Reference Data (context only, not loaded in code)

- Referenced source: https://www.thehindu.com/news/cities/bangalore/india-needs-39-lakh-charging-stations-by-2030-report/article69187609.ece
- Mentioned for comparison/context only. The ~39-lakh figure discussed in this article is **not** generated by, or compared against, this project's model in code.

---

## Methodology

### 1. Data Loading

The dataset is uploaded manually at runtime via `google.colab.files.upload()`. The notebook detects the file extension and loads it with `pandas.read_csv` or `pandas.read_excel` (all columns read as strings initially).

### 2. Data Cleaning & Parsing

The raw export has an irregular, multi-row header (state names and category totals mixed with header/label rows), so the code uses a custom row-parsing approach rather than direct column selection:

- Each row is flattened into a single text string.
- A hardcoded list of Indian state/UT names (lowercased) is used to detect which state, if any, each row refers to.
- All numeric tokens in the row are extracted with a regex, and the **largest numeric value found in the row** is taken as that state's total (assumed to correspond to the `TOTAL` column).
- Detected state names are normalized (trimmed, `&` replaced with "and", extra whitespace collapsed, title-cased), with a small manual fix-map for known variants (e.g., "Pondicherry" → "Puducherry").
- A calendar year is auto-detected by regex-searching the raw column headers/first rows for a `20XX` pattern; the notebook's run detected **2024** this way (with 2024 as a hardcoded fallback if no year is found).
- Rows are grouped by `state` and `year` and summed, to handle any duplicate rows for the same state.
- **Rows that failed automatic state detection are dropped from the final table.** In the actual run, this excluded Jammu & Kashmir, Ladakh, and "UT of DNH and DD," because their row text didn't match any entry in the hardcoded state-keyword list — these three regions are **not** represented in the final 31-state dataset or any downstream projection.

### 3. Exploratory Data Analysis

`matplotlib` and `seaborn` are imported and a default plot style is set (`sns.set(style='whitegrid')`), but **no charts are actually generated anywhere in the notebook**. The only "analysis" performed is printing dataframe shapes, unique year/state counts, and displaying intermediate tables. There is no visual EDA in the current implementation.

### 4. Feature Engineering (not used in forecasting)

For each state, the code computes:
- `ev_prev`, `ev_prev2` — prior-year and two-years-prior values (via `groupby().shift()`)
- `growth_1y` — year-over-year growth rate
- `cumulative_ev` — running total

Because the dataset contains only **one year (2024)** per state, these lag/growth features are always `0` (there is no prior year to shift from) or simply equal the current value. They are computed but have **no effect on the projection step** that follows — the actual growth rate used for forecasting is a fixed assumption, not derived from these features.

### 5. EV Projection to Future Years — CAGR-Based (not machine learning)

Despite `scikit-learn` (`train_test_split`, `mean_absolute_error`, `mean_squared_error`, `r2_score`) and `xgboost` being installed and imported at the top of the notebook, **no model from either library is ever instantiated, fitted, or evaluated anywhere in the code.** The actual projection method is a simple compound-growth formula:

```
Projected EVs = Base-Year EVs × (1 + CAGR) ^ (Target Year − Base Year)
```

- `annual_cagr` is hardcoded to **0.30** (30% assumed annual growth), applied uniformly to every state.
- An optional `state_cagr` dictionary allows per-state override rates, but in the current notebook this dictionary is **empty** (the per-state examples are commented out), so every state uses the same 30% rate.
- The base year is each state's latest available year in the cleaned data (2024, for all states, since only one year exists).
- Projections are computed for target years **2026, 2028, and 2030**.

This is a deterministic mathematical projection, not a trained or validated statistical/ML model. No accuracy, R², MAE, or RMSE metrics exist, because no model is fit to held-out data.

### 6. Charging Station Requirement — Throughput-Based Model

Charger requirements are **not** computed with a fixed "EVs ÷ ratio" formula. Instead, for each state/year's projected EV count, the code simulates daily public-charging demand:

```
Public Energy Demand (kWh/day) = Projected EVs × Avg Daily Km/Vehicle × Energy per Km (kWh) × (1 − Home-Charging Share)

Total Charging Sessions/day = Public Energy Demand ÷ Avg Energy per Public Session (kWh)
Fast Sessions/day = Total Sessions × Fast-Charging Share
Slow Sessions/day = Total Sessions − Fast Sessions

Fast Chargers Needed = ceil( Fast Sessions/day ÷ (Operational Hours/day × Utilization ÷ Fast Session Duration) )
Slow Chargers Needed = ceil( Slow Sessions/day ÷ (Operational Hours/day × Utilization ÷ Slow Session Duration) )

Total Chargers Needed = Fast Chargers Needed + Slow Chargers Needed
```

All parameters are hardcoded assumptions in the notebook (see [Assumptions](#assumptions) for the full list and values), not derived from data or a fitted model.

### 7. State-Level Output

The projection (step 5) and charger calculation (step 6) are run independently for each of the 31 states, for each of the three target years (2026, 2028, 2030), and combined into two result tables that are exported as CSV files.

---

## Machine Learning Model

**There is currently no machine-learning model in this project.**

- `scikit-learn` and `xgboost` are listed in the pip-install command and imported at the top of the notebook, but none of their functions or classes (`train_test_split`, `XGBRegressor`, `mean_absolute_error`, `mean_squared_error`, `r2_score`, etc.) are called anywhere in the executed code.
- `joblib` is imported (typically used to save trained models) but is never used to save anything, since no model is trained.
- The actual "forecast" is the fixed-rate CAGR formula described in [Methodology, Step 5](#5-ev-projection-to-future-years--cagr-based-not-machine-learning).

This is flagged here explicitly per project convention: the installed libraries suggest a machine-learning approach was planned, but the current implementation uses a deterministic formula instead. Implementing an actual regression model is listed under [Future Scope](#future-scope).

---

## Technologies and Libraries

| Library | Installed/Imported | Actually Used in Code |
|---|---|---|
| Python (Google Colab) | ✅ | ✅ Runtime environment |
| pandas | ✅ | ✅ Loading, cleaning, aggregation, projection tables |
| NumPy | ✅ | ✅ Numeric operations (`inf` handling, array ops) |
| re / math (standard library) | ✅ | ✅ Regex parsing, `ceil()` in charger calc |
| Matplotlib | ✅ | ⚠️ Imported and styled only — no plots generated |
| Seaborn | ✅ | ⚠️ Imported and styled only — no plots generated |
| scikit-learn | ✅ | ❌ Imported only — no model trained/evaluated |
| XGBoost | ✅ | ❌ Imported only — never instantiated |
| joblib | ✅ | ❌ Imported only — nothing saved |
| openpyxl | ✅ (install only) | Used implicitly by `pandas.read_excel` for `.xlsx` support |
| google.colab | ✅ | ✅ File upload widget (`files.upload()`) |

---

## Results

- The notebook produces a per-state, per-target-year table of projected EV counts (`preds_df`) for 2026, 2028, and 2030, using the 30% CAGR assumption applied to 2024 baseline figures.
- It produces a corresponding per-state, per-target-year table of estimated fast/slow/total charger requirements (`chargers_df`), derived from the throughput model.
- Sample results from the executed run (partial, illustrative only — not exhaustive):

| State | Target Year | Projected EVs | Fast Chargers Needed | Slow Chargers Needed | Total Chargers Needed |
|---|---|---|---|---|---|
| Andhra Pradesh | 2030 | 24,482 | 46 | 551 | 597 |
| Maharashtra | 2026 | *(see full CSV output)* | 8 | 87 | 95 |
| Karnataka | 2028 | *(see full CSV output)* | 13 | 147 | 160 |

Full results for all 31 states and all three target years are written to `ev_sales_projection.csv` and `charger_requirements.csv` (see [Project Structure](#project-structure)). No model-performance metrics are reported, because no predictive model requiring evaluation was trained (see [Machine Learning Model](#machine-learning-model)).

---

## Visualizations

**None currently exist in this project.** Although `matplotlib` and `seaborn` are imported and a plot style is configured at the start of the notebook, no chart, graph, or figure is generated by any cell. Adding EV-trend and charger-requirement visualizations is listed under [Future Scope](#future-scope).

---

## Project Structure

The uploaded project currently consists of a single notebook file:

```text
EVolve.ipynb        # Single Colab notebook containing the entire pipeline:
                     #   - manual dataset upload
                     #   - state-name/row parsing and cleaning
                     #   - feature scaffolding (unused lag features)
                     #   - CAGR-based EV projection (2026/2028/2030)
                     #   - throughput-based charger requirement calculation
                     #   - CSV export of results
```

At runtime, the notebook additionally generates (in the Colab session's `/content/` directory — not included in this repository unless manually downloaded):

```text
ev_sales_projection.csv     # state, target_year, pred_ev_sales, cagr_used
charger_requirements.csv    # state, target_year, pred_ev_sales, energy/session figures,
                             # fast_chargers_needed, slow_chargers_needed, chargers_total
```

No `data/`, `src/`, `outputs/`, or `requirements.txt` folders/files currently exist in the project — the entire pipeline lives in the one notebook, and the input dataset is not bundled with it (it must be supplied by the user at runtime).

---

## How to Run

This notebook is written for **Google Colab** and depends on `google.colab.files` for dataset upload, so it will not run unmodified outside Colab.

1. Open `EVolve.ipynb` in Google Colab.
2. Run the first cell — it installs `xgboost`, `matplotlib`, `seaborn`, `pandas`, `numpy`, `joblib`, and `openpyxl`, then prompts a file-upload dialog.
3. When prompted, upload your VAHAN-exported state-wise vehicle data file (`.csv` or `.xlsx`). The notebook expects a layout similar to the "State Wise Vehicle Category Data" export described in [Data Sources](#data-sources).
4. Run the remaining cells in order:
   - Row inspection and parsing
   - State-name cleaning and aggregation
   - Feature scaffolding
   - CAGR-based EV projection
   - Throughput-based charger calculation
5. The final cell writes `ev_sales_projection.csv` and `charger_requirements.csv` to the Colab session's `/content/` directory — download them from the Colab file browser if you want to keep them.

**Running locally:** replace the `google.colab.files.upload()` cell with a direct `pd.read_csv()` / `pd.read_excel()` call pointing to a local file path; the rest of the pipeline (parsing, projection, charger calculation) is standard pandas/NumPy and does not depend on Colab.

---

## Requirements

Based on the actual `pip install` line in the notebook:

```text
pandas
numpy
matplotlib
seaborn
joblib
openpyxl
xgboost==1.7.6
scikit-learn
```

Note: as detailed in [Technologies and Libraries](#technologies-and-libraries), `matplotlib`, `seaborn`, `xgboost`, `scikit-learn`, and `joblib` are installed/imported but not functionally exercised by the current code — they are included here because the notebook installs them, not because removing them would currently break functionality.

---

## Assumptions

All figures below are hardcoded parameters in the notebook, not derived from data:

**Growth assumption:**
- Annual EV growth rate (CAGR): **30%**, applied uniformly to all states (adjustable in code between roughly 15–40%; per-state overrides are supported but currently unused).

**Charging-demand assumptions (throughput model):**
| Parameter | Value |
|---|---|
| Average daily distance driven per EV | 30 km |
| Energy consumption | 0.15 kWh/km |
| Share of energy charged at home/private | 70% |
| Average energy delivered per public session | 8.0 kWh |
| Share of public sessions on fast chargers | 20% |
| Charger operational hours per day | 18 hours |
| Utilization factor | 50% |
| Average fast-charging session duration | 30 minutes |
| Average slow-charging session duration | 90 minutes |

**Other assumptions:**
- Each state's 2024 total is treated as an independent baseline; state-level projections do not account for interactions between states (e.g., cross-border charging use).
- The single available data year (2024) is treated as representative enough to project forward via a fixed growth rate, in the absence of multi-year historical data.
- Real-world factors — policy changes, fuel prices, consumer behavior shifts, grid constraints, and technology change — are not modeled and may cause actual outcomes to differ from these projections.

---

## Limitations

- **The core scoping assumption of multi-year (2020–June 2025) historical data does not match the code.** The notebook processes a single 2024 snapshot; no historical trend is available to validate or ground the 30% growth assumption.
- The growth rate (30%/year) is an assumption, not one estimated from data, a model fit, or a cited external source within the code.
- No machine-learning model is actually trained or evaluated, despite `scikit-learn` and `xgboost` being installed — there are no accuracy metrics to report.
- Three regions (Jammu & Kashmir, Ladakh, and the Dadra & Nagar Haveli/Daman & Diu union territory) are silently excluded from the final dataset because the state-name-matching logic didn't recognize their row text — this reduces state coverage from India's full set of states/UTs to 31.
- The "largest number in the row" heuristic used to identify each state's total is fragile — it would misparse any row where a different column (e.g., serial number, or a category count) happens to exceed the true total.
- The throughput-based charger calculation depends entirely on the nine hardcoded assumptions above; none are calibrated against real charger utilization data.
- No comparison is made against actual existing charging infrastructure counts, so it's not possible from the code alone to say whether projected requirements represent net-new stations or overlap with what already exists.
- No exploratory visualizations exist to sanity-check the cleaned data or the resulting projections.
- Forecast uncertainty is not quantified anywhere (no confidence intervals, sensitivity analysis, or scenario ranges are computed).

---

## Future Scope

Potential extensions — **none of the following are currently implemented**:

- Incorporating actual multi-year (2020–June 2025) EV registration data, as originally scoped, to derive an empirical growth rate rather than assuming a fixed CAGR.
- Implementing an actual machine-learning or time-series model (e.g., using the already-installed `scikit-learn`/`xgboost`) with proper train/test evaluation and reported metrics.
- Adding exploratory visualizations (year-wise trends, state comparisons, projected-vs-current infrastructure charts) using the already-imported `matplotlib`/`seaborn`.
- Comparing projected charger requirements against actual current installed infrastructure (e.g., from the PIB press-release data referenced in this README) to estimate incremental need.
- Expanding beyond electric passenger cars to two-wheelers and three-wheelers.
- Incorporating state population, urbanization, income/GDP, and fuel-price data as additional predictors.
- Incorporating state-specific EV policy and incentive data.
- Distinguishing AC vs. DC/fast charger types more granularly, and separating highway vs. urban charging needs.
- Accounting for electricity grid capacity constraints.
- Producing district-level rather than state-level estimates.
- Building an interactive dashboard for exploring projections under different assumptions.

---

## Summary of Discrepancies Flagged in This README

For transparency, per the project's documentation conventions, here is a consolidated list of places where the original project description differs from what the code implements:

1. **Time range:** Described as 2020–June 2025; code uses a single 2024 snapshot.
2. **Forecasting method:** Described as machine learning; code uses a fixed-rate CAGR formula. ML libraries are installed/imported but unused.
3. **Visualizations:** Described as part of the analysis; no charts are generated in the code, despite plotting libraries being imported and styled.
4. **State coverage:** Three regions are silently dropped due to name-matching gaps, so coverage is 31 states/UTs rather than all Indian states/UTs.
5. **Charging Station Data / External Projection sources:** Referenced as data sources in the brief; in the code they are not loaded or used — they are contextual/literature references only.
