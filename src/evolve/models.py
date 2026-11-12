"""Simple growth models for annual EV registrations (statistical curve fitting, not ML).

Every model is fitted on one category's training rows (columns: state, year, count,
optionally zero_filled) and predicts any (state, year) pairs. Zero-filled rows are not
observations and are dropped before fitting. Nothing here uses randomness.

Log-linear models work on y = log1p(count) and x = year:
  pooled     y = a_s + b * x            (state intercepts, one shared slope)
  shrinkage  y = a_s + b_s' * x,  b_s' = w_s * b_s + (1 - w_s) * b,  w_s = Sxx_s / (Sxx_s + lam)
"""
import math

import numpy as np
import pandas as pd

from . import config


def training_rows(train: pd.DataFrame) -> pd.DataFrame:
    """Observed rows only: drop zero-filled rows and missing counts."""
    df = train
    if "zero_filled" in df:
        df = df[~df["zero_filled"].astype(bool)]
    df = df[df["count"].notna()]
    return df[["state", "year", "count"]].astype({"year": int, "count": float})


def _frame(states, years, values) -> pd.DataFrame:
    return pd.DataFrame({"state": states, "year": years, "forecast": values})


def _grid(states, years):
    states, years = list(states), list(years)
    return [s for s in states for _ in years], [y for _ in states for y in years]


class _LastValueModel:
    name = "naive"
    growth = 0.0

    def fit(self, train):
        df = training_rows(train).sort_values(["state", "year"])
        last = df.groupby("state").tail(1).set_index("state")
        self.last_year_ = last["year"].to_dict()
        self.last_value_ = last["count"].to_dict()
        self.train_max_year_ = int(df["year"].max()) if len(df) else None
        return self

    def predict(self, states, years):
        ss, yy = _grid(states, years)
        vals = []
        for s, y in zip(ss, yy):
            if s not in self.last_value_:
                vals.append(np.nan)  # no observed history for this state
                continue
            h = y - self.last_year_[s]
            vals.append(self.last_value_[s] * (1.0 + self.growth) ** h)
        return _frame(ss, yy, vals)


class Naive(_LastValueModel):
    """Same as last observed year."""
    name = "naive"
    growth = 0.0


class FixedGrowth(_LastValueModel):
    """Last observed value grown at a fixed annual rate (legacy notebook rule: 30%)."""

    def __init__(self, growth=config.BASELINE_GROWTH):
        self.growth = growth
        self.name = f"growth{round(growth * 100)}"


class _LogLinear:
    """Shared fitting code: per-state means and sums, then a slope per state."""

    def _stats(self, train):
        df = training_rows(train).copy()
        df["y"] = np.log1p(df["count"])
        g = df.groupby("state")
        xbar, ybar = g["year"].transform("mean"), g["y"].transform("mean")
        df["xd"], df["yd"] = df["year"] - xbar, df["y"] - ybar
        st = pd.DataFrame({
            "xbar": g["year"].mean(),
            "ybar": g["y"].mean(),
            "sxx": (df["xd"] ** 2).groupby(df["state"]).sum(),
            "sxy": (df["xd"] * df["yd"]).groupby(df["state"]).sum(),
            "n": g.size(),
        })
        total_sxx = st["sxx"].sum()
        self.pooled_slope_ = float(st["sxy"].sum() / total_sxx) if total_sxx > 0 else 0.0
        self.train_max_year_ = int(df["year"].max()) if len(df) else None
        return st

    def _set_lines(self, st, slopes):
        self.slope_ = slopes.to_dict()
        self.intercept_ = (st["ybar"] - slopes * st["xbar"]).to_dict()

    def predict(self, states, years):
        ss, yy = _grid(states, years)
        vals = []
        for s, y in zip(ss, yy):
            if s not in self.slope_:
                vals.append(np.nan)
                continue
            vals.append(max(0.0, math.expm1(self.intercept_[s] + self.slope_[s] * y)))
        return _frame(ss, yy, vals)

    def growth_rate(self, state=None) -> float:
        """Implied annual growth factor minus one, exp(slope) - 1 (on the log1p scale)."""
        b = self.pooled_slope_ if state is None else self.slope_[state]
        return math.exp(b) - 1.0


class Pooled(_LogLinear):
    """State-specific intercepts and one shared slope (within-state OLS)."""
    name = "pooled"

    def fit(self, train):
        st = self._stats(train)
        self._set_lines(st, pd.Series(self.pooled_slope_, index=st.index))
        return self


def shrink_weights(sxx: pd.Series, lam: float) -> pd.Series:
    """w = Sxx / (Sxx + lam); states with Sxx = 0 (one year of data) get w = 0."""
    if math.isinf(lam):
        return pd.Series(0.0, index=sxx.index)
    if lam == 0:
        return (sxx > 0).astype(float)
    return sxx / (sxx + lam)


class Shrinkage(_LogLinear):
    """State slopes shrunk toward the pooled slope with a fixed strength lam."""
    name = "shrinkage"

    def __init__(self, lam: float):
        self.lam = float(lam)

    def fit(self, train):
        st = self._stats(train)
        own = (st["sxy"] / st["sxx"].where(st["sxx"] > 0)).fillna(self.pooled_slope_)
        w = shrink_weights(st["sxx"], self.lam)
        self.weights_ = w.to_dict()
        self._set_lines(st, w * own + (1 - w) * self.pooled_slope_)
        return self


def wape(actual, pred) -> float:
    """Weighted absolute percentage error: sum |pred - actual| / sum actual."""
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    denom = a.sum()
    return float(np.abs(p - a).sum() / denom) if denom > 0 else float("nan")


def mape(actual, pred, min_actual=config.MAPE_MIN_ACTUAL):
    """Mean absolute percentage error on rows with actual >= min_actual.

    Returns (mape, rows_used); mape is NaN if no row qualifies.
    """
    a, p = np.asarray(actual, float), np.asarray(pred, float)
    keep = a >= min_actual
    n = int(keep.sum())
    if n == 0:
        return float("nan"), 0
    return float(np.mean(np.abs(p[keep] - a[keep]) / a[keep])), n


def _one_step_wape(model, train, test_year) -> float:
    fit_rows = train[train["year"] < test_year]
    actual = training_rows(train[train["year"] == test_year])
    if actual.empty:
        return float("nan")
    model.fit(fit_rows)
    pred = model.predict(actual["state"].unique(), [test_year]).merge(actual, on=["state", "year"])
    pred = pred[pred["forecast"].notna()]
    return wape(pred["count"], pred["forecast"])


class ShrinkageCV(_LogLinear):
    """Shrinkage with lam chosen from the training data only.

    Inner folds: every training year t that has at least
    SHRINKAGE_MIN_INNER_TRAIN_YEARS earlier training years is predicted one step ahead
    from those earlier years. The lam with the lowest mean inner WAPE is used; ties go
    to the larger lam (closer to the pooled model). If no inner fold is possible, lam = inf.
    """
    name = "shrinkage"

    def __init__(self, grid=config.SHRINKAGE_GRID, min_train_years=config.SHRINKAGE_MIN_INNER_TRAIN_YEARS):
        self.grid = tuple(grid)
        self.min_train_years = min_train_years

    def fit(self, train):
        obs = training_rows(train)
        years = sorted(obs["year"].unique())
        inner = [t for t in years if sum(y < t for y in years) >= self.min_train_years]
        self.inner_years_ = inner
        self.inner_scores_ = {}
        best_lam, best = float("inf"), float("inf")
        for lam in sorted(self.grid, reverse=True):  # larger lam first -> wins ties
            scores = [_one_step_wape(Shrinkage(lam), obs, t) for t in inner]
            score = float(np.mean(scores)) if scores else float("nan")
            self.inner_scores_[lam] = score
            if scores and score < best:
                best_lam, best = lam, score
        self.lam = best_lam
        inner_model = Shrinkage(best_lam).fit(obs)
        self.__dict__.update({k: v for k, v in inner_model.__dict__.items() if k != "lam"})
        return self


def make_model(name: str):
    """Fresh, unfitted model by name."""
    if name == "naive":
        return Naive()
    if name == "growth30":
        return FixedGrowth(config.BASELINE_GROWTH)
    if name == "pooled":
        return Pooled()
    if name == "shrinkage":
        return ShrinkageCV()
    raise ValueError(f"Unknown model {name!r}")


MODEL_NAMES = ("pooled", "shrinkage", "naive", "growth30")
BASELINE_NAMES = ("naive", "growth30")
