from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
os.chdir(PROJECT_ROOT)

import pandas as pd
import yaml
from src.data.benchmark import build_benchmark_file, load_index_files, prepare_index_features
from src.data.dataset_config import (
    OFFICIAL_CLEAN_OHLCV_PATH,
    OFFICIAL_FEATURES_PATH,
    OFFICIAL_MARKET_FEATURES_PATH,
    OFFICIAL_PRICE_RAW_DIR,
)
from src.data.loaders import read_symbol_files, save_parquet
from src.data.validators import filter_primary_equity_symbols, standardize_ohlcv, validate_ohlcv
from src.features.returns import add_returns
from src.features.trend import add_moving_averages
from src.features.volatility import add_atr, add_realized_volatility, add_ewma_volatility, add_volatility_percentile, classify_volatility_regime
from src.features.distribution import add_rolling_distribution_stats
from src.features.liquidity import add_liquidity_features
from src.features.breadth import calculate_market_breadth
from src.models.regime import add_market_regime
from src.analytics.entropy import build_market_entropy_profile

with open('config/strategy_config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

horizons = cfg.get('returns', {}).get('horizons', [1, 5, 10, 20])
ma_windows = cfg.get('trend', {}).get('ma_windows', [20, 50, 200])
atr_window = cfg.get('volatility', {}).get('atr_window', 14)
realized_windows = cfg.get('volatility', {}).get('realized_windows', [20])
ewma_span = cfg.get('volatility', {}).get('ewma_span', 20)
percentile_window = cfg.get('volatility', {}).get('percentile_window', 252)
distribution_window = cfg.get('distribution', {}).get('window', 60)

# Step 1: Load and standardize raw data. OFFICIAL_PRICE_RAW_DIR
# (src/data/dataset_config.py) is the single source of truth for the raw
# price dataset -- audit gate #6 / critical finding P0-2 -- never read from
# the legacy data/raw/daily_ohlcv/ directory here.
raw = read_symbol_files(OFFICIAL_PRICE_RAW_DIR)
# full_history_v2 files already carry a parsed `date` column alongside the
# original `tradingdate` string -- drop the latter so standardize_ohlcv's
# tradingdate->date alias doesn't collide with the column that already exists.
raw = raw.drop(columns=["tradingdate"], errors="ignore")
raw = standardize_ohlcv(raw)
raw_checks = validate_ohlcv(raw)

if raw.empty:
    raise SystemExit(f"No raw data found in {OFFICIAL_PRICE_RAW_DIR}. Run scratch/full_backfill_v2.py first.")

raw = raw.dropna(subset=["symbol", "date", "close"]).copy()
raw = filter_primary_equity_symbols(raw)

excluded = pd.read_csv('config/excluded_symbols.csv')
raw = raw[~raw["symbol"].isin(excluded["symbol"])].copy()

raw = raw.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last").reset_index(drop=True)

# Step 2: Save clean OHLCV (needed by stealth screener and other downstream)
save_parquet(raw, OFFICIAL_CLEAN_OHLCV_PATH)
print("clean_daily_ohlcv", raw.shape)
print("raw_validation", raw_checks)

# Step 3: Generate stock features
features = add_returns(raw, horizons=horizons)
features = add_moving_averages(features, windows=ma_windows)
features = add_atr(features, window=atr_window)
for window in realized_windows:
    features = add_realized_volatility(features, window=window)
features = add_ewma_volatility(features, span=ewma_span)

if realized_windows:
    preferred_vol_col = 'realized_vol_20d' if 20 in realized_windows else f'realized_vol_{realized_windows[0]}d'
else:
    preferred_vol_col = f'ewma_vol_{ewma_span}d'

features = add_volatility_percentile(features, vol_col=preferred_vol_col, window=percentile_window)
features = classify_volatility_regime(features)
features = add_rolling_distribution_stats(features, window=distribution_window)
features = add_liquidity_features(features)
save_parquet(features, OFFICIAL_FEATURES_PATH)
print("stock_features", features.shape)

# Step 4: Generate index features and benchmark (moved ahead of market regime
# so VNINDEX's own price series is available for crash/breakout detection)
index_raw = load_index_files('data/raw/index_ohlcv')
benchmark = pd.DataFrame()
if not index_raw.empty:
    index_features = prepare_index_features(index_raw, horizons=horizons)
    save_parquet(index_features, 'data/processed/index_features.parquet')
    benchmark = build_benchmark_file(
        index_id='VNINDEX',
        raw_dir='data/raw/index_ohlcv',
        output_path='data/processed/benchmark_vnindex.parquet',
        horizons=horizons,
    )
    print('index_features', index_features.shape)
    print('benchmark_vnindex', benchmark.shape)
else:
    print('No raw index data found in data/raw/index_ohlcv')

# Step 5: Generate market features and regime (crash_severity/breakout_signal
# need the real VNINDEX price series from Step 4 -- see src/models/regime.py)
print("Generating market features and regime...")
features["date"] = pd.to_datetime(features["date"])
breadth = calculate_market_breadth(features)
market = add_market_regime(breadth, benchmark=benchmark)
market_entropy = build_market_entropy_profile(features, windows=[21, 63, 126], n_bins=24)
market = market.merge(market_entropy, on="date", how="left")
save_parquet(market, OFFICIAL_MARKET_FEATURES_PATH)
print("market_features", market.shape)

print("\n=== Feature generation complete ===")
