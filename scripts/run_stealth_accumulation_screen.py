from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
os.chdir(PROJECT_ROOT)

from src.data.dataset_config import OFFICIAL_FEATURES_PATH, OFFICIAL_MARKET_FEATURES_PATH
from src.data.loaders import read_parquet, save_parquet
from src.screening.stealth_accumulation import (
    compare_screen_backtests,
    latest_screen_snapshot,
    load_screen_config,
    prepare_stealth_accumulation_features,
)


# Input-chain freshness (CLAUDE.md rule 12 / AUDIT_NOTEBOOKS_REPORT.md Đợt 3 NV2):
# this step only ever checked that its inputs were non-empty, never that they
# were current. Harmless in a normal sequential nightly run; catches a
# standalone rerun against a half-built or stale feature file.
from src.validation.freshness_check import DerivedArtifactStale, assert_input_chain_fresh

try:
    assert_input_chain_fresh(PROJECT_ROOT, consumer="run_stealth_accumulation_screen")
except DerivedArtifactStale as exc:
    raise SystemExit(str(exc)) from exc

config = load_screen_config("config/screens/stealth_accumulation.yaml")

# Use stock_features directly — it already contains clean OHLCV + all computed features
features_df = read_parquet(OFFICIAL_FEATURES_PATH)
market_df = read_parquet(OFFICIAL_MARKET_FEATURES_PATH)
benchmark_df = read_parquet("data/processed/benchmark_vnindex.parquet")

if features_df.empty:
    raise SystemExit("No features data found. Run scripts/generate_features.py first.")
if benchmark_df.empty:
    print("WARNING: benchmark_vnindex.parquet missing — market proxy falls back to the basket itself (audit G2).")

# Run stealth accumulation screening
# features_df serves as both price_df and feature source
screen_df = prepare_stealth_accumulation_features(
    price_df=features_df,
    volatility_df=features_df,
    distribution_df=features_df,
    market_df=market_df,
    config=config,
    benchmark_df=benchmark_df,
)

latest_df = latest_screen_snapshot(screen_df, top_n=config["output"]["top_n"], only_watchlist=False)
watchlist_df = latest_screen_snapshot(screen_df, top_n=config["output"]["top_n"], only_watchlist=True)

sector_cfg = config.get("sector", {})
sector_latest_df = latest_screen_snapshot(
    screen_df,
    top_n=config["output"]["top_n"],
    only_watchlist=False,
    sector_aware=True,
    max_names_per_sector=sector_cfg.get("max_names_per_sector"),
    sector_col=sector_cfg.get("column", "sector"),
    unknown_sector=sector_cfg.get("unknown_label", "Unclassified"),
)
sector_watchlist_df = latest_screen_snapshot(
    screen_df,
    top_n=config["output"]["top_n"],
    only_watchlist=True,
    sector_aware=True,
    max_names_per_sector=sector_cfg.get("max_names_per_sector"),
    sector_col=sector_cfg.get("column", "sector"),
    unknown_sector=sector_cfg.get("unknown_label", "Unclassified"),
)

backtest_cfg = config.get("backtest", {})
backtest = compare_screen_backtests(
    screen_df,
    top_n=backtest_cfg.get("top_n", 5),
    holding_periods=backtest_cfg.get("holding_periods", [5, 10, 20]),
    only_watchlist=backtest_cfg.get("only_watchlist", False),
    entry_delay_days=backtest_cfg.get("entry_delay_days", 1),
    entry_price_col=backtest_cfg.get("entry_price_col", "open"),
    exit_price_col=backtest_cfg.get("exit_price_col", "close"),
    max_names_per_sector=sector_cfg.get("max_names_per_sector", 2),
    sector_col=sector_cfg.get("column", "sector"),
    unknown_sector=sector_cfg.get("unknown_label", "Unclassified"),
    benchmark_symbol=backtest_cfg.get("benchmark_symbol", "VNINDEX"),
    benchmark_path=backtest_cfg.get("benchmark_path"),
    cost_model=backtest_cfg.get("cost_model"),
)

save_parquet(screen_df, "data/signals/stealth_accumulation_history.parquet")
save_parquet(latest_df, "data/signals/stealth_accumulation_latest.parquet")
save_parquet(watchlist_df, "data/signals/stealth_accumulation_watchlist.parquet")
save_parquet(sector_latest_df, "data/signals/stealth_accumulation_sector_latest.parquet")
save_parquet(sector_watchlist_df, "data/signals/stealth_accumulation_sector_watchlist.parquet")
save_parquet(backtest["summary"], "data/signals/stealth_accumulation_backtest_summary.parquet")
save_parquet(backtest["by_date"], "data/signals/stealth_accumulation_backtest_by_date.parquet")
save_parquet(backtest["selections"], "data/signals/stealth_accumulation_backtest_selections.parquet")

print("=== Stealth Accumulation Screen Complete ===")
print("History rows:", len(screen_df))
print("Latest leaders:", len(latest_df))
print("Watchlist names:", len(watchlist_df))
print("Sector-aware leaders:", len(sector_latest_df))
print("Sector-aware watchlist:", len(sector_watchlist_df))
if not backtest["summary"].empty and "benchmark_source" in backtest["summary"].columns:
    print("Benchmark source:", backtest["summary"]["benchmark_source"].dropna().iloc[0])
