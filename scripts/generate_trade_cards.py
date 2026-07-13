from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
os.chdir(PROJECT_ROOT)

import pandas as pd

from src.data.dataset_config import OFFICIAL_FEATURES_PATH
from src.data.loaders import read_parquet, save_parquet
from src.reporting.trade_card_pipeline import build_trade_cards, save_trade_cards


def _latest_date(df: object, column: str = "date"):
    if not hasattr(df, "empty") or getattr(df, "empty"):
        return None
    if column not in df.columns:
        return None
    values = pd.to_datetime(df[column], errors="coerce").dropna()
    if values.empty:
        return None
    return values.max()


signals = read_parquet("data/signals/setup_signals.parquet")
features = read_parquet(OFFICIAL_FEATURES_PATH)

if signals.empty:
    raise SystemExit("No signals found. Run scripts/generate_signals.py first.")

features_latest = _latest_date(features)
signals_latest = _latest_date(signals)
if features_latest is not None and signals_latest is not None and signals_latest < features_latest:
    raise SystemExit(
        "setup_signals.parquet is stale relative to stock_features.parquet. "
        "Run scripts/generate_signals.py before generating trade cards."
    )

# Load setup eligibility and volatility rule parameters
eligibility = read_parquet("data/signals/breakout_20d_setup_eligibility.parquet")
vol_rule = read_parquet("data/signals/breakout_20d_volatility_rule.parquet")

trade_cards = build_trade_cards(
    features=signals,
    eligibility=eligibility,
    vol_rule=vol_rule,
    signal_col="breakout_20d",
)

if trade_cards.empty:
    print("No trade cards generated (no active breakout signals).")
else:
    save_trade_cards(trade_cards, path="data/signals/breakout_20d_trade_cards.parquet")
    print(f"Generated {len(trade_cards)} trade cards")
    print(f"Saved to data/signals/breakout_20d_trade_cards.parquet")
