"""One-time derivation of classify_entropy_regime's low/high thresholds from
the real market_entropy_21d distribution -- run once, result hardcoded as
ENTROPY_REGIME_LOW_THRESHOLD / ENTROPY_REGIME_HIGH_THRESHOLD in
src/analytics/entropy.py. Re-run this (and re-hardcode) if there's a reason
to refresh the calibration against materially more history -- not to chase
a backtest result. See docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md NV3.
"""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.analytics.entropy import derive_entropy_regime_thresholds

market = pd.read_parquet(PROJECT_ROOT / "data/processed/market_features.parquet")
series = market["market_entropy_21d"]

low, high = derive_entropy_regime_thresholds(series, low_percentile=15.0, high_percentile=85.0)

print(f"date range: {market['date'].min().date()} -> {market['date'].max().date()}")
print(f"n non-null market_entropy_21d: {series.notna().sum()}")
print(f"observed range: [{series.min():.3f}, {series.max():.3f}]")
print(f"derived low_threshold (p15): {low:.3f}")
print(f"derived high_threshold (p85): {high:.3f}")

s = series.dropna()
n = len(s)
print(
    f"resulting split -- Structured {(s <= low).sum()} ({(s <= low).sum() / n:.1%}), "
    f"Transitional {((s > low) & (s < high)).sum()} ({((s > low) & (s < high)).sum() / n:.1%}), "
    f"Chaotic {(s >= high).sum()} ({(s >= high).sum() / n:.1%})"
)
