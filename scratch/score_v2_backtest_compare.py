"""docs/reports/scoring/SCORE_V2_DESIGN.md confirmation run, walk-forward leg: v2 vs. old
composite (deployed alpha_score) vs. minimal score (realized_vol_20d
alone), identical currently-deployed config (size=10, sector cap=2),
same 5 folds. One run each, no tuning.
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


def _score_day_v2(g):
    vol_score = (1.0 - g["realized_vol_20d"].rank(pct=True, na_option="keep")) * 100.0
    liq_score = (1.0 - g["value_ma20"].rank(pct=True, na_option="keep")) * 100.0
    g["v2_score"] = 0.70 * vol_score.fillna(50.0) + 0.30 * liq_score.fillna(50.0)
    return g


def _score_day_minimal(g):
    g["minimal_score"] = (1.0 - g["realized_vol_20d"].rank(pct=True, na_option="keep")) * 100.0
    return g


print("Computing v2_score, minimal_score, old composite alpha_score...")
scored_v2 = features_all.groupby("date", group_keys=False).apply(_score_day_v2, include_groups=True)
scored_min = features_all.groupby("date", group_keys=False).apply(_score_day_minimal, include_groups=True)
scored_old = calculate_alpha_scores(features_all, benchmark)

metas = {
    "v2 (vol70/liq30)": scored_v2[["symbol", "date", "v2_score"]].rename(columns={"v2_score": "meta_score"}),
    "old composite": scored_old[["symbol", "date", "alpha_score"]].rename(columns={"alpha_score": "meta_score"}),
    "minimal (vol100)": scored_min[["symbol", "date", "minimal_score"]].rename(columns={"minimal_score": "meta_score"}),
}

FOLDS = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-07-06"),
]
BASE = dict(
    rebalance_period=20,
    portfolio_size=10,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
    benchmark_features=benchmark,
    max_per_sector=2,
    sector_map=sector_map,
)

rows = []
for variant_name, meta in metas.items():
    for test_start, test_end in FOLDS:
        test_start_ts, test_end_ts = pd.Timestamp(test_start), pd.Timestamp(test_end)
        test_features = features_all[(features_all["date"] >= test_start_ts) & (features_all["date"] <= test_end_ts)].copy()
        test_meta = meta[(meta["date"] >= test_start_ts) & (meta["date"] <= test_end_ts)].copy()
        r = run_portfolio_backtest(features=test_features, meta_ranking=test_meta, **BASE)
        m = r["metrics"]
        rows.append({"variant": variant_name, "fold": test_start[:4], "cagr": m["cagr"], "max_dd": m["max_drawdown"]})
    print(f"{variant_name} done")

detail = pd.DataFrame(rows)
detail.to_csv("data/full_history_v2/score_v2_backtest_detail.csv", index=False)

summary = detail.groupby("variant").agg(
    mean_cagr=("cagr", "mean"), median_cagr=("cagr", "median"),
    worst_fold=("cagr", "min"), avg_max_dd=("max_dd", "mean"),
).reindex(list(metas.keys()))

pd.set_option("display.width", 160)
print("\n" + "=" * 90)
print("WALK-FORWARD COMPARISON -- v2 vs old composite vs minimal score (size=10, sector cap=2)")
print("=" * 90)
print(detail.pivot(index="fold", columns="variant", values="cagr").to_string(formatters={c: "{:+.1%}".format for c in metas}))
print()
print(summary.to_string(formatters={"mean_cagr": "{:+.1%}".format, "median_cagr": "{:+.1%}".format,
      "worst_fold": "{:+.1%}".format, "avg_max_dd": "{:.1%}".format}))
print("\ndone")
