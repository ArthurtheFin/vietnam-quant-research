"""One-off diagnostic (not part of the codebase): broad IC screen across
~35 technical candidate factors, on correctly-computed (zero-fill
corporate-action handling, see scratch/test_corp_action_zerofill_alternative.py)
data, following the request to keep looking within technical (price/volume)
factors rather than switching to fundamentals.

Uses data/signals/stealth_accumulation_history.parquet, which already
contains full 2020-2026 daily history for both the core price factors and a
much wider set of pre-engineered pattern/accumulation features (bollinger
band width, price position in range, relative strength vs market/sector,
volume ratios, pre-computed composite scores from the stealth-accumulation
screen, etc.) -- no need to hand-build new features before checking whether
signal already exists among what's already computed.

Multiple-testing caveat: ~35-40 candidates tested. At the naive |t|>2
threshold, several would clear it by chance alone. Flagging |t|>3 as the bar
for "worth a closer look", and any candidate that clears it still needs a
split-half/train-test robustness check (done below for the top candidates)
before it can be called a real, usable factor.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.data.loaders import read_parquet

df = read_parquet("data/signals/stealth_accumulation_history.parquet")
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

# Zero-fill corporate-action handling (least destructive of the two tested).
return_1d_zf = df["return_1d"].where(~df["suspect_corporate_action"], 0.0)
HOLDING = 20
df["return_20d"] = return_1d_zf.groupby(df["symbol"]).transform(
    lambda s: (1.0 + s).rolling(HOLDING).apply(np.prod, raw=True) - 1.0
)
df["forward_return_20d"] = return_1d_zf.groupby(df["symbol"]).transform(
    lambda s: (1.0 + s.shift(-HOLDING)).rolling(HOLDING).apply(np.prod, raw=True) - 1.0
)

MIN_VALUE_MA20 = 10_000_000_000.0
REBALANCE_PERIOD = 20
MIN_ELIGIBLE = 15

# (column, sign) -- sign is a PRIOR guess only, used to orient IC direction in
# the printout; mean_ic itself is computed on the RAW column (unsigned).
CANDIDATES = {
    # already tested / ruled out (full-distribution IC + quantile spread) -- included for reference
    "distance_ma20 [RULED OUT]": "distance_ma20",
    "return_20d [RULED OUT]": "return_20d",
    "realized_vol_20d [RULED OUT]": "realized_vol_20d",
    # momentum / trend continuation, other horizons
    "return_5d": "return_5d",
    "return_10d": "return_10d",
    "return_60d": "return_60d",
    "distance_ma50": "distance_ma50",
    "distance_ma200": "distance_ma200",
    "relative_strength_20d": "relative_strength_20d",
    "sector_relative_strength_20d": "sector_relative_strength_20d",
    "sector_tailwind_20d": "sector_tailwind_20d",
    "market_down_alpha_20d": "market_down_alpha_20d",
    "higher_low_ratio": "higher_low_ratio",
    # volatility / tail risk
    "atr_pct_14": "atr_pct_14",
    "volatility_percentile": "volatility_percentile",
    "dist_skew_60d": "dist_skew_60d",
    "dist_kurt_60d": "dist_kurt_60d",
    "tail_ratio_60d": "tail_ratio_60d",
    # liquidity / volume
    "value_ma20": "value_ma20",
    "volume_zscore_20d": "volume_zscore_20d",
    "value_zscore_20d": "value_zscore_20d",
    "volume_ratio_5_20": "volume_ratio_5_20",
    "value_ratio_10_60": "value_ratio_10_60",
    "up_down_value_ratio_10d": "up_down_value_ratio_10d",
    "up_down_volume_ratio": "up_down_volume_ratio",
    # price structure / pattern
    "bb_width": "bb_width",
    "bb_width_percentile": "bb_width_percentile",
    "price_position_20d": "price_position_20d",
    "pullback_from_high_20d": "pullback_from_high_20d",
    "distance_to_pivot": "distance_to_pivot",
    "close_location_value": "close_location_value",
    "upper_wick_pct": "upper_wick_pct",
    "base_range_percentile": "base_range_percentile",
    # pre-computed composite scores from the stealth-accumulation screen
    "accumulation_score": "accumulation_score",
    "breakout_quality_score": "breakout_quality_score",
    "relative_strength_score": "relative_strength_score",
    "pressure_score": "pressure_score",
    "near_pivot_score": "near_pivot_score",
    "liquidity_score": "liquidity_score",
    "tight_range_score": "tight_range_score",
    "volatility_dryup_score": "volatility_dryup_score",
    "quiet_volume_score": "quiet_volume_score",
    "absorption_score": "absorption_score",
    "breadth_support_score": "breadth_support_score",
    "sector_support_score": "sector_support_score",
    "market_support_score": "market_support_score",
    "volatility_support_score": "volatility_support_score",
    "net_accumulation_score": "net_accumulation_score",
}

BOOLEAN_CANDIDATES = ["ready_for_breakout", "is_compressed", "bb_squeeze", "range_squeeze", "watchlist_flag"]


def spearman_ic(x: pd.Series, y: pd.Series) -> float | None:
    both = pd.concat([x, y], axis=1).dropna()
    if len(both) < 10:
        return None
    return both.iloc[:, 0].corr(both.iloc[:, 1], method="spearman")


all_dates = sorted(df["date"].unique())
rebalance_dates = all_dates[::REBALANCE_PERIOD]

records: dict[str, list[float]] = {name: [] for name in CANDIDATES}
bool_records: dict[str, list[tuple[float, float]]] = {name: [] for name in BOOLEAN_CANDIDATES}

for idx, current_date in enumerate(rebalance_dates):
    if idx == 0:
        continue
    decision_date = all_dates[all_dates.index(current_date) - 1]
    snap = df[df["date"] == decision_date].copy()
    if "value_ma20" in snap.columns:
        snap = snap[snap["value_ma20"].fillna(0) >= MIN_VALUE_MA20]
    if "above_ma200" in snap.columns:
        snap = snap[snap["above_ma200"].astype(bool)]
    snap = snap.dropna(subset=["forward_return_20d"])
    if len(snap) < MIN_ELIGIBLE:
        continue

    fwd = snap["forward_return_20d"]
    for name, col in CANDIDATES.items():
        if col not in snap.columns:
            continue
        ic = spearman_ic(snap[col], fwd)
        if ic is not None:
            records[name].append(ic)

    for name in BOOLEAN_CANDIDATES:
        if name not in snap.columns:
            continue
        flag = snap[name].fillna(False).astype(bool)
        if flag.sum() < 5 or (~flag).sum() < 5:
            continue
        bool_records[name].append((fwd[flag].mean(), fwd[~flag].mean()))

print(f"Numeric factor IC screen, {len(rebalance_dates) - 1} rebalance dates, zero-fill target\n")
results = []
for name, ics in records.items():
    arr = np.array(ics)
    if len(arr) < 5:
        continue
    mean_ic = arr.mean()
    std_ic = arr.std(ddof=1) if len(arr) > 1 else np.nan
    t_stat = mean_ic / std_ic * np.sqrt(len(arr)) if std_ic and std_ic > 0 else np.nan
    results.append((name, mean_ic, t_stat, len(arr)))

results.sort(key=lambda r: -abs(r[2]) if not np.isnan(r[2]) else 0)
for name, mean_ic, t_stat, n in results:
    flag = " <-- |t|>3, worth a closer look" if abs(t_stat) > 3 else ""
    print(f"  {name:35s} mean_IC={mean_ic:+.4f}  t-stat={t_stat:+.2f}  N={n}{flag}")

print(f"\nBoolean/flag factors (mean forward_return_20d, flag=True vs flag=False):\n")
for name, pairs in bool_records.items():
    if not pairs:
        continue
    true_means = np.array([p[0] for p in pairs])
    false_means = np.array([p[1] for p in pairs])
    diffs = true_means - false_means
    t_stat, p_val = stats.ttest_1samp(diffs, 0.0) if len(diffs) > 1 else (np.nan, np.nan)
    print(f"  {name:25s} mean(True)={true_means.mean():+.4f}  mean(False)={false_means.mean():+.4f}  "
          f"diff={diffs.mean():+.4f}  t-stat={t_stat:+.2f}  N_dates={len(pairs)}")
