from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
os.chdir(PROJECT_ROOT)

import pandas as pd
from src.data.loaders import read_parquet, save_parquet
from src.alpha.scoring import calculate_alpha_scores

def main():
    print("=== Running Alpha Scoring System ===")
    
    # 1. Load data
    stock_path = Path("data/processed/stock_features.parquet")
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
        "symbol", "date", "close", "alpha_score", "momentum_score", 
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
    
    print("=== Alpha Scoring Complete ===")

if __name__ == "__main__":
    main()
