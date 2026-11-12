"""Base forecasts of annual EV registrations for FORECAST_YEARS.

Each category's model is the one chosen by the backtest selection rule; it is refitted on
all observed years (zero-filled rows excluded). Both baselines are always written too, for
comparison. No uncertainty bands in this phase.
"""
import pandas as pd

from . import config
from .backtest import NATIONAL_TREND, _make_national, national_series
from .models import BASELINE_NAMES, make_model
from .report import md_table

FORECAST_COLUMNS = ["state", "category", "year", "forecast", "model", "selected", "low_volume"]


def run_forecast(long: pd.DataFrame, selection: dict, years=config.FORECAST_YEARS):
    """Return (forecast frame, notes) where notes records what was fitted."""
    years = list(years)
    if long["year"].max() >= min(years):
        raise ValueError("forecast years overlap the observed data")
    frames, notes = [], []
    for cat in config.TARGET_CATEGORIES + config.LOW_VOLUME_CATEGORIES:
        low = cat in config.LOW_VOLUME_CATEGORIES
        cat_df = long[long["category"] == cat]
        states = sorted(cat_df["state"].unique())
        chosen = selection[(cat, "state")]
        names = list(dict.fromkeys([chosen, *BASELINE_NAMES]))
        for name in names:
            model = make_model(name).fit(cat_df)
            pred = model.predict(states, years)
            frames.append(pred.assign(category=cat, model=name, selected=name == chosen, low_volume=low))
            notes.append({"category": cat, "level": "state", "model": name, "selected": name == chosen,
                          "lambda": getattr(model, "lam", None) if name == "shrinkage" else None,
                          "train_years": f"{int(cat_df['year'].min())}-{int(cat_df['year'].max())}"})
        if low:
            nat = national_series(cat_df)
            nat_chosen = selection[(cat, "national")]
            for name in (NATIONAL_TREND, *BASELINE_NAMES):
                pred = _make_national(name).fit(nat).predict([config.NATIONAL_LABEL], years)
                frames.append(pred.assign(category=cat, model=name, selected=name == nat_chosen,
                                          low_volume=True))
                notes.append({"category": cat, "level": "national", "model": name,
                              "selected": name == nat_chosen, "lambda": None,
                              "train_years": f"{int(nat['year'].min())}-{int(nat['year'].max())}"})
    out = pd.concat(frames, ignore_index=True)[FORECAST_COLUMNS]
    missing = out[out["forecast"].isna()]
    if not missing.empty:
        raise ValueError(f"no forecast possible for: {missing[['state', 'category', 'model']].drop_duplicates().values.tolist()}")
    out = out.sort_values(["category", "model", "state", "year"]).reset_index(drop=True)
    return out, notes


def render_section(fc: pd.DataFrame, notes: list) -> str:
    """Markdown section appended to the backtest report describing the forecast run."""
    L = ["## Forecast run", "",
         f"Models refitted on all observed years and projected for {min(fc['year'])}-{max(fc['year'])}. "
         "`selected` marks the model chosen by the backtest rule; baselines are written for comparison. "
         "No uncertainty bands in this phase.", ""]
    L.append(md_table([[n["category"], n["level"], n["model"], "yes" if n["selected"] else "",
                        "" if n["lambda"] is None else n["lambda"], n["train_years"]] for n in notes],
                      ["Category", "Level", "Model", "Selected", "Lambda", "Fitted on"]))
    sel = fc[fc["selected"]]
    state_sel = sel[sel["state"] != config.NATIONAL_LABEL]
    tot = state_sel.groupby(["category", "year"])["forecast"].sum().unstack("year")
    L += ["", "Sum over states of the selected forecasts (annual new registrations):", ""]
    yrs = list(tot.columns)
    L.append(md_table([[c] + [f"{tot.loc[c, y]:,.0f}" for y in yrs] for c in tot.index], ["Category"] + yrs))
    return "\n".join(L)
