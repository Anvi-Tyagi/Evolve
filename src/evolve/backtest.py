"""Expanding-window backtest of the growth models against the two baselines.

For each fold (train years start..end, test year T) and category, every model is fitted
on rows with year < T only and scored on year T. Zero-filled rows are excluded from both
training and scoring. A state that no model can predict (no observed training history)
is excluded from every model's score for that fold, so all models are scored on the
same rows; such exclusions are returned and reported.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config
from .models import BASELINE_NAMES, MODEL_NAMES, Pooled, make_model, mape, training_rows, wape
from .report import md_table

NATIONAL_TREND = "national_trend"
NATIONAL_CANDIDATES = (NATIONAL_TREND,) + BASELINE_NAMES

RESULT_COLUMNS = ["fold", "train_start", "train_end", "test_year", "category", "level",
                  "model", "n_rows", "wape", "mape", "mape_rows", "national_pct_error"]


@dataclass
class BacktestResult:
    results: pd.DataFrame
    excluded: list = field(default_factory=list)   # (fold, category, state, reason)
    lambdas: dict = field(default_factory=dict)    # (fold, category) -> chosen lambda
    inner_scores: dict = field(default_factory=dict)
    pooled_growth: dict = field(default_factory=dict)  # (fold, category) -> exp(slope) - 1


def split(cat_df: pd.DataFrame, start: int, end: int, test_year: int):
    """Training rows (start..end) and observed test rows for one fold. Enforces no leakage."""
    if end >= test_year:
        raise ValueError(f"training window ends {end}, not before test year {test_year}")
    train = cat_df[(cat_df["year"] >= start) & (cat_df["year"] <= end)]
    assert train["year"].max() < test_year, "leakage: training data reaches the test year"
    test = training_rows(cat_df[cat_df["year"] == test_year])
    return train, test


def national_series(cat_df: pd.DataFrame) -> pd.DataFrame:
    """National total per year from observed (non-zero-filled) rows."""
    obs = training_rows(cat_df)
    nat = obs.groupby("year", as_index=False)["count"].sum()
    nat["state"] = config.NATIONAL_LABEL
    nat["zero_filled"] = False
    return nat[["state", "year", "count", "zero_filled"]]


def _metrics(actual, pred) -> dict:
    m, n_m = mape(actual, pred, config.MAPE_MIN_ACTUAL)
    tot = float(np.sum(actual))
    return {"n_rows": int(len(actual)), "wape": wape(actual, pred), "mape": m, "mape_rows": n_m,
            "national_pct_error": float((np.sum(pred) - tot) / tot) if tot > 0 else float("nan")}


def _make_national(name):
    return Pooled() if name == NATIONAL_TREND else make_model(name)


def run_backtest(long: pd.DataFrame, folds=config.BACKTEST_FOLDS) -> BacktestResult:
    rows, out = [], BacktestResult(results=pd.DataFrame())
    categories = config.TARGET_CATEGORIES + config.LOW_VOLUME_CATEGORIES
    for fold_no, (start, end, test_year) in enumerate(folds, start=1):
        for cat in categories:
            cat_df = long[long["category"] == cat]
            train, test = split(cat_df, start, end, test_year)
            names = MODEL_NAMES if cat in config.TARGET_CATEGORIES else BASELINE_NAMES

            # State level.
            preds = {}
            for name in names:
                model = make_model(name).fit(train)
                if name == "pooled":
                    out.pooled_growth[(fold_no, cat)] = model.growth_rate()
                if name == "shrinkage":
                    out.lambdas[(fold_no, cat)] = model.lam
                    out.inner_scores[(fold_no, cat)] = dict(model.inner_scores_)
                p = model.predict(test["state"], [test_year]).set_index("state")["forecast"]
                preds[name] = p
            unpredictable = sorted(set().union(*(set(p.index[p.isna()]) for p in preds.values())))
            for s in unpredictable:
                out.excluded.append((fold_no, cat, s, "no observed training history"))
            scored = test[~test["state"].isin(unpredictable)]
            for name in names:
                pred = preds[name].reindex(scored["state"]).to_numpy()
                rows.append({"fold": fold_no, "train_start": start, "train_end": end,
                             "test_year": test_year, "category": cat, "level": "state",
                             "model": name, **_metrics(scored["count"].to_numpy(), pred)})

            # National level for low-volume categories (one series, one point per fold).
            if cat in config.LOW_VOLUME_CATEGORIES:
                nat = national_series(cat_df)
                nat_train = nat[(nat["year"] >= start) & (nat["year"] <= end)]
                nat_test = nat[nat["year"] == test_year]
                for name in NATIONAL_CANDIDATES:
                    m = _make_national(name).fit(nat_train)
                    pred = m.predict([config.NATIONAL_LABEL], [test_year])["forecast"].to_numpy()
                    rows.append({"fold": fold_no, "train_start": start, "train_end": end,
                                 "test_year": test_year, "category": cat, "level": "national",
                                 "model": name, **_metrics(nat_test["count"].to_numpy(), pred)})
    out.results = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    return out


def select_models(results: pd.DataFrame) -> dict:
    """Selection rule (fixed in advance): lowest mean WAPE across folds.

    Returns {(category, level): model}. Target categories choose among all four state-level
    candidates; low-volume categories choose between the baselines at state level and
    among national_trend + baselines at national level. Ties: candidate order.
    """
    order = {n: i for i, n in enumerate(MODEL_NAMES + (NATIONAL_TREND,))}
    mean = results.groupby(["category", "level", "model"])["wape"].mean().reset_index()
    mean["order"] = mean["model"].map(order)
    chosen = {}
    for (cat, level), g in mean.groupby(["category", "level"]):
        best = g.sort_values(["wape", "order"]).iloc[0]
        chosen[(cat, level)] = best["model"]
    return chosen


def _pct(x) -> str:
    return "n/a" if pd.isna(x) else f"{x * 100:.1f}%"


def national_growth(long: pd.DataFrame) -> pd.DataFrame:
    """Year-on-year growth of national total registrations (all categories, observed rows)."""
    tot = training_rows(long).groupby("year")["count"].sum()
    return pd.DataFrame({"year": tot.index, "total": tot.values, "growth": tot.pct_change().values})


def render_report(bt: BacktestResult, selection: dict, long: pd.DataFrame) -> str:
    res = bt.results
    L = ["# EV registrations forecast backtest", "",
         "Statistical growth modelling (curve fitting) on annual new EV registrations per state. "
         "Expanding-window backtest; every model is fitted only on years before the test year.", ""]
    L += ["Folds: " + "; ".join(f"fold {i}: train {s}-{e}, test {t}"
                                for i, (s, e, t) in enumerate(config.BACKTEST_FOLDS, 1)) + ".", ""]
    L += ["Metrics (fixed in advance): **WAPE** = sum |forecast - actual| / sum actual (headline). "
          f"MAPE only on state-category rows with actual >= {config.MAPE_MIN_ACTUAL} "
          "(rows used shown). National % error = (sum forecast - sum actual) / sum actual. "
          "Zero-filled rows are excluded from training and scoring.", ""]
    L += ["Selection rule (fixed in advance): for each category, the candidate with the lowest "
          "mean WAPE across the two folds.", ""]

    # National growth note.
    ng = national_growth(long)
    L += ["## National growth slowdown", ""]
    L.append(md_table([[int(r.year), f"{int(r.total):,}", _pct(r.growth)] for r in ng.itertuples()],
                      ["Year", "National EV registrations", "Growth vs previous year"]))
    recent = ng[ng["year"].isin([t for *_, t in config.BACKTEST_FOLDS])]
    g30 = res[(res["model"] == "growth30") & (res["level"] == "state")]
    below = [int(r.year) for r in recent.itertuples() if r.growth < config.BASELINE_GROWTH]
    if len(below) == len(recent):
        comparison = (f"Observed national growth was below {config.BASELINE_GROWTH:.0%} in every test year, "
                      "so the fixed rule overshoots nationally unless growth re-accelerates.")
    elif below:
        comparison = (f"Observed national growth was below {config.BASELINE_GROWTH:.0%} in "
                      f"{', '.join(map(str, below))}.")
    else:
        comparison = f"Observed national growth was at or above {config.BASELINE_GROWTH:.0%} in every test year."
    L += ["", f"Growth was {', '.join(f'{_pct(r.growth)} in {int(r.year)}' for r in recent.itertuples())}. "
          f"The legacy fixed {config.BASELINE_GROWTH:.0%} rule assumes every state keeps growing "
          f"{config.BASELINE_GROWTH:.0%} a year. {comparison} Its national % error per category and fold "
          "is in the tables below "
          f"(range {_pct(g30['national_pct_error'].min())} to {_pct(g30['national_pct_error'].max())}).", ""]

    # Main tables.
    L += ["## Results by category (state level)", ""]
    for cat in config.TARGET_CATEGORIES + config.LOW_VOLUME_CATEGORIES:
        low = cat in config.LOW_VOLUME_CATEGORIES
        L += [f"### {cat}" + (" (low volume: baselines only at state level)" if low else ""), ""]
        sub = res[(res["category"] == cat) & (res["level"] == "state")]
        L.append(_results_table(sub))
        mean = sub.groupby("model")["wape"].mean()
        L.append(_mean_line(mean, selection[(cat, "state")]))
        if not low:
            L.append(_verdict(sub))
        L.append("")
        if low:
            nat = res[(res["category"] == cat) & (res["level"] == "national")]
            L += [f"National level ({cat}, one series; WAPE equals absolute % error here):", ""]
            L.append(_results_table(nat, national=True))
            L.append(_mean_line(nat.groupby("model")["wape"].mean(), selection[(cat, "national")]))
            L.append("")

    L += ["## Implied annual growth of the pooled model", "",
          "exp(shared slope) - 1 on the log1p scale, fitted on each fold's training years.", ""]
    L.append(md_table([[f, c, _pct(g)] for (f, c), g in sorted(bt.pooled_growth.items())],
                      ["Fold", "Category", "Implied annual growth"]))
    L.append("")

    L += ["## Shrinkage strength chosen inside each training window", "",
          "Lambda is picked by one-step-ahead inner folds within the training years only; "
          "0 = each state's own slope, inf = pooled slope.", ""]
    L.append(md_table([[f, c, bt.lambdas[(f, c)], ", ".join(f"{k}: {_pct(v)}" for k, v in bt.inner_scores[(f, c)].items())]
                       for (f, c) in sorted(bt.lambdas)],
                      ["Fold", "Category", "Chosen lambda", "Inner mean WAPE by lambda"]))

    L += ["## Rows excluded from scoring", "",
          "Excluded identically for every model in that fold (no model can forecast a state "
          "with no observed training years).", ""]
    L.append(md_table([list(e) for e in bt.excluded], ["Fold", "Category", "State", "Reason"]))

    L += ["## Not included", "",
          "- Logistic S-curve: needs a saturation ceiling; none has been supplied as an "
          "explicit assumption, and six annual points cannot identify one.",
          "- Uncertainty bands: planned for a later phase.", ""]
    return "\n".join(L)


def _results_table(sub: pd.DataFrame, national=False) -> str:
    rows = []
    for r in sub.sort_values(["fold", "model"]).itertuples():
        row = [r.fold, r.test_year, r.model, _pct(r.wape)]
        if not national:
            row += [_pct(r.mape), r.mape_rows, r.n_rows]
        row.append(_pct(r.national_pct_error))
        rows.append(row)
    headers = ["Fold", "Test year", "Model", "WAPE"]
    if not national:
        headers += ["MAPE", "MAPE rows", "Rows scored"]
    headers.append("National % error")
    return md_table(rows, headers)


def _mean_line(mean: pd.Series, chosen: str) -> str:
    parts = ", ".join(f"{m} {_pct(v)}" for m, v in mean.sort_values().items())
    return f"\nMean WAPE across folds: {parts}. **Selected: {chosen}.**\n"


def _verdict(sub: pd.DataFrame) -> str:
    """Plain statement of whether the fitted models beat both baselines on each fold."""
    w = sub.pivot(index="fold", columns="model", values="wape")
    lines = []
    for model in ("pooled", "shrinkage"):
        beats = [(f, all(w.loc[f, model] < w.loc[f, b] for b in BASELINE_NAMES)) for f in w.index]
        if all(b for _, b in beats):
            lines.append(f"- {model} beats both baselines on every fold.")
        elif not any(b for _, b in beats):
            lines.append(f"- {model} does **not** beat both baselines on any fold.")
        else:
            ok = ", ".join(str(f) for f, b in beats if b)
            lines.append(f"- {model} beats both baselines only on fold(s) {ok}.")
    best_model = min(w[["pooled", "shrinkage"]].mean().items(), key=lambda kv: kv[1])
    best_base = min(w[list(BASELINE_NAMES)].mean().items(), key=lambda kv: kv[1])
    if best_model[1] < best_base[1]:
        lines.append(f"- On mean WAPE, the best model ({best_model[0]}) beats the best baseline ({best_base[0]}).")
    else:
        lines.append(f"- On mean WAPE, the models do **not** beat the best baseline ({best_base[0]}).")
    return "\n".join(lines) + "\n"
