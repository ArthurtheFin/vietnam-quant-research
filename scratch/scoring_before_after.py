"""NV3 (SCORING_UPDATE_REPORT.md evidence): before/after comparison of the
src/alpha/scoring.py change (return_20d removed from momentum_score) on
data/full_history_v2. distance_ma20's threshold-loosening in
src/screening/final_watchlist.py is a gate change, not a scoring-formula
change, and isn't comparable via alpha_score top-N/backtest the same way --
covered qualitatively in the report instead.

Reuses the exact walk-forward machinery already in the codebase
(scratch/rolling_walk_forward.py's FOLDS + BASE kwargs + run_portfolio_backtest),
not a new backtest methodology. One run each, no tuning.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest

features_all = read_parquet("data/processed/stock_features.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
benchmark["date"] = pd.to_datetime(benchmark["date"])


def calculate_alpha_scores_OLD(stock_df: pd.DataFrame, benchmark_df: pd.DataFrame) -> pd.DataFrame:
    """Verbatim pre-edit copy of src.alpha.scoring.calculate_alpha_scores,
    kept here only for this one-off before/after comparison."""
    if stock_df.empty:
        return stock_df.copy()
    stocks = stock_df.sort_values(["symbol", "date"]).copy()
    if "volume_ma20" in stocks.columns:
        stocks["volume_ratio_20d"] = stocks["volume"] / stocks["volume_ma20"].replace(0, np.nan)
    else:
        stocks["volume_ratio_20d"] = 1.0
    if not benchmark_df.empty:
        bench = benchmark_df.sort_values("date").copy()
        bench_cols = ["date", "close", "return_20d", "return_60d"]
        available_bench = [c for c in bench_cols if c in bench.columns]
        bench = bench[available_bench].copy()
        rename_map = {}
        if "close" in bench.columns:
            rename_map["close"] = "bench_close"
        if "return_20d" in bench.columns:
            rename_map["return_20d"] = "bench_ret_20d"
        if "return_60d" in bench.columns:
            rename_map["return_60d"] = "bench_ret_60d"
        bench = bench.rename(columns=rename_map)
    else:
        bench = pd.DataFrame(columns=["date"])
    merged = pd.merge(stocks, bench, on="date", how="left")
    for r_col in ["return_20d", "return_60d"]:
        if r_col not in merged.columns:
            merged[r_col] = 0.0
    merged["rs_20d"] = (merged["return_20d"] - merged["bench_ret_20d"]) if "bench_ret_20d" in merged.columns else 0.0
    merged["rs_60d"] = (merged["return_60d"] - merged["bench_ret_60d"]) if "bench_ret_60d" in merged.columns else 0.0
    merged["rs_20d"] = merged["rs_20d"].fillna(0.0)
    merged["rs_60d"] = merged["rs_60d"].fillna(0.0)
    merged["market_regime"] = "unknown"

    def compute_ranks(group):
        r20 = group["return_20d"].rank(pct=True, na_option="keep") * 100.0
        r60 = group["return_60d"].rank(pct=True, na_option="keep") * 100.0
        group["momentum_score"] = ((r20.fillna(50.0) + r60.fillna(50.0)) / 2.0).clip(0.0, 100.0)
        rs20 = group["rs_20d"].rank(pct=True, na_option="keep") * 100.0
        rs60 = group["rs_60d"].rank(pct=True, na_option="keep") * 100.0
        group["rs_score"] = ((rs20.fillna(50.0) + rs60.fillna(50.0)) / 2.0).clip(0.0, 100.0)
        c_above_ma20 = (group["close"] > group.get("ma20", group["close"])).astype(float)
        c_above_ma50 = (group["close"] > group.get("ma50", group["close"])).astype(float)
        c_above_ma200 = (group["close"] > group.get("ma200", group["close"])).astype(float)
        group["trend_score"] = (c_above_ma20 * 34.0 + c_above_ma50 * 33.0 + c_above_ma200 * 33.0).clip(0.0, 100.0)
        group["volume_score"] = (group["volume_ratio_20d"].rank(pct=True, na_option="keep") * 100.0).fillna(50.0).clip(0.0, 100.0)
        vol_metric = group.get("realized_vol_20d", group.get("atr_pct_14", pd.Series(1.0, index=group.index)))
        group["volatility_score"] = ((1.0 - vol_metric.rank(pct=True, na_option="keep")) * 100.0).fillna(50.0).clip(0.0, 100.0)
        liq_metric = group.get("value_ma20", pd.Series(1.0, index=group.index))
        group["liquidity_score"] = (liq_metric.rank(pct=True, na_option="keep") * 100.0).fillna(50.0).clip(0.0, 100.0)
        group["alpha_score"] = (
            0.25 * group["momentum_score"] + 0.25 * group["rs_score"] + 0.20 * group["trend_score"]
            + 0.15 * group["volume_score"] + 0.10 * group["volatility_score"] + 0.05 * group["liquidity_score"]
        ).clip(0.0, 100.0)
        return group

    ranked_frames = [compute_ranks(group.copy()) for _, group in merged.groupby("date", sort=False)]
    return pd.concat(ranked_frames, ignore_index=True) if ranked_frames else merged.iloc[0:0].copy()


from src.alpha.scoring import calculate_alpha_scores as calculate_alpha_scores_NEW  # noqa: E402

print("Computing OLD alpha_score...")
old_scored = calculate_alpha_scores_OLD(features_all, benchmark)
print("Computing NEW alpha_score...")
new_scored = calculate_alpha_scores_NEW(features_all, benchmark)

# -----------------------------------------------------------------------
# Step A: top-20 at the 5 most recent dates, IN/OUT marking
# -----------------------------------------------------------------------
print("\n" + "=" * 80)
print("STEP A -- top-20 by alpha_score, last 5 dates, OLD vs NEW")
print("=" * 80)
last5 = sorted(new_scored["date"].unique())[-5:]
for d in last5:
    old_top20 = set(old_scored[old_scored["date"] == d].nlargest(20, "alpha_score")["symbol"])
    new_top20 = set(new_scored[new_scored["date"] == d].nlargest(20, "alpha_score")["symbol"])
    overlap = old_top20 & new_top20
    only_old = old_top20 - new_top20
    only_new = new_top20 - old_top20
    print(f"\n{d.date()}: overlap={len(overlap)}/20  OUT(old-only)={sorted(only_old)}  IN(new-only)={sorted(only_new)}")

# -----------------------------------------------------------------------
# Step B: turnover estimate across full history (rebalanced monthly, ~21d)
# -----------------------------------------------------------------------
print("\n" + "=" * 80)
print("STEP B -- turnover estimate (top-20 overlap), monthly rebalance dates, full history")
print("=" * 80)
all_dates = sorted(new_scored["date"].unique())
rebalance_dates = all_dates[::21]
overlaps = []
for d in rebalance_dates:
    old_top20 = set(old_scored[old_scored["date"] == d].nlargest(20, "alpha_score")["symbol"])
    new_top20 = set(new_scored[new_scored["date"] == d].nlargest(20, "alpha_score")["symbol"])
    if old_top20 and new_top20:
        overlaps.append(len(old_top20 & new_top20) / 20.0)
avg_overlap = np.mean(overlaps) if overlaps else np.nan
print(f"Avg top-20 overlap across {len(overlaps)} monthly rebalance dates: {avg_overlap:.1%}  "
      f"(=> avg turnover from this change alone: {1 - avg_overlap:.1%})")

# -----------------------------------------------------------------------
# Step C: walk-forward backtest, OLD vs NEW, same folds/costs as
# scratch/rolling_walk_forward.py (reused verbatim, not re-derived)
# -----------------------------------------------------------------------
print("\n" + "=" * 80)
print("STEP C -- walk-forward backtest, OLD vs NEW alpha_score (same folds/costs as "
      "scratch/rolling_walk_forward.py)")
print("=" * 80)

FOLDS = [
    ("2021-12-31", "2022-01-01", "2022-12-31"),
    ("2022-12-31", "2023-01-01", "2023-12-31"),
    ("2023-12-31", "2024-01-01", "2024-12-31"),
    ("2024-12-31", "2025-01-01", "2025-12-31"),
    ("2025-12-31", "2026-01-01", "2026-07-06"),
]
BASE = dict(
    rebalance_period=20,
    portfolio_size=5,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
)

results = {"OLD": [], "NEW": []}
for label, scored in [("OLD", old_scored), ("NEW", new_scored)]:
    meta = scored[["symbol", "date", "alpha_score"]].rename(columns={"alpha_score": "meta_score"})
    for train_end, test_start, test_end in FOLDS:
        test_start_ts, test_end_ts = pd.Timestamp(test_start), pd.Timestamp(test_end)
        test_features = features_all[(features_all["date"] >= test_start_ts) & (features_all["date"] <= test_end_ts)].copy()
        test_meta = meta[(meta["date"] >= test_start_ts) & (meta["date"] <= test_end_ts)].copy()
        try:
            r = run_portfolio_backtest(features=test_features, meta_ranking=test_meta, **BASE)
            m = r["metrics"]
            results[label].append({"fold": test_start[:4], "cagr": m["cagr"], "max_dd": m["max_drawdown"], "sharpe": m["sharpe_ratio"]})
        except Exception as exc:
            results[label].append({"fold": test_start[:4], "cagr": np.nan, "max_dd": np.nan, "sharpe": np.nan, "error": str(exc)})

print(f"{'Variant':8s} " + " ".join(f"{f[1][:4]:>9s}" for f in FOLDS) + f" {'AvgCAGR':>9s} {'MedCAGR':>9s} {'WinRate':>8s}")
for label, res in results.items():
    cagrs = [r["cagr"] for r in res]
    row = " ".join(f"{c:+9.1%}" if pd.notna(c) else f"{'ERR':>9s}" for c in cagrs)
    valid = [c for c in cagrs if pd.notna(c)]
    avg = np.mean(valid) if valid else np.nan
    med = np.median(valid) if valid else np.nan
    win_rate = np.mean([c > 0 for c in valid]) if valid else np.nan
    print(f"{label:8s} {row} {avg:+9.1%} {med:+9.1%} {win_rate:>8.0%}")

print("\nPer-fold detail:")
for label, res in results.items():
    print(f"  {label}:")
    for r in res:
        if "error" in r:
            print(f"    {r['fold']}: ERROR {r['error']}")
        else:
            print(f"    {r['fold']}: CAGR={r['cagr']:+.2%}  MaxDD={r['max_dd']:.2%}  Sharpe={r['sharpe']:+.2f}")

print("\ndone")
