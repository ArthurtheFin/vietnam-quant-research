from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import os
os.chdir(PROJECT_ROOT)

import yaml
from src.data.loaders import read_parquet, save_parquet
from src.backtest.setup_rules import add_breakout_signal, add_pullback_ma_signal, add_volume_spike_signal

with open('config/strategy_config.yaml', 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

signal_cfg = cfg.get('signals', {})
breakout_lookback = signal_cfg.get('breakout_lookback', 20)
breakout_min_volume_z = signal_cfg.get('breakout_min_volume_z', 1.0)
pullback_ma_col = signal_cfg.get('pullback_ma_col', 'ma20')
pullback_tolerance = signal_cfg.get('pullback_tolerance', 0.015)
volume_spike_threshold = signal_cfg.get('volume_spike_threshold', 2.0)

features = read_parquet('data/processed/stock_features.parquet')
if features.empty:
    raise SystemExit('No features found. Run scripts/generate_features.py first.')

signals = add_breakout_signal(features, lookback=breakout_lookback, min_volume_z=breakout_min_volume_z)
signals = add_pullback_ma_signal(signals, ma_col=pullback_ma_col, tolerance=pullback_tolerance)
signals = add_volume_spike_signal(signals, threshold=volume_spike_threshold)
save_parquet(signals, 'data/signals/setup_signals.parquet')
print(signals.shape)
