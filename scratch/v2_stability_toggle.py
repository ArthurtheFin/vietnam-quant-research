"""GD5 NV1 diagnostic (measurement-tool check, NOT a signal test -- see
V2_STABILITY_NOTE.md): isolate which of the two GD4-added filters
(trading_status==ACTIVE prefilter vs final_watchlist's own
strict_pass|fallback_eligible "minimal_eligible" gate) drives the
71.0 (SCORE_V2_REPORT.md) -> 52.8 (GD4 minimal_watchlist) percentile drop,
now that scratch/score_v2_null_test.py rerun on current data ruled out data
vintage (still 71.0 on 2026-07-15 data with the original config).

One toggle, one run: ACTIVE-only prefilter, v2_score, NO minimal_eligible
gate. By elimination against the two known points (71.0 with neither
filter, 52.8 with both), this run's percentile tells us whether ACTIVE
alone explains the drop or whether minimal_eligible is the dominant factor.
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
    ("2022-01-01", "2022-12-31"), ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-07-06"),
]
BASE = dict(
    rebalance_period=20, portfolio_size=10, allocation_method="equal_weight",
    transaction_cost_pct=0.0015, initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000, require_above_ma200=True,
    benchmark_features=benchmark, max_per_sector=2, sector_map=sector_map,
)

feats = panel[panel["symbol"].isin(active_symbols)].copy()
feats = feats.drop(columns=[c for c in ["meta_score", "trade_edge_score", "setup_quality_score", "risk_penalty_score"] if c in feats.columns])
meta_full = feats[["symbol", "date", "v2_score"]].rename(columns={"v2_score": "meta_score"})

t0 = time.time()
rows = []
for test_start, test_end in FOLDS:
    ts, te = pd.Timestamp(test_start), pd.Timestamp(test_end)
    test_features = feats[(feats["date"] >= ts) & (feats["date"] <= te)].copy()
    real_test_meta = meta_full[(meta_full["date"] >= ts) & (meta_full["date"] <= te)].copy()
    real_r = run_portfolio_backtest(features=test_features, meta_ranking=real_test_meta, **BASE)
    real_cagr = real_r["metrics"]["cagr"]

    symbols_dates = test_features[["symbol", "date"]].drop_duplicates().reset_index(drop=True)
    rng = np.random.default_rng(SEED)
    null_cagrs = np.empty(N_ITER)
    for i in range(N_ITER):
        rand_meta = symbols_dates.copy()
        rand_meta["meta_score"] = rng.random(len(symbols_dates))
        r = run_portfolio_backtest(features=test_features, meta_ranking=rand_meta, **BASE)
        null_cagrs[i] = r["metrics"]["cagr"]
        if (i + 1) % 500 == 0:
            print(f"[{time.time()-t0:.0f}s] fold {test_start[:4]}: {i+1}/{N_ITER}")
            sys.stdout.flush()

    percentile = float((null_cagrs < real_cagr).mean() * 100.0)
    rows.append({"fold": test_start[:4], "real_cagr": real_cagr, "real_percentile_in_null": percentile, "n_symbol_days": len(symbols_dates)})
    print(f"[{time.time()-t0:.0f}s] fold {test_start[:4]} DONE: real_cagr={real_cagr:+.1%} percentile={percentile:.1f}")
    sys.stdout.flush()

result = pd.DataFrame(rows)
result.to_csv("data/output/v2_stability_toggle_active_only.csv", index=False)
print("\n" + "=" * 90)
print("TOGGLE: ACTIVE-only prefilter, NO minimal_eligible gate")
print("=" * 90)
print(result.to_string(index=False))
print(f"\nAverage percentile: {result['real_percentile_in_null'].mean():.1f}")
print("done")
