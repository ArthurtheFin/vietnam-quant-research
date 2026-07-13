from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
os.chdir(PROJECT_ROOT)

import pandas as pd
from src.data.dataset_config import OFFICIAL_FEATURES_PATH
from src.data.loaders import read_parquet, save_parquet, append_parquet
from src.alpha.scoring import calculate_alpha_scores
from src.utils.pipeline_io import build_lineage_metadata, validate_lineage_metadata, write_json

def main():
    print("=== Running Alpha Scoring System ===")

    # 1. Load data
    stock_path = Path(OFFICIAL_FEATURES_PATH)
    bench_path = Path("data/processed/benchmark_vnindex.parquet")
    
    if not stock_path.exists():
        print(f"Error: stock_features not found at {stock_path}. Run scripts/generate_features.py first.")
        sys.exit(1)
        
    stock_df = read_parquet(str(stock_path))
    benchmark_df = read_parquet(str(bench_path)) if bench_path.exists() else pd.DataFrame()
    
    if benchmark_df.empty:
        print("[Warning] benchmark_vnindex not found. Skipping relative strength calculations.")
        
    # 2. Run Scoring
    print("Calculating alpha scores cross-sectionally...")
    scored = calculate_alpha_scores(stock_df, benchmark_df)
    
    # 3. Save full history
    out_path = "data/signals/alpha_scores.parquet"
    save_parquet(scored, out_path)
    print(f"Saved full history of alpha scores to {out_path} ({len(scored)} rows)")
    
    # 4. Generate Reports
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Latest date
    latest_date = scored["date"].max()
    latest_subset = scored[scored["date"] == latest_date].copy()
    
    cols = [
        "symbol", "date", "close", "alpha_score", "alpha_score_shadow_v1", "momentum_score",
        "rs_score", "trend_score", "volume_score", "volatility_score",
        "liquidity_score", "market_regime"
    ]
    available_cols = [c for c in cols if c in latest_subset.columns]

    # Report 1: daily alpha ranking
    ranking = latest_subset[available_cols].sort_values("alpha_score", ascending=False)
    ranking.to_csv(reports_dir / "daily_alpha_ranking.csv", index=False)
    print(f"Exported daily alpha ranking to {reports_dir / 'daily_alpha_ranking.csv'} ({len(ranking)} symbols)")

    # Report 2: top 20 watchlist (alpha_score >= 75 or top 20)
    top_watchlist = ranking.head(20).copy()
    top_watchlist.to_csv(reports_dir / "top_watchlist.csv", index=False)
    print(f"Exported top 20 watchlist to {reports_dir / 'top_watchlist.csv'}")

    # Lineage (audit gate #12): daily_alpha_ranking.csv/top_watchlist.csv are
    # plain CSVs with no metadata slot of their own -- write a sidecar so both
    # can be traced back to the exact features snapshot + code version that
    # produced them, same convention as portfolio_risk_report.json.
    lineage = validate_lineage_metadata(
        build_lineage_metadata(OFFICIAL_FEATURES_PATH, base_dir=PROJECT_ROOT),
        label="alpha_scoring_metadata.json",
    )
    write_json(
        {
            "latest_date": latest_date.date().isoformat(),
            "symbol_count": int(len(ranking)),
            "top_watchlist_count": int(len(top_watchlist)),
            "generated_files": [
                "data/signals/alpha_scores.parquet",
                "reports/daily_alpha_ranking.csv",
                "reports/top_watchlist.csv",
            ],
            "lineage": lineage,
        },
        reports_dir / "alpha_scoring_metadata.json",
    )
    print(f"Wrote lineage metadata to {reports_dir / 'alpha_scoring_metadata.json'}")

    # Shadow log: v2 (deployed) vs v1 (shadow) side by side, appended daily
    # so the live out-of-sample comparison accumulates day by day starting
    # from today (SCORE_V2_REPORT.md).
    if "alpha_score_shadow_v1" in latest_subset.columns:
        shadow_cols = ["symbol", "date", "alpha_score", "alpha_score_shadow_v1"]
        shadow_today = latest_subset[shadow_cols].copy()
        append_parquet(shadow_today, "data/signals/alpha_score_shadow_log.parquet", subset=["symbol", "date"])
        print(f"Appended {len(shadow_today)} rows to data/signals/alpha_score_shadow_log.parquet "
              f"(v2 vs v1 shadow comparison, date={latest_date.date()})")

    print("=== Alpha Scoring Complete ===")

if __name__ == "__main__":
    main()
