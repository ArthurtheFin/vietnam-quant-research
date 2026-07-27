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
from src.validation.freshness_check import DerivedArtifactStale, assert_derived_artifact_fresh


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

# Load setup eligibility and volatility rule parameters.
#
# STALENESS GUARD (AUDIT_NOTEBOOKS_REPORT.md OPEN_AUTO #1). These two files have
# NO producer anywhere in src/ or scripts/ -- the only thing that writes them is
# `save_breakout_research_outputs()`, called exclusively from
# notebooks/03_alpha_signals/07_breakout_research.ipynb, by hand. Meanwhile this
# script is step 4/7 of the nightly pipeline and reads them every night.
#
# The audit found them frozen at 2026-07-02 while setup_signals.parquet was
# 2026-07-23 -- 21 days of trade cards silently built on stale per-symbol
# eligibility (win_rate/avg_return/profit_factor/edge_tier) and a stale
# stop_loss. Nothing warned, because the trade cards themselves were being
# regenerated daily and so passed every downstream freshness check.
#
# Neither file carries a `date` column, so freshness is measured by file mtime
# against setup_signals.parquet's mtime (both are "when was this last rebuilt").
# Deliberately a hard failure, not a warning: shipping a watchlist derived from
# month-old research is worse than not shipping one, and a silent warning is
# exactly the failure mode that let this run for 21 days.
#
# NOT auto-generated in the pipeline on purpose: run_breakout_research() picks
# its stop-loss via _select_best_stop_relaxed() (src/backtest/breakout_research.py:275),
# an IN-SAMPLE grid search over the same data it reports on. Wiring that into a
# nightly job would automate an overfit choice and re-fit it daily. Porting it
# needs its own pre-registered design -- tracked separately, see
# AUDIT_NOTEBOOKS_REPORT.md "Đợt 2.1".
ELIGIBILITY_PATH = Path("data/signals/breakout_20d_setup_eligibility.parquet")
VOL_RULE_PATH = Path("data/signals/breakout_20d_volatility_rule.parquet")
SIGNALS_PATH = Path("data/signals/setup_signals.parquet")
DEFAULT_MAX_ELIGIBILITY_LAG_DAYS = 7

try:
    assert_derived_artifact_fresh(
        derived_paths=(ELIGIBILITY_PATH, VOL_RULE_PATH),
        source_path=SIGNALS_PATH,
        max_lag_days=float(
            os.environ.get("MAX_ELIGIBILITY_LAG_DAYS", DEFAULT_MAX_ELIGIBILITY_LAG_DAYS)
        ),
        remedy=(
            "Trade cards would inherit stale eligibility/stop-loss parameters from it. "
            "Fix: run notebooks/03_alpha_signals/07_breakout_research.ipynb with "
            "ALLOW_PRODUCTION_WRITE=1 to refresh both files, then rerun this step. "
            "Temporary override: MAX_ELIGIBILITY_LAG_DAYS=<days> (or -1 to disable). "
            "Background: AUDIT_NOTEBOOKS_REPORT.md OPEN_AUTO #1."
        ),
    )
except DerivedArtifactStale as exc:
    raise SystemExit(str(exc)) from exc

eligibility = read_parquet(ELIGIBILITY_PATH)
vol_rule = read_parquet(VOL_RULE_PATH)

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
