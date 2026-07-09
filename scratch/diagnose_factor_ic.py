"""Phase B step 2 (one-off diagnostic, not part of the codebase): proper
Information Coefficient (IC) study per candidate factor.

CORRECTION to the earlier shuffle test: meta_ranking.parquet only covers 16
dates clustered in 2025-2026 (checked directly), while the backtest rebalances
every 20 trading days across 2020-2026. For ~99% of rebalance dates,
run_portfolio_backtest's ranking_indexed.loc[decision_date] raises KeyError
and falls back to a DYNAMIC score computed straight from stock_features:
    meta_score_fallback = 0.4*momentum_rank(return_20d,return_60d)
                        + 0.4*trend_score(above_ma50,above_ma200)
                        + 0.2*liquidity_rank(value_ma20)
So shuffling meta_ranking["meta_score"] barely touched anything -- it mostly
proved that column is unused in this backtest span, NOT that scoring has zero
alpha in general. This script tests the factors that actually drove the
result: IC (Spearman rank correlation with forward_return_20d) computed at
every rebalance date, among symbols passing the same eligibility filters used
by the backtest (liquidity + above_ma200), same lookback direction as the
backtest (decision made on prior-day data, matching D1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet

features = read_parquet("data/processed/stock_features.parquet")
features = features.sort_values(["symbol", "date"]).reset_index(drop=True)
features["date"] = pd.to_datetime(features["date"])

MIN_VALUE_MA20 = 10_000_000_000.0
REBALANCE_PERIOD = 20

all_dates = sorted(features["date"].unique())
rebalance_dates = all_dates[::REBALANCE_PERIOD]

FACTORS = {
    "return_20d (momentum 20d)": ("return_20d", 1),
    "return_60d (momentum 60d)": ("return_60d", 1),
    "return_5d (short momentum)": ("return_5d", 1),
    "value_ma20 (liquidity)": ("value_ma20", 1),
    "atr_pct_14 (volatility, lower=better)": ("atr_pct_14", -1),
    "volume_zscore_20d (volume confirm)": ("volume_zscore_20d", 1),
    "distance_ma20 (extension, lower=better)": ("distance_ma20", -1),
    "realized_vol_20d (vol, lower=better)": ("realized_vol_20d", -1),
}


def spearman_ic(x: pd.Series, y: pd.Series) -> float | None:
    both = pd.concat([x, y], axis=1).dropna()
    if len(both) < 10:
        return None
    return both.iloc[:, 0].corr(both.iloc[:, 1], method="spearman")


records = {name: [] for name in FACTORS}
records["composite_fallback (0.4*mom + 0.4*trend + 0.2*liq)"] = []
dates_used = []

for idx, current_date in enumerate(rebalance_dates):
    if idx == 0:
        continue
    decision_date = all_dates[all_dates.index(current_date) - 1]
    snap = features[features["date"] == decision_date].set_index("symbol")
    if snap.empty or "forward_return_20d" not in snap.columns:
        continue

    # Same eligibility filter as the backtest (liquidity + above_ma200), so IC
    # reflects the actual investable universe, not the full raw market.
    eligible = snap.copy()
    if "value_ma20" in eligible.columns:
        eligible = eligible[eligible["value_ma20"].fillna(0) >= MIN_VALUE_MA20]
    if "above_ma200" in eligible.columns:
        eligible = eligible[eligible["above_ma200"].astype(bool)]
    if len(eligible) < 15:
        continue

    fwd = eligible["forward_return_20d"]
    any_ic = False
    for name, (col, sign) in FACTORS.items():
        if col not in eligible.columns:
            continue
        ic = spearman_ic(eligible[col] * sign, fwd)
        if ic is not None:
            records[name].append(ic)
            any_ic = True

    # Reconstruct the exact fallback composite score used by run_portfolio_backtest
    ret20 = pd.to_numeric(eligible.get("return_20d"), errors="coerce").fillna(0.0)
    ret60 = pd.to_numeric(eligible.get("return_60d"), errors="coerce").fillna(0.0)
    mom_rank = (ret20.rank(pct=True) + ret60.rank(pct=True)) / 2.0
    val20 = pd.to_numeric(eligible.get("value_ma20"), errors="coerce").fillna(0.0)
    liq_rank = val20.rank(pct=True)
    above50 = eligible.get("above_ma50", pd.Series(True, index=eligible.index)).astype(float)
    above200 = eligible.get("above_ma200", pd.Series(True, index=eligible.index)).astype(float)
    trend_score = (above50 + above200) / 2.0
    composite = mom_rank * 0.4 + trend_score * 0.4 + liq_rank * 0.2
    ic_composite = spearman_ic(composite, fwd)
    if ic_composite is not None:
        records["composite_fallback (0.4*mom + 0.4*trend + 0.2*liq)"].append(ic_composite)

    if any_ic:
        dates_used.append(current_date)

print(f"Rebalance dates used: {len(dates_used)}")
print()
print(f"{'Factor':45s} {'Mean IC':>10s} {'Std':>8s} {'t-stat':>8s} {'N':>5s}")
print("-" * 80)
for name, values in records.items():
    if not values:
        print(f"{name:45s} {'(no data)':>10s}")
        continue
    arr = np.array(values)
    mean_ic = arr.mean()
    std_ic = arr.std(ddof=1) if len(arr) > 1 else np.nan
    t_stat = mean_ic / std_ic * np.sqrt(len(arr)) if std_ic and std_ic > 0 else np.nan
    print(f"{name:45s} {mean_ic:>+10.4f} {std_ic:>8.4f} {t_stat:>+8.2f} {len(arr):>5d}")

print()
print("Rule of thumb: |mean IC| > 0.02-0.03 with |t-stat| > 2 is considered a")
print("real (if modest) signal in equity factor research. IC ~0 / |t| < 2 means")
print("no demonstrated predictive power at this horizon/universe.")
