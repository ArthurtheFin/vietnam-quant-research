"""docs/reports/scoring/docs/reports/scoring/CONCENTRATION_ANALYSIS_REPORT.md NV2: portfolio-construction sensitivity.
One run per configuration, no tuning, no picking the prettiest result.
Same folds/costs as scratch/fold_autopsy.py / scratch/scoring_before_after.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest
from src.alpha.scoring import calculate_alpha_scores

features_all = read_parquet("data/processed/stock_features.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
benchmark["date"] = pd.to_datetime(benchmark["date"])

sector_df = pd.read_csv("config/sector_map.csv")
sector_map = dict(zip(sector_df["symbol"], sector_df["sector"]))
print(f"Sector map coverage: {len(sector_map)} symbols, "
      f"{sector_df['sector'].nunique()} distinct sectors -- available, sector-cap variant will run.")

scored = calculate_alpha_scores(features_all, benchmark)
meta = scored[["symbol", "date", "alpha_score"]].rename(columns={"alpha_score": "meta_score"})

FOLDS = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-07-06"),
]
BASE = dict(
    rebalance_period=20,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
    benchmark_features=benchmark,
)

CONFIGS = {
    "size=5 (current)": {"portfolio_size": 5},
    "size=10": {"portfolio_size": 10},
    "size=20": {"portfolio_size": 20},
    "size=10 + sector cap 2": {"portfolio_size": 10, "max_per_sector": 2, "sector_map": sector_map},
}

rows = []
for config_name, extra_kwargs in CONFIGS.items():
    fold_cagrs, fold_maxdds, fold_turnovers = [], [], []
    for test_start, test_end in FOLDS:
        test_start_ts, test_end_ts = pd.Timestamp(test_start), pd.Timestamp(test_end)
        test_features = features_all[(features_all["date"] >= test_start_ts) & (features_all["date"] <= test_end_ts)].copy()
        test_meta = meta[(meta["date"] >= test_start_ts) & (meta["date"] <= test_end_ts)].copy()
        kwargs = dict(BASE)
        kwargs.update(extra_kwargs)
        r = run_portfolio_backtest(features=test_features, meta_ranking=test_meta, **kwargs)
        m = r["metrics"]
        trades = r["trades_log"]
        total_traded = trades["size_amount"].sum() if not trades.empty else 0.0
        n_rebal = trades["date"].nunique() if not trades.empty else 0
        turnover = (total_traded / n_rebal / BASE["initial_nav"]) if n_rebal else np.nan
        fold_cagrs.append(m["cagr"])
        fold_maxdds.append(m["max_drawdown"])
        fold_turnovers.append(turnover)
        rows.append({
            "config": config_name, "fold": test_start[:4], "cagr": m["cagr"],
            "max_dd": m["max_drawdown"], "turnover_pct_per_rebal": turnover,
        })
    print(f"{config_name}: fold CAGRs = {[f'{c:+.1%}' for c in fold_cagrs]}")

detail = pd.DataFrame(rows)
detail.to_csv("data/full_history_v2/concentration_size_sensitivity_detail.csv", index=False)

summary = detail.groupby("config").agg(
    mean_cagr=("cagr", "mean"), median_cagr=("cagr", "median"),
    worst_fold_cagr=("cagr", "min"), avg_max_dd=("max_dd", "mean"),
    avg_turnover=("turnover_pct_per_rebal", "mean"),
).reindex(list(CONFIGS.keys()))

pd.set_option("display.width", 160)
print("\n" + "=" * 100)
print("NV2 SUMMARY -- config x {mean CAGR, median CAGR, worst fold, avg max DD, avg turnover}")
print("=" * 100)
print(summary.to_string(formatters={
    "mean_cagr": "{:+.1%}".format, "median_cagr": "{:+.1%}".format,
    "worst_fold_cagr": "{:+.1%}".format, "avg_max_dd": "{:.1%}".format,
    "avg_turnover": "{:.1%}".format,
}))

print("\nTheoretical expectation to check against (more names -> shallower worst "
      "fold, mean/median converge): "
      f"worst_fold_cagr size5={summary.loc['size=5 (current)','worst_fold_cagr']:+.1%} "
      f"-> size10={summary.loc['size=10','worst_fold_cagr']:+.1%} "
      f"-> size20={summary.loc['size=20','worst_fold_cagr']:+.1%}")
gap5 = summary.loc["size=5 (current)", "mean_cagr"] - summary.loc["size=5 (current)", "median_cagr"]
gap20 = summary.loc["size=20", "mean_cagr"] - summary.loc["size=20", "median_cagr"]
print(f"mean-median gap: size5={gap5:+.1%} -> size20={gap20:+.1%} "
      f"({'narrows as expected' if abs(gap20) < abs(gap5) else 'does NOT narrow -- variance is not concentration-driven'})")

print("\ndone")
