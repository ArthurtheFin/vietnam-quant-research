"""
Alpha Scoring System for Vietnam stock market research.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.validation.guards import assert_no_forward_columns


def calculate_alpha_scores(stock_df: pd.DataFrame, benchmark_df: pd.DataFrame) -> pd.DataFrame:
    """
    Primary output `alpha_score` is the v2 composite (docs/reports/scoring/docs/reports/scoring/SCORE_V2_DESIGN.md /
    docs/reports/scoring/docs/reports/scoring/SCORE_V2_REPORT.md), installed after the v1 composite (below) was found
    to have no significant standalone IC anywhere it was tested
    (docs/reports/scoring/docs/reports/scoring/SCORE_FORENSIC_REPORT.md NV3) and to have actively driven the 2026
    walk-forward disaster fold via a momentum/relative-strength reversal
    (docs/reports/scoring/docs/reports/scoring/SCORE_FORENSIC_REPORT.md NV2):
    - v2: 70% realized_vol_20d rank (lower vol = higher score; the one
      component with independently validated IC, t_NW=-5.41 both universes
      at design time, recalibrated -5.48 on 2026-07-15 data -- docs/reports/scoring/docs/reports/scoring/ROBUSTNESS_REPORT.md
      NV2, stable) + 30% value_ma20 rank (lower/less-liquid = higher score,
      matching its own validated but narrower IC evidence, t_NW=-3.33 full
      universe only at design time, recalibrated -3.37, with a disclosed
      survivorship-bias caveat -- docs/reports/data/docs/reports/data/DATA_BASELINE.md). Confirmation run:
      null-test avg percentile 71.0/2000 across 5 folds (no fold <5th), IC
      t_NW=+6.09 (full) / +5.67 (top150) residualized, same-signed all 3
      periods -- **this 71.0 is valid for v2 tested standalone only** (the
      confirmation run's own gate: min_value_ma20/above_ma200 inside
      run_portfolio_backtest, nothing more). When v2 runs inside
      final_watchlist.py's full eligibility gate (strict_pass/fallback_eligible,
      not just liquidity/trend), the same null test gives 52.8, not 71.0 --
      docs/reports/scoring/docs/reports/scoring/V2_STABILITY_NOTE.md traced the entire gap to that extra gate, not to
      data or universe. Do not cite 71.0 for v2-inside-final_watchlist
      contexts. As of docs/reports/scoring/docs/reports/scoring/ROBUSTNESS_REPORT.md (GD5): v2 has a real, FDR-
      surviving ranking effect but no surviving profitability evidence once
      honestly deflated for the project's full multiple-testing history
      (DSR=0.0083 at M=560 trials, bootstrap CI crosses 0 for both CAGR and
      Sharpe) -- docs/reports/scoring/docs/reports/scoring/SCORE_V2_REPORT.md's "Trạng thái sau GĐ5" section locks the
      operational decision: shadow log only, no real-capital allocation.

    The v1 composite is retained as `alpha_score_shadow_v1` for live,
    ongoing out-of-sample comparison (not used by any downstream
    consumer) -- momentum score 25% (60d return rank), relative strength
    25% (20d & 60d alpha vs. benchmark), trend 20% (MA20/50/200), volume
    15% (volume_ratio_20d rank), volatility 10% (realized_vol_20d rank,
    lower is better), liquidity 5% (value_ma20 rank, higher is better --
    note this is the OPPOSITE direction from v2's liquidity component;
    v1's direction was never independently validated).
    """
    if stock_df.empty:
        return stock_df.copy()

    # audit/PATH_TO_100.md Signal/Alpha item: assert_no_forward_columns previously
    # only guarded the two output write sites (final_watchlist.py); the scoring
    # step itself had no guard. mode="drop" (not "raise") -- research callers
    # routinely pass stock_features.parquet/stealth_accumulation_history.parquet
    # with forward_return_Nd columns already present for their OWN downstream
    # backtest/IC use; this function just must never let those columns influence
    # or ride through its own scoring math.
    stock_df = assert_no_forward_columns(stock_df, context="src.alpha.scoring.calculate_alpha_scores", mode="drop")
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
        # 1. Momentum score: return_60d rank. return_20d removed per
        # docs/reports/scoring/docs/reports/scoring/FACTOR_RETEST_V2_REPORT.md NV4: no significant IC in any of the 4 tested
        # combinations (full/top150 x raw/residualized, max |t_NW|=1.24, raw sign
        # even flips between universes) on clean full-2020+ data.
        r60 = group["return_60d"].rank(pct=True, na_option="keep") * 100.0
        group["momentum_score"] = r60.fillna(50.0).clip(0.0, 100.0)
        
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
        
        # 7. v1 composite -- kept as a shadow/comparison column only, not
        # consumed downstream. See docs/reports/scoring/docs/reports/scoring/SCORE_FORENSIC_REPORT.md for why it was
        # superseded.
        group["alpha_score_shadow_v1"] = (
            0.25 * group["momentum_score"]
            + 0.25 * group["rs_score"]
            + 0.20 * group["trend_score"]
            + 0.15 * group["volume_score"]
            + 0.10 * group["volatility_score"]
            + 0.05 * group["liquidity_score"]
        ).clip(0.0, 100.0)

        # 8. v2 composite -- the primary, deployed `alpha_score`
        # (docs/reports/scoring/docs/reports/scoring/SCORE_V2_DESIGN.md / docs/reports/scoring/docs/reports/scoring/SCORE_V2_REPORT.md). Liquidity direction is
        # intentionally inverted from the v1 liquidity_score column above
        # (lower value_ma20 = higher v2 score), matching the validated IC
        # sign -- see the function docstring.
        vol_metric_v2 = group.get("realized_vol_20d", group.get("atr_pct_14", pd.Series(1.0, index=group.index)))
        v2_vol_score = ((1.0 - vol_metric_v2.rank(pct=True, na_option="keep")) * 100.0).fillna(50.0)
        liq_metric_v2 = group.get("value_ma20", pd.Series(1.0, index=group.index))
        v2_liquidity_score = ((1.0 - liq_metric_v2.rank(pct=True, na_option="keep")) * 100.0).fillna(50.0)
        group["alpha_score"] = (0.70 * v2_vol_score + 0.30 * v2_liquidity_score).clip(0.0, 100.0)

        return group
        
    ranked_frames = [compute_ranks(group.copy()) for _, group in merged.groupby("date", sort=False)]
    return pd.concat(ranked_frames, ignore_index=True) if ranked_frames else merged.iloc[0:0].copy()
