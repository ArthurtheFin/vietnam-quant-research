"""GD4 NV2 part 3 -- null test (2000 random portfolios/fold, seed=42) for the
composite (base_final_score) and the "watchlist toi gian" (v2_score gated by
final_watchlist's own strict_pass/fallback_eligible). Reuses run_portfolio_backtest
and the exact FOLDS/BASE config from scratch/score_v2_null_test.py.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest
from src.validation.trading_status import latest_trading_status

SEED = 42
N_ITER = 2000

panel = pd.read_parquet("data/output/watchlist_validation_panel.parquet")
panel["date"] = pd.to_datetime(panel["date"])
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
benchmark["date"] = pd.to_datetime(benchmark["date"])

sector_df = pd.read_csv("config/sector_map.csv")
sector_map = dict(zip(sector_df["symbol"], sector_df["sector"]))
active_symbols = set(latest_trading_status().loc[lambda d: d["status"] == "ACTIVE", "symbol"])

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

t0 = time.time()


def run_null_test(label: str, feature_source: pd.DataFrame, score_col: str, active_only: bool = True):
    feats = feature_source.copy()
    if active_only:
        feats = feats[feats["symbol"].isin(active_symbols)]
    meta_full = feats[["symbol", "date", score_col]].rename(columns={score_col: "meta_score"})
    # BUG FOUND during first run: the panel already carries its own stale
    # meta_score/trade_edge_score/setup_quality_score/risk_penalty_score
    # columns (from the meta_ranking as-of merge done for signal_score/
    # risk_score in watchlist_validation.py). run_portfolio_backtest's
    # internal merge(scores_today, features_today) then collided on
    # "meta_score", pandas auto-suffixed both copies to meta_score_x/_y,
    # and the function's own `score_col in merged.columns` check silently
    # found neither -- meaning it skipped the score-based sort entirely and
    # fell through to merge order (identical for every random draw). This
    # produced real_percentile_in_null=0.0 for every fold with a
    # zero-variance null distribution -- an artifact of the column
    # collision, not a real result. Confirmed by reproducing real vs random
    # runs and finding IDENTICAL selected symbols regardless of score.
    # Fix: drop the panel's own leftover meta_ranking columns before
    # handing features to run_portfolio_backtest.
    feats = feats.drop(columns=[c for c in ["meta_score", "trade_edge_score", "setup_quality_score", "risk_penalty_score"] if c in feats.columns])

    rng = np.random.default_rng(SEED)
    rows = []
    for test_start, test_end in FOLDS:
        test_start_ts, test_end_ts = pd.Timestamp(test_start), pd.Timestamp(test_end)
        test_features = feats[(feats["date"] >= test_start_ts) & (feats["date"] <= test_end_ts)].copy()
        if test_features.empty:
            rows.append({"fold": test_start[:4], "real_cagr": np.nan, "real_percentile_in_null": np.nan, "n_symbol_days": 0})
            continue

        real_test_meta = meta_full[(meta_full["date"] >= test_start_ts) & (meta_full["date"] <= test_end_ts)].copy()
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
                print(f"[{time.time()-t0:.0f}s] {label} fold {test_start[:4]}: {i+1}/{N_ITER}")
                sys.stdout.flush()

        percentile = float((null_cagrs < real_cagr).mean() * 100.0)
        pcts = np.percentile(null_cagrs, [5, 25, 50, 75, 95])
        rows.append({
            "fold": test_start[:4], "real_cagr": real_cagr,
            "null_p5": pcts[0], "null_p25": pcts[1], "null_p50": pcts[2], "null_p75": pcts[3], "null_p95": pcts[4],
            "real_percentile_in_null": percentile, "n_symbol_days": len(symbols_dates),
        })
        print(f"[{time.time()-t0:.0f}s] {label} fold {test_start[:4]} DONE: real_cagr={real_cagr:+.1%} percentile={percentile:.1f}")
        sys.stdout.flush()

    result = pd.DataFrame(rows)
    result.to_csv(f"data/output/watchlist_validation_null_{label}.csv", index=False)
    print(f"\n{'='*90}\nNULL TEST -- {label}\n{'='*90}")
    print(result.to_string(index=False))
    print(f"Average percentile: {result['real_percentile_in_null'].mean():.1f}")
    print(f"Any fold < 10th percentile: {(result['real_percentile_in_null'] < 10).any()}")
    return result


print("=== Composite (base_final_score), universe = trading_status ACTIVE ===")
run_null_test("composite", panel, "base_final_score", active_only=True)

print("\n=== Watchlist toi gian (v2_score, gated by strict_pass|fallback_eligible, ACTIVE) ===")
minimal_panel = panel[panel["minimal_eligible"].fillna(False)].copy()
run_null_test("minimal_watchlist", minimal_panel, "v2_score", active_only=True)

print(f"\n[{time.time()-t0:.0f}s] all done")
