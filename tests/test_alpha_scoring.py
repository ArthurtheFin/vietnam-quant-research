from __future__ import annotations

import numpy as np
import pandas as pd
from src.alpha.scoring import calculate_alpha_scores


def test_alpha_scoring_logic():
    # 1. Create mock stock data
    dates = pd.date_range(start="2026-06-01", periods=5)
    symbols = ["AAA", "BBB", "CCC"]
    
    rows = []
    for d in dates:
        for idx, s in enumerate(symbols):
            # Give AAA highest returns, BBB medium, CCC lowest
            ret_scale = 0.05 if s == "AAA" else (0.02 if s == "BBB" else -0.01)
            rows.append({
                "symbol": s,
                "date": d,
                "close": 10000.0 * (1.0 + idx * 0.1),
                "volume": 100000.0 * (1.0 + idx * 0.2),
                "volume_ma20": 100000.0,
                "return_20d": ret_scale,
                "return_60d": ret_scale * 1.5,
                "realized_vol_20d": 0.15 + idx * 0.05,
                "value_ma20": 1000000.0,
                "ma20": 9500.0,
                "ma50": 9000.0,
                "ma200": 8000.0,
            })
            
    stock_df = pd.DataFrame(rows)
    
    # 2. Create mock benchmark data (VNINDEX)
    bench_rows = []
    for d in dates:
        bench_rows.append({
            "symbol": "VNINDEX",
            "date": d,
            "close": 1200.0,
            "return_20d": 0.01,
            "return_60d": 0.02,
        })
    benchmark_df = pd.DataFrame(bench_rows)
    
    # 3. Calculate scores
    scored = calculate_alpha_scores(stock_df, benchmark_df)
    
    # 4. Assertions
    assert not scored.empty
    assert "alpha_score" in scored.columns
    assert "rs_score" in scored.columns
    assert "momentum_score" in scored.columns
    assert "market_regime" in scored.columns
    
    # Check that AAA has higher score than CCC due to better momentum and relative strength
    latest = scored[scored["date"] == dates[-1]]
    aaa_score = float(latest[latest["symbol"] == "AAA"]["alpha_score"].iloc[0])
    ccc_score = float(latest[latest["symbol"] == "CCC"]["alpha_score"].iloc[0])
    assert aaa_score > ccc_score
    
    # Check bounds
    assert (scored["alpha_score"] >= 0.0).all()
    assert (scored["alpha_score"] <= 100.0).all()
