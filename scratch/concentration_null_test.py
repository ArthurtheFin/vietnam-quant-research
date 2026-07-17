"""docs/reports/scoring/CONCENTRATION_ANALYSIS_REPORT.md NV1: null test. For each of the 5
walk-forward folds, generate N_ITER random 5-stock portfolios drawn from
the exact same eligible universe the real system uses at each rebalance
(same rebalance schedule, same transaction costs, same equal-weight
allocation) via run_portfolio_backtest itself -- a uniform-random score
column makes the engine's own top-N-by-score selection equivalent to a
uniform random N-subset of the eligible universe, so no selection logic
is reimplemented here.

Fixed seed=42 (same convention as scratch/pilot_backfill.py earlier this
session), single RNG stream continued across all 2000*5 iterations (not
reset per iteration) for reproducibility.
"""
from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest
from src.alpha.scoring import calculate_alpha_scores
from src.validation.metrics import calculate_cagr, calculate_max_drawdown

SEED = 42
N_ITER = 2000

features_all = read_parquet("data/processed/stock_features.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
benchmark["date"] = pd.to_datetime(benchmark["date"])

FOLDS = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-07-06"),
]
BASE = dict(
    rebalance_period=20,
    portfolio_size=5,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
    benchmark_features=benchmark,
)

print("Computing deployed (real) alpha_score...")
scored = calculate_alpha_scores(features_all, benchmark)
real_meta = scored[["symbol", "date", "alpha_score"]].rename(columns={"alpha_score": "meta_score"})

rng = np.random.default_rng(SEED)

t0 = time.time()
rows = []
for fold_idx, (test_start, test_end) in enumerate(FOLDS):
    test_start_ts, test_end_ts = pd.Timestamp(test_start), pd.Timestamp(test_end)
    test_features = features_all[(features_all["date"] >= test_start_ts) & (features_all["date"] <= test_end_ts)].copy()

    # real (deployed) score result for this fold
    real_test_meta = real_meta[(real_meta["date"] >= test_start_ts) & (real_meta["date"] <= test_end_ts)].copy()
    real_r = run_portfolio_backtest(features=test_features, meta_ranking=real_test_meta, **BASE)
    real_cagr = real_r["metrics"]["cagr"]
    real_maxdd = real_r["metrics"]["max_drawdown"]

    # null distribution: N_ITER random-score portfolios, same eligible universe
    symbols_dates = test_features[["symbol", "date"]].drop_duplicates().reset_index(drop=True)
    null_cagrs = np.empty(N_ITER)
    for i in range(N_ITER):
        rand_scores = rng.random(len(symbols_dates))
        rand_meta = symbols_dates.copy()
        rand_meta["meta_score"] = rand_scores
        r = run_portfolio_backtest(features=test_features, meta_ranking=rand_meta, **BASE)
        null_cagrs[i] = r["metrics"]["cagr"]
        if (i + 1) % 500 == 0:
            print(f"[{time.time()-t0:.0f}s] fold {test_start[:4]}: {i+1}/{N_ITER} random portfolios done")

    percentile = float((null_cagrs < real_cagr).mean() * 100.0)
    pcts = np.percentile(null_cagrs, [1, 5, 25, 50, 75, 95, 99])
    rows.append({
        "fold": test_start[:4], "real_cagr": real_cagr, "real_maxdd": real_maxdd,
        "null_p1": pcts[0], "null_p5": pcts[1], "null_p25": pcts[2], "null_p50": pcts[3],
        "null_p75": pcts[4], "null_p95": pcts[5], "null_p99": pcts[6],
        "real_percentile_in_null": percentile,
    })
    print(f"[{time.time()-t0:.0f}s] fold {test_start[:4]} DONE: real_cagr={real_cagr:+.1%} "
          f"percentile={percentile:.1f}  null_median={pcts[3]:+.1%}\n")
    sys.stdout.flush()

result = pd.DataFrame(rows)
result.to_csv("data/full_history_v2/concentration_null_test.csv", index=False)

pd.set_option("display.width", 200)
print("\n" + "=" * 100)
print(f"NULL TEST SUMMARY (seed={SEED}, N_ITER={N_ITER} per fold)")
print("=" * 100)
print(result.to_string(index=False, formatters={
    c: "{:+.1%}".format for c in ["real_cagr", "real_maxdd", "null_p1", "null_p5", "null_p25", "null_p50", "null_p75", "null_p95", "null_p99"]
} | {"real_percentile_in_null": "{:.1f}".format}))

print(f"\nAverage real-portfolio percentile across 5 folds: {result['real_percentile_in_null'].mean():.1f}")

print("\nPre-registered interpretation per fold:")
for _, row in result.iterrows():
    p = row["real_percentile_in_null"]
    is_disaster = row["real_cagr"] < -0.30
    if is_disaster and p < 5:
        verdict = "percentile<5 in a disaster fold -> active signal actively HURT this period"
    elif 5 <= p < 25:
        verdict = "percentile 5-25 -> mainly concentration variance, not active harm"
    elif p > 50 and not is_disaster:
        verdict = "percentile>50 in a good fold -> signal added value here"
    elif is_disaster and p < 25:
        verdict = "signal has value on average but structure amplifies the tail here"
    else:
        verdict = "(see raw percentile, doesn't match a pre-registered bucket cleanly)"
    print(f"  {row['fold']}: percentile={p:.1f}  real_cagr={row['real_cagr']:+.1%}  disaster={is_disaster}  -> {verdict}")

print(f"\n[{time.time()-t0:.0f}s] done")
