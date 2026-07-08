from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
os.chdir(PROJECT_ROOT)

import pandas as pd

from src.analytics.meta_ranking import build_meta_ranking, save_meta_ranking_outputs, top_meta_candidates
from src.data.loaders import read_parquet
from src.screening.final_watchlist import build_watchlist_tiers, save_watchlist_outputs

import yaml


def _latest_date(df: object, candidates: tuple[str, ...] = ("analysis_date", "date", "trade_card_date", "stealth_date")):
    if not hasattr(df, "empty") or getattr(df, "empty"):
        return None
    for column in candidates:
        if column not in df.columns:
            continue
        values = pd.to_datetime(df[column], errors="coerce").dropna()
        if not values.empty:
            return values.max()
    return None


def _assert_not_stale(reference_df, target_df, reference_name: str, target_name: str) -> None:
    reference_latest = _latest_date(reference_df)
    target_latest = _latest_date(target_df)
    if reference_latest is None or target_latest is None:
        return
    if target_latest < reference_latest:
        raise SystemExit(
            f"{target_name} is stale relative to {reference_name}. "
            f"Latest {reference_name}: {reference_latest.date()}, latest {target_name}: {target_latest.date()}."
        )


features = read_parquet("data/signals/setup_signals.parquet")
trade_cards = read_parquet("data/signals/breakout_20d_trade_cards.parquet")
stealth_latest = read_parquet("data/signals/stealth_accumulation_latest.parquet")
stock_features = read_parquet("data/processed/stock_features.parquet")
alpha_scores = read_parquet("data/signals/alpha_scores.parquet")

if features.empty and trade_cards.empty and stealth_latest.empty:
    raise SystemExit("No ranking inputs found. Generate setup signals or stealth outputs first.")

_assert_not_stale(stock_features, features, "stock_features.parquet", "setup_signals.parquet")
if trade_cards.empty:
    print("Warning: No trade cards found. Run scripts/generate_trade_cards.py for better ranking quality.")
else:
    _assert_not_stale(features, trade_cards, "setup_signals.parquet", "breakout_20d_trade_cards.parquet")
if stealth_latest.empty:
    print("Warning: No stealth data found. Run scripts/run_stealth_accumulation_screen.py first.")
else:
    _assert_not_stale(stock_features, stealth_latest, "stock_features.parquet", "stealth_accumulation_latest.parquet")
if not alpha_scores.empty:
    _assert_not_stale(stock_features, alpha_scores, "stock_features.parquet", "alpha_scores.parquet")

ranked = build_meta_ranking(
    features=features,
    trade_cards=trade_cards,
    stealth=stealth_latest,
    signal_col="breakout_20d",
)

# Merge Alpha Scores into Meta-Ranking dataset
if not alpha_scores.empty:
    alpha_df = alpha_scores.copy()
    if not alpha_df.empty:
        # Get latest alpha score per symbol
        alpha_latest = alpha_df.sort_values("date").groupby("symbol").tail(1)
        rename_map = {
            "alpha_score": "alpha_score",
            "momentum_score": "alpha_momentum_score",
            "rs_score": "alpha_rs_score",
            "trend_score": "alpha_trend_score",
            "volume_score": "alpha_volume_score",
            "volatility_score": "alpha_volatility_score",
            "liquidity_score": "alpha_liquidity_score",
        }
        cols_to_keep = ["symbol"] + [c for c in rename_map.keys() if c in alpha_latest.columns]
        alpha_latest_sub = alpha_latest[cols_to_keep].rename(columns={k: v for k, v in rename_map.items() if k in alpha_latest.columns})
        ranked = ranked.merge(alpha_latest_sub, on="symbol", how="left")
        print(f"Successfully merged alpha scores into meta ranking dataset.")

paths = save_meta_ranking_outputs(
    ranked,
    out_dir="data/signals",
    prefix="meta_ranking",
    top_n=20,
    min_score=50.0,
)
watchlist = top_meta_candidates(ranked, top_n=20, min_score=50.0)
prime = top_meta_candidates(ranked, top_n=10, min_score=75.0, allowed_buckets=("Prime Candidate",))

with open("config/strategy_config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

final_cfg = cfg.get("final_watchlist", {})
benchmark = read_parquet(final_cfg.get("paths", {}).get("benchmark", "data/processed/benchmark_vnindex.parquet"))
analysis_as_of = _latest_date(ranked) or _latest_date(features) or _latest_date(stock_features)
candidate_symbols = None  # unrestricted: rank the full universe, not a pre-filtered subset

watchlist_outputs = build_watchlist_tiers(
    features=stock_features,
    benchmark=benchmark,
    meta_ranking=ranked,
    alpha_scores=alpha_scores,
    config=final_cfg,
    as_of_date=analysis_as_of,
    candidate_symbols=candidate_symbols,
)
final_watchlist = watchlist_outputs["client_ready_watchlist"].copy()
final_paths = save_watchlist_outputs(watchlist_outputs, final_cfg, base_dir=PROJECT_ROOT)

print("=== Meta Ranking Complete ===")
print("Ranked universe:", len(ranked))
print("Watchlist names:", len(watchlist))
print("Prime candidates:", len(prime))
print("Ranked path:", paths["ranked"])
print("Research candidates:", len(watchlist_outputs["research_candidates"]))
print("Trading watchlist:", len(watchlist_outputs["trading_watchlist"]))
print("Client-ready watchlist:", len(final_watchlist))
print("Final watchlist path:", final_paths["parquet"])
