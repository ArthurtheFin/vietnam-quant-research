"""Recompute DSR under 3 M (trial-count) scenarios, reusing the exact same
real v2 backtest daily-return series and deflated_sharpe_ratio() from
dsr_and_bootstrap_v2.py (unmodified) -- only n_trials varies. Response to
an adversarial review questioning the conservatism of the declared M=560.
See docs/reports/scoring/ROBUSTNESS_REPORT.md section 5 for the full
git-history-based methodology behind the 560/635/678 scenario values.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dsr_and_bootstrap_v2 import compute_v2_score, deflated_sharpe_ratio

features_all = read_parquet("data/processed/stock_features.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
benchmark["date"] = pd.to_datetime(benchmark["date"])
sector_df = pd.read_csv("config/sector_map.csv")
sector_map = dict(zip(sector_df["symbol"], sector_df["sector"]))

scored = compute_v2_score(features_all)
v2_meta = scored[["symbol", "date", "v2_score"]].rename(columns={"v2_score": "meta_score"})

BASE = dict(
    rebalance_period=20, portfolio_size=10, allocation_method="equal_weight",
    transaction_cost_pct=0.0015, initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000, require_above_ma200=True,
    benchmark_features=benchmark, max_per_sector=2, sector_map=sector_map,
)

test_start, test_end = pd.Timestamp("2022-01-01"), pd.Timestamp("2026-07-06")
test_features = features_all[(features_all["date"] >= test_start) & (features_all["date"] <= test_end)].copy()
test_meta = v2_meta[(v2_meta["date"] >= test_start) & (v2_meta["date"] <= test_end)].copy()

result = run_portfolio_backtest(features=test_features, meta_ranking=test_meta, **BASE)
metrics = result["metrics"]
print(f"CAGR={metrics['cagr']:+.2%} Sharpe={metrics.get('sharpe_ratio', float('nan')):.3f}")

port_ret = result["portfolio_returns"]
if isinstance(port_ret, pd.DataFrame):
    ret_col = "return" if "return" in port_ret.columns else port_ret.columns[-1]
    daily_returns = port_ret[ret_col].dropna().to_numpy(dtype=float)
else:
    daily_returns = pd.Series(port_ret).dropna().to_numpy(dtype=float)

for label, M in [("conservative (current declared)", 560), ("moderate", 635), ("broad", 678)]:
    r = deflated_sharpe_ratio(daily_returns, M)
    print(f"\n=== M={M} ({label}) ===")
    print(f"  SR_hat(ann)={r['sr_hat_annualized']:.4f}  SR0(daily)={r['sr0_threshold_daily']:.5f}  z={r['z_stat']:.3f}  DSR={r['dsr']:.4f}")
