"""Reusable primitives for the validated mean-reversion factor score.

See STRATEGY_RESEARCH_REPORT.md (sections 3-6) for the research behind this:
Spearman IC between distance_ma20 / return_20d / realized_vol_20d and
forward_return_20d, walk-forward validated (single-split + rolling 5-fold) on
VN 2020-2026 data. All three factors are used INVERTED (low raw value ranks
highest) -- this is a mean-reversion score, not a momentum-chasing one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FACTORS = ["distance_ma20", "return_20d", "realized_vol_20d"]

# Full-history calibration (matches STRATEGY_RESEARCH_REPORT.md section 6
# exactly: weights proportional to |IC|, all three signs negative). Treat as
# a default, not a permanent constant -- recalibrate periodically by calling
# compute_factor_ic + derive_factor_weights on a fresh TRAIN window.
DEFAULT_WEIGHTS = {"distance_ma20": 0.39, "return_20d": 0.32, "realized_vol_20d": 0.29}
DEFAULT_SIGNS = {"distance_ma20": -1, "return_20d": -1, "realized_vol_20d": -1}


def _spearman_ic(x: pd.Series, y: pd.Series) -> float | None:
    both = pd.concat([x, y], axis=1).dropna()
    if len(both) < 10:
        return None
    return both.iloc[:, 0].corr(both.iloc[:, 1], method="spearman")


def compute_factor_ic(
    features: pd.DataFrame,
    factors: list[str] = FACTORS,
    target_col: str = "forward_return_20d",
    rebalance_period: int = 20,
    min_value_ma20: float = 10_000_000_000.0,
    require_above_ma200: bool = True,
    min_eligible: int = 15,
) -> dict[str, float]:
    """Mean Spearman IC of each raw factor column vs. target_col, sampled
    every `rebalance_period` sessions with the decision lagged 1 session
    (same convention as scratch/walk_forward_validation.py). The caller
    controls the train/test split by pre-filtering `features` to the desired
    date range -- this function has no notion of train vs test itself.
    """
    if features.empty:
        return {name: 0.0 for name in factors}
    all_dates = sorted(features["date"].unique())
    rebalance_dates = all_dates[::rebalance_period]
    records: dict[str, list[float]] = {name: [] for name in factors}
    for idx, current_date in enumerate(rebalance_dates):
        if idx == 0:
            continue
        decision_date = all_dates[all_dates.index(current_date) - 1]
        snap = features[features["date"] == decision_date].set_index("symbol")
        if snap.empty or target_col not in snap.columns:
            continue
        eligible = snap.copy()
        if "value_ma20" in eligible.columns:
            eligible = eligible[eligible["value_ma20"].fillna(0) >= min_value_ma20]
        if require_above_ma200 and "above_ma200" in eligible.columns:
            eligible = eligible[eligible["above_ma200"].astype(bool)]
        if len(eligible) < min_eligible:
            continue
        fwd = eligible[target_col]
        for name in factors:
            if name not in eligible.columns:
                continue
            ic = _spearman_ic(eligible[name], fwd)
            if ic is not None:
                records[name].append(ic)
    return {name: (float(np.mean(v)) if v else 0.0) for name, v in records.items()}


def derive_factor_weights(mean_ic: dict[str, float]) -> tuple[dict[str, float], dict[str, int]]:
    """weights proportional to |IC|; signs = direction of IC (>=0 -> +1, else -1)."""
    abs_sum = sum(abs(v) for v in mean_ic.values()) or 1.0
    weights = {name: abs(v) / abs_sum for name, v in mean_ic.items()}
    signs = {name: (1 if v >= 0 else -1) for name, v in mean_ic.items()}
    return weights, signs


def score_reversal_quality(
    features: pd.DataFrame,
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    signs: dict[str, int] = DEFAULT_SIGNS,
    factors: list[str] = FACTORS,
    score_col: str = "reversal_quality_score",
) -> pd.DataFrame:
    """Per-date cross-sectional percentile-rank weighted composite.

    Sign convention: signs[name] is applied to the RAW column before
    ranking, so a -1 sign means "low raw values rank highest" (e.g. low
    distance_ma20 = not overbought, low return_20d = just pulled back, low
    realized_vol_20d = calm). Missing values rank at the 50th percentile
    (neutral), matching scratch/rolling_walk_forward.py::build_score exactly.
    Returns only ["symbol", "date", score_col] -- callers merge back onto
    their own feature frame as needed.
    """
    cols_present = [c for c in factors if c in features.columns]
    df = features[["symbol", "date"] + cols_present].copy()
    grouped = df.groupby("date")
    total = pd.Series(0.0, index=df.index)
    for name in cols_present:
        sign = signs.get(name, 1)
        rank = grouped[name].transform(lambda s, _sign=sign: (s * _sign).rank(pct=True))
        total = total + weights.get(name, 0.0) * rank.fillna(0.5)
    df[score_col] = total * 100.0
    return df[["symbol", "date", score_col]]
