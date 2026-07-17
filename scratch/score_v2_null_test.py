"""docs/reports/scoring/docs/reports/scoring/SCORE_V2_DESIGN.md confirmation run, null-test leg: v2's percentile
within 2,000 random portfolios per fold, under the currently-deployed
config (portfolio_size=10, sector cap=2). Seed=42, one continuous RNG
stream, same convention as scratch/concentration_null_test.py.
"""
from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest

SEED = 42
N_ITER = 2000

features_all = read_parquet("data/processed/stock_features.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
benchmark["date"] = pd.to_datetime(benchmark["date"])

sector_df = pd.read_csv("config/sector_map.csv")
sector_map = dict(zip(sector_df["symbol"], sector_df["sector"]))

# v2 score = 0.70 * inverted-rank(realized_vol_20d) + 0.30 * inverted-rank(value_ma20)
# per docs/reports/scoring/docs/reports/scoring/SCORE_V2_DESIGN.md, computed cross-sectionally per day.
def compute_v2_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    def _score_day(g):
        vol_score = (1.0 - g["realized_vol_20d"].rank(pct=True, na_option="keep")) * 100.0
        liq_score = (1.0 - g["value_ma20"].rank(pct=True, na_option="keep")) * 100.0
        g["v2_score"] = 0.70 * vol_score.fillna(50.0) + 0.30 * liq_score.fillna(50.0)
        return g

    return out.groupby("date", group_keys=False).apply(_score_day)


print("Computing v2_score...")
scored_v2 = compute_v2_score(features_all)
v2_meta = scored_v2[["symbol", "date", "v2_score"]].rename(columns={"v2_score": "meta_score"})

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

rng = np.random.default_rng(SEED)
t0 = time.time()
rows = []
for test_start, test_end in FOLDS:
    test_start_ts, test_end_ts = pd.Timestamp(test_start), pd.Timestamp(test_end)
    test_features = features_all[(features_all["date"] >= test_start_ts) & (features_all["date"] <= test_end_ts)].copy()

    real_test_meta = v2_meta[(v2_meta["date"] >= test_start_ts) & (v2_meta["date"] <= test_end_ts)].copy()
    real_r = run_portfolio_backtest(features=test_features, meta_ranking=real_test_meta, **BASE)
    real_cagr = real_r["metrics"]["cagr"]

    symbols_dates = test_features[["symbol", "date"]].drop_duplicates().reset_index(drop=True)
    null_cagrs = np.empty(N_ITER)
    for i in range(N_ITER):
        rand_scores = rng.random(len(symbols_dates))
        rand_meta = symbols_dates.copy()
        rand_meta["meta_score"] = rand_scores
        r = run_portfolio_backtest(features=test_features, meta_ranking=rand_meta, **BASE)
        null_cagrs[i] = r["metrics"]["cagr"]
        if (i + 1) % 500 == 0:
            print(f"[{time.time()-t0:.0f}s] fold {test_start[:4]}: {i+1}/{N_ITER} done")
            sys.stdout.flush()

    percentile = float((null_cagrs < real_cagr).mean() * 100.0)
    pcts = np.percentile(null_cagrs, [1, 5, 25, 50, 75, 95, 99])
    rows.append({
        "fold": test_start[:4], "real_cagr": real_cagr,
        "null_p1": pcts[0], "null_p5": pcts[1], "null_p25": pcts[2], "null_p50": pcts[3],
        "null_p75": pcts[4], "null_p95": pcts[5], "null_p99": pcts[6],
        "real_percentile_in_null": percentile,
    })
    print(f"[{time.time()-t0:.0f}s] fold {test_start[:4]} DONE: real_cagr={real_cagr:+.1%} percentile={percentile:.1f}\n")
    sys.stdout.flush()

result = pd.DataFrame(rows)
result.to_csv("data/full_history_v2/score_v2_null_test.csv", index=False)
print("\n" + "=" * 90)
print(f"V2 NULL TEST SUMMARY (seed={SEED}, N_ITER={N_ITER}, config: size=10, sector_cap=2)")
print("=" * 90)
print(result.to_string(index=False, formatters={c: "{:+.1%}".format for c in
      ["real_cagr", "null_p1", "null_p5", "null_p25", "null_p50", "null_p75", "null_p95", "null_p99"]} | {"real_percentile_in_null": "{:.1f}".format}))
print(f"\nAverage v2 percentile across 5 folds: {result['real_percentile_in_null'].mean():.1f}")
print(f"Any fold < 5th percentile: {(result['real_percentile_in_null'] < 5).any()}")
print("\ndone")
