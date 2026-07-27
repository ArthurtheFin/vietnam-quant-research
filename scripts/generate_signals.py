from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import os
os.chdir(PROJECT_ROOT)

import yaml
from src.data.dataset_config import OFFICIAL_FEATURES_PATH
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

# Input-chain freshness (CLAUDE.md rule 12 / AUDIT_NOTEBOOKS_REPORT.md Đợt 3 NV2):
# this step only ever checked that its inputs were non-empty, never that they
# were current. Harmless in a normal sequential nightly run; catches a
# standalone rerun against a half-built or stale feature file.
from src.validation.freshness_check import DerivedArtifactStale, assert_input_chain_fresh

try:
    assert_input_chain_fresh(PROJECT_ROOT, consumer="generate_signals")
except DerivedArtifactStale as exc:
    raise SystemExit(str(exc)) from exc

features = read_parquet(OFFICIAL_FEATURES_PATH)
if features.empty:
    raise SystemExit('No features found. Run scripts/generate_features.py first.')

signals = add_breakout_signal(features, lookback=breakout_lookback, min_volume_z=breakout_min_volume_z)
signals = add_pullback_ma_signal(signals, ma_col=pullback_ma_col, tolerance=pullback_tolerance)
signals = add_volume_spike_signal(signals, threshold=volume_spike_threshold)
save_parquet(signals, 'data/signals/setup_signals.parquet')
print(signals.shape)
