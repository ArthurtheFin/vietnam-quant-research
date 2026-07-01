"""
Alpha Scoring System for Vietnam stock market research.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_alpha_scores(stock_df: pd.DataFrame, benchmark_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate a 0-100 alpha score cross-sectionally by date using:
    - momentum score: 25% (20d & 60d average return rank)
    - relative strength score: 25% (20d & 60d alpha relative to benchmark rank)
    - trend score: 20% (close > MA20, MA50, MA200 criteria)
    - volume confirmation score: 15% (volume_ratio_20d rank)
    - volatility contraction score: 10% (realized volatility rank, lower is better)
    - liquidity score: 5% (value_ma20 rank)
    """
    if stock_df.empty:
        return stock_df.copy()
        
    stocks = stock_df.sort_values(["symbol", "date"]).copy()
    
    # Calculate volume ratio
    if "volume_ma20" in stocks.columns:
        stocks["volume_ratio_20d"] = stocks["volume"] / stocks["volume_ma20"].replace(0, np.nan)
    else:
        stocks["volume_ratio_20d"] = 1.0
        
    # Prepare benchmark returns
    if not benchmark_df.empty:
        bench = benchmark_df.sort_values("date").copy()
        bench_cols = ["date", "close", "return_20d", "return_60d"]
        available_bench = [c for c in bench_cols if c in bench.columns]
        bench = bench[available_bench].copy()
        
        rename_map = {}
        if "close" in bench.columns:
            rename_map["close"] = "bench_close"
        if "return_20d" in bench.columns:
            rename_map["return_20d"] = "bench_ret_20d"
        if "return_60d" in bench.columns:
            rename_map["return_60d"] = "bench_ret_60d"
            
        bench = bench.rename(columns=rename_map)
    else:
        bench = pd.DataFrame(columns=["date"])
        
    # Merge benchmark returns
    merged = pd.merge(stocks, bench, on="date", how="left")
    
    # Fill NAs and compute relative strength
    for r_col in ["return_20d", "return_60d"]:
        if r_col not in merged.columns:
            merged[r_col] = 0.0
            
    if "bench_ret_20d" in merged.columns:
        merged["rs_20d"] = merged["return_20d"] - merged["bench_ret_20d"]
    else:
        merged["rs_20d"] = 0.0
        
    if "bench_ret_60d" in merged.columns:
        merged["rs_60d"] = merged["return_60d"] - merged["bench_ret_60d"]
    else:
        merged["rs_60d"] = 0.0
        
    merged["rs_20d"] = merged["rs_20d"].fillna(0.0)
    merged["rs_60d"] = merged["rs_60d"].fillna(0.0)
    
    # Market Regime Filter
    # uptrend if benchmark close > MA50 and MA50 > MA200
    # downtrend if benchmark close < MA50 and MA50 < MA200
    # otherwise neutral
    if not benchmark_df.empty and "close" in benchmark_df.columns:
        bench_regime = benchmark_df.sort_values("date").copy()
        if "ma50" not in bench_regime.columns:
            bench_regime["ma50"] = bench_regime["close"].rolling(50, min_periods=5).mean()
        if "ma200" not in bench_regime.columns:
            bench_regime["ma200"] = bench_regime["close"].rolling(200, min_periods=20).mean()
            
        bench_regime["market_regime"] = "neutral"
        bench_regime.loc[(bench_regime["close"] > bench_regime["ma50"]) & (bench_regime["ma50"] > bench_regime["ma200"]), "market_regime"] = "uptrend"
        bench_regime.loc[(bench_regime["close"] < bench_regime["ma50"]) & (bench_regime["ma50"] < bench_regime["ma200"]), "market_regime"] = "downtrend"
        
        bench_regime = bench_regime.sort_values("date").reset_index(drop=True)
        regime_map = bench_regime.set_index("date")["market_regime"].to_dict()
        
        # Determine fallback regime (latest known)
        if not bench_regime.empty:
            latest_date = bench_regime["date"].max()
            latest_regime = regime_map[latest_date]
        else:
            latest_date = None
            latest_regime = "unknown"
            
        merged["market_regime"] = merged["date"].map(regime_map)
        
        # Forward fill the latest known regime for any dates after the benchmark's max date
        if latest_date is not None and latest_regime != "unknown":
            is_newer = merged["date"] > latest_date
            merged.loc[is_newer & merged["market_regime"].isna(), "market_regime"] = latest_regime
            
        merged["market_regime"] = merged["market_regime"].fillna("unknown")
    else:
        merged["market_regime"] = "unknown"
        
    # Group by date and calculate rankings cross-sectionally
    def compute_ranks(group):
        # 1. Momentum score: rank average of return_20d and return_60d
        r20 = group["return_20d"].rank(pct=True, na_option="keep") * 100.0
        r60 = group["return_60d"].rank(pct=True, na_option="keep") * 100.0
        group["momentum_score"] = ((r20.fillna(50.0) + r60.fillna(50.0)) / 2.0).clip(0.0, 100.0)
        
        # 2. RS score: rank average of rs_20d and rs_60d
        rs20 = group["rs_20d"].rank(pct=True, na_option="keep") * 100.0
        rs60 = group["rs_60d"].rank(pct=True, na_option="keep") * 100.0
        group["rs_score"] = ((rs20.fillna(50.0) + rs60.fillna(50.0)) / 2.0).clip(0.0, 100.0)
        
        # 3. Trend score: close > MA20, MA50, MA200 criteria
        c_above_ma20 = (group["close"] > group.get("ma20", group["close"])).astype(float)
        c_above_ma50 = (group["close"] > group.get("ma50", group["close"])).astype(float)
        c_above_ma200 = (group["close"] > group.get("ma200", group["close"])).astype(float)
        group["trend_score"] = (c_above_ma20 * 34.0 + c_above_ma50 * 33.0 + c_above_ma200 * 33.0).clip(0.0, 100.0)
        
        # 4. Volume confirmation score: volume_ratio_20d rank
        group["volume_score"] = (group["volume_ratio_20d"].rank(pct=True, na_option="keep") * 100.0).fillna(50.0).clip(0.0, 100.0)
        
        # 5. Volatility contraction score: realized_vol_20d (lower is better, i.e. contraction)
        vol_metric = group.get("realized_vol_20d", group.get("atr_pct_14", pd.Series(1.0, index=group.index)))
        group["volatility_score"] = ((1.0 - vol_metric.rank(pct=True, na_option="keep")) * 100.0).fillna(50.0).clip(0.0, 100.0)
        
        # 6. Liquidity score: value_ma20 rank
        liq_metric = group.get("value_ma20", pd.Series(1.0, index=group.index))
        group["liquidity_score"] = (liq_metric.rank(pct=True, na_option="keep") * 100.0).fillna(50.0).clip(0.0, 100.0)
        
        # 7. Final Alpha Score
        group["alpha_score"] = (
            0.25 * group["momentum_score"]
            + 0.25 * group["rs_score"]
            + 0.20 * group["trend_score"]
            + 0.15 * group["volume_score"]
            + 0.10 * group["volatility_score"]
            + 0.05 * group["liquidity_score"]
        ).clip(0.0, 100.0)
        
        return group
        
    ranked_frames = [compute_ranks(group.copy()) for _, group in merged.groupby("date", sort=False)]
    return pd.concat(ranked_frames, ignore_index=True) if ranked_frames else merged.iloc[0:0].copy()
