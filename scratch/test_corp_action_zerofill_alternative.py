"""One-off diagnostic (not part of the codebase): does a LESS destructive
corporate-action handling recover the IC/backtest signal that collapsed
after regenerating stock_features.parquet with the current G4 fix?

Context (see docs/reports/codebase_audit/docs/reports/codebase_audit/PIPELINE_AUDIT_REPORT.md): G4 NaNs out return_1d on any day
flagged as a suspected unadjusted corporate action. Because return_20d /
forward_return_20d are 20-day ROLLING PRODUCTS of return_1d, a single NaN'd
day poisons the entire 20-day window around it -- 1,545 flagged days (0.86%
of all rows) turned 28,643 return_20d rows and 27,611 forward_return_20d
rows (~15-16% of the dataset) into NaN, shrinking and changing the
composition of every IC/backtest sample computed since.

This tests an alternative: instead of NaN, treat the flagged day's
contribution to the rolling product as a NEUTRAL 0% return (i.e. that one
day doesn't count, but the other 19 days in the window are NOT thrown away).
This still refuses to treat the corporate-action price jump as a real
trading return (same principle G4 was fixing), but doesn't destroy 15-16%
of the dataset to do it.

If this recovers meaningful IC/backtest signal -> the "no alpha" finding was
partly an artifact of an overly destructive cleaning step, and full
re-validation on the improved computation is worth doing.
If IC/backtest signal stays weak even with this less destructive handling
-> the weak-signal finding is more robust, not a data-cleaning artifact.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.reversal_quality_score import compute_factor_ic, derive_factor_weights
from src.backtest import run_portfolio_backtest
from src.data.loaders import read_parquet

features = read_parquet("data/processed/stock_features.parquet")
features["date"] = pd.to_datetime(features["date"])
features = features.sort_values(["symbol", "date"]).reset_index(drop=True)

print(f"Loaded {len(features)} rows, {features['symbol'].nunique()} symbols, "
      f"{features['suspect_corporate_action'].sum()} flagged corporate-action days")

# --- Recompute return_20d / forward_return_20d with a zero-fill instead of NaN ---
return_1d_zerofilled = features["return_1d"].where(~features["suspect_corporate_action"], 0.0)

HOLDING = 20
features["return_20d_zerofill"] = return_1d_zerofilled.groupby(features["symbol"]).transform(
    lambda s: (1.0 + s).rolling(HOLDING).apply(np.prod, raw=True) - 1.0
)
features["forward_return_20d_zerofill"] = return_1d_zerofilled.groupby(features["symbol"]).transform(
    lambda s: (1.0 + s.shift(-HOLDING)).rolling(HOLDING).apply(np.prod, raw=True) - 1.0
)

print(f"\nreturn_20d NaN count: current(NaN-window)={features['return_20d'].isna().sum()}, "
      f"zerofill={features['return_20d_zerofill'].isna().sum()}")
print(f"forward_return_20d NaN count: current(NaN-window)={features['forward_return_20d'].isna().sum()}, "
      f"zerofill={features['forward_return_20d_zerofill'].isna().sum()}")

# --- IC comparison: current (NaN-window) vs zero-fill, both on the SAME regenerated file ---
print("\n--- Full-history IC, current NaN-window approach (already measured) ---")
mean_ic_current = compute_factor_ic(features)
print(mean_ic_current)

print("\n--- Full-history IC, zero-fill alternative ---")
features_alt = features.rename(columns={"return_20d": "return_20d_ORIG", "forward_return_20d": "forward_return_20d_ORIG"})
features_alt = features_alt.rename(columns={"return_20d_zerofill": "return_20d", "forward_return_20d_zerofill": "forward_return_20d"})
mean_ic_zerofill = compute_factor_ic(features_alt)
print(mean_ic_zerofill)

weights_zf, signs_zf = derive_factor_weights(mean_ic_zerofill)
print("\nzero-fill derived weights/signs:", weights_zf, signs_zf)

# --- Rolling 5-fold backtest with the zero-fill target/factor ---
FACTORS = ["distance_ma20", "return_20d", "realized_vol_20d"]
REBALANCE_PERIOD = 20

FOLDS = [
    ("2021-12-31", "2022-01-01", "2022-12-31"),
    ("2022-12-31", "2023-01-01", "2023-12-31"),
    ("2023-12-31", "2024-01-01", "2024-12-31"),
    ("2024-12-31", "2025-01-01", "2025-12-31"),
    ("2025-12-31", "2026-01-01", "2026-07-06"),
]

BASE = dict(
    rebalance_period=REBALANCE_PERIOD,
    portfolio_size=5,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
)


def build_score(features_df: pd.DataFrame, weights: dict, signs: dict) -> pd.DataFrame:
    df = features_df[["symbol", "date"] + FACTORS].copy()
    grouped = df.groupby("date")
    total = pd.Series(0.0, index=df.index)
    for name in FACTORS:
        rank = grouped[name].transform(lambda s: (s * signs[name]).rank(pct=True))
        total = total + weights[name] * rank.fillna(0.5)
    df["meta_score"] = total * 100.0
    return df[["symbol", "date", "meta_score"]]


print("\n--- Rolling 5-fold backtest, zero-fill alternative (weights/signs derived per-fold from TRAIN, same convention as rolling_walk_forward.py) ---")
fold_cagrs = []
for train_end, test_start, test_end in FOLDS:
    train_end_ts, test_start_ts, test_end_ts = pd.Timestamp(train_end), pd.Timestamp(test_start), pd.Timestamp(test_end)
    train_features = features_alt[features_alt["date"] <= train_end_ts]
    test_features = features_alt[(features_alt["date"] >= test_start_ts) & (features_alt["date"] <= test_end_ts)].copy()

    train_ic = compute_factor_ic(train_features)
    weights, signs = derive_factor_weights(train_ic)
    test_score = build_score(test_features, weights, signs)

    try:
        r = run_portfolio_backtest(features=test_features, meta_ranking=test_score, **BASE)
        m = r["metrics"]
        fold_cagrs.append(m["cagr"])
        print(f"  {test_start[:4]}: CAGR={m['cagr']:+.2%}  MaxDD={m['max_drawdown']:.2%}  Sharpe={m['sharpe_ratio']:+.2f}  "
              f"(train weights: {weights})")
    except Exception as exc:
        print(f"  {test_start[:4]}: ERROR {exc}")

if fold_cagrs:
    arr = np.array(fold_cagrs)
    print(f"\n  AvgCAGR={arr.mean():+.2%}  MedCAGR={np.median(arr):+.2%}  WinRate={(arr > 0).mean():.0%}")

# --- Shuffle test on the zero-fill full-history default-weight score, for the same bar used throughout ---
print("\n--- Shuffle test: zero-fill DEFAULT-weight score (0.39/0.32/0.29) vs shuffled, full history ---")
DEFAULT_WEIGHTS = {"distance_ma20": 0.39, "return_20d": 0.32, "realized_vol_20d": 0.29}
DEFAULT_SIGNS = {"distance_ma20": -1, "return_20d": -1, "realized_vol_20d": -1}
full_score = build_score(features_alt, DEFAULT_WEIGHTS, DEFAULT_SIGNS)
r_real = run_portfolio_backtest(features=features_alt, meta_ranking=full_score, **BASE)
print(f"  Real (default weights):  CAGR={r_real['metrics']['cagr']:+.2%}  Sharpe={r_real['metrics']['sharpe_ratio']:+.2f}")

shuffle_cagrs = []
for seed in range(10):
    rng = np.random.default_rng(seed)
    shuf = full_score.copy()
    shuf["meta_score"] = shuf.groupby("date")["meta_score"].transform(lambda s: rng.permutation(s.values))
    r = run_portfolio_backtest(features=features_alt, meta_ranking=shuf, **BASE)
    shuffle_cagrs.append(r["metrics"]["cagr"])
shuffle_arr = np.array(shuffle_cagrs)
print(f"  Shuffled (avg of 10 seeds): CAGR={shuffle_arr.mean():+.2%}  std={shuffle_arr.std(ddof=1):.2%}  "
      f"pct_seeds_beaten_by_real={(shuffle_arr < r_real['metrics']['cagr']).mean():.0%}")
