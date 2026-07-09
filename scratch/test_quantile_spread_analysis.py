"""One-off diagnostic (not part of the codebase): does a QUANTILE/tail-based
view of each factor reveal signal that the whole-distribution Spearman IC
(scratch/test_corp_action_zerofill_alternative.py) might mask?

Motivation: a layered/sequential filter architecture (each stage removes the
worst names by one factor) specifically exploits TAIL behavior -- "the worst
quintile underperforms" -- which a single rank correlation coefficient can
dilute if the true relationship is concentrated in the extremes rather than
monotonic across the whole range. Before designing any multi-stage filter
architecture around these 3 factors, check directly: does sorting into
quintiles by each factor show a real, walk-forward-stable spread in
subsequent forward_return_20d between the best and worst bucket?

Uses the zero-fill return computation (scratch/test_corp_action_zerofill_alternative.py)
since it is the least destructive, most information-preserving handling of
the corporate-action issue found so far.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet

features = read_parquet("data/processed/stock_features.parquet")
features["date"] = pd.to_datetime(features["date"])
features = features.sort_values(["symbol", "date"]).reset_index(drop=True)

return_1d_zerofilled = features["return_1d"].where(~features["suspect_corporate_action"], 0.0)
HOLDING = 20
features["return_20d"] = return_1d_zerofilled.groupby(features["symbol"]).transform(
    lambda s: (1.0 + s).rolling(HOLDING).apply(np.prod, raw=True) - 1.0
)
features["forward_return_20d"] = return_1d_zerofilled.groupby(features["symbol"]).transform(
    lambda s: (1.0 + s.shift(-HOLDING)).rolling(HOLDING).apply(np.prod, raw=True) - 1.0
)

MIN_VALUE_MA20 = 10_000_000_000.0
REBALANCE_PERIOD = 20
FACTORS = ["distance_ma20", "return_20d", "realized_vol_20d"]
N_QUANTILES = 5

all_dates = sorted(features["date"].unique())
rebalance_dates = all_dates[::REBALANCE_PERIOD]

records: dict[str, list[pd.DataFrame]] = {name: [] for name in FACTORS}

for idx, current_date in enumerate(rebalance_dates):
    if idx == 0:
        continue
    decision_date = all_dates[all_dates.index(current_date) - 1]
    snap = features[features["date"] == decision_date].copy()
    if "value_ma20" in snap.columns:
        snap = snap[snap["value_ma20"].fillna(0) >= MIN_VALUE_MA20]
    if "above_ma200" in snap.columns:
        snap = snap[snap["above_ma200"].astype(bool)]
    snap = snap.dropna(subset=["forward_return_20d"])
    if len(snap) < 15:
        continue
    for name in FACTORS:
        sub = snap.dropna(subset=[name])
        if len(sub) < 15:
            continue
        sub = sub.copy()
        try:
            sub["quantile"] = pd.qcut(sub[name], N_QUANTILES, labels=False, duplicates="drop")
        except ValueError:
            continue
        records[name].append(sub[["quantile", "forward_return_20d"]])

print(f"Quantile spread analysis (N_QUANTILES={N_QUANTILES}), factor sorted ascending "
      f"(quantile 0 = lowest raw value, quantile {N_QUANTILES - 1} = highest raw value)\n")

for name in FACTORS:
    if not records[name]:
        print(f"{name}: no data")
        continue
    all_obs = pd.concat(records[name], ignore_index=True)
    summary = all_obs.groupby("quantile")["forward_return_20d"].agg(["mean", "median", "count"])
    print(f"--- {name} ---")
    print(summary.to_string())
    top = all_obs[all_obs["quantile"] == all_obs["quantile"].max()]["forward_return_20d"]
    bottom = all_obs[all_obs["quantile"] == 0]["forward_return_20d"]
    spread = top.mean() - bottom.mean()
    # Welch t-test, top vs bottom quantile
    from scipy import stats
    t_stat, p_val = stats.ttest_ind(top, bottom, equal_var=False)
    print(f"  Top-Bottom spread: {spread:+.4f}  t-stat={t_stat:+.2f}  p={p_val:.3f}  "
          f"n_top={len(top)} n_bottom={len(bottom)}")
    print()
