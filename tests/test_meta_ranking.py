import pandas as pd

from src.analytics.meta_ranking import build_meta_ranking, top_meta_candidates


def test_build_meta_ranking_prefers_hybrid_high_quality_setups():
    features = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC"],
            "date": pd.to_datetime(["2024-06-20", "2024-06-20", "2024-06-20"]),
            "close": [100.0, 50.0, 30.0],
            "breakout_20d": [True, False, False],
            "return_20d": [0.20, 0.06, -0.03],
            "return_5d": [0.07, 0.01, -0.02],
            "volume_zscore_20d": [1.8, 0.4, -0.5],
            "above_ma20": [True, True, False],
            "above_ma50": [True, False, False],
            "above_ma200": [True, False, False],
            "avg_value_20d": [45_000_000_000.0, 18_000_000_000.0, 7_000_000_000.0],
            "atr_pct_14": [0.02, 0.04, 0.08],
        }
    )
    trade_cards = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "date": pd.to_datetime(["2024-06-20", "2024-06-20"]),
            "close": [100.0, 50.0],
            "breakout_20d": [True, False],
            "edge_tier": ["Strong Edge", "Conditional Edge"],
            "eligible": [True, True],
            "volatility_regime": ["Low Vol", "Normal Vol"],
            "volatility_rule": ["Allowed", "Conditional"],
            "profit_factor": [2.4, 1.4],
            "avg_return": [0.06, 0.02],
            "median_return": [0.03, 0.01],
            "stop_loss": [-0.10, -0.10],
            "holding_period": [20, 20],
            "setup_quality_score": [82, 55],
            "trade_edge_score": [88, 42],
            "action": ["Valid Breakout Setup", "Watchlist - No Signal"],
        }
    )
    stealth = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC"],
            "date": pd.to_datetime(["2024-06-20", "2024-06-20", "2024-06-20"]),
            "close": [100.0, 50.0, 30.0],
            "sector": ["Banking", "Retail", "Steel"],
            "watchlist_flag": [True, True, False],
            "net_accumulation_score": [90, 58, 25],
            "accumulation_score": [86, 55, 30],
            "breakout_quality_score": [84, 56, 28],
            "relative_strength_score": [85, 60, 35],
            "breadth_support_score": [80, 58, 40],
            "sector_support_score": [78, 55, 35],
            "market_support_score": [76, 55, 40],
            "liquidity_score": [88, 60, 35],
            "fakeout_risk_score": [20, 40, 75],
            "overextension_risk_score": [18, 35, 70],
            "upper_wick_risk_score": [15, 28, 60],
            "volatility_spike_risk_score": [20, 38, 72],
            "exhaustion_volume_risk_score": [18, 35, 68],
            "tail_risk_score": [15, 28, 60],
            "atr_pct_14": [0.02, 0.04, 0.08],
            "avg_value_20d": [45_000_000_000.0, 18_000_000_000.0, 7_000_000_000.0],
            "volatility_regime": ["Low Vol", "Normal Vol", "Panic Vol"],
            "market_regime": ["Risk-on", "Risk-on", "Risk-off"],
        }
    )

    ranked = build_meta_ranking(features=features, trade_cards=trade_cards, stealth=stealth)
    watchlist = top_meta_candidates(ranked, top_n=2, min_score=50.0)

    assert list(ranked["symbol"])[:2] == ["AAA", "BBB"]
    assert ranked.loc[0, "priority_bucket"] in {"Prime Candidate", "High Conviction Watchlist"}
    assert ranked.loc[0, "setup_style"] == "Hybrid Breakout + Accumulation"
    assert ranked.loc[0, "meta_score"] > ranked.loc[1, "meta_score"]
    assert "meta_summary" in ranked.columns
    assert len(watchlist) >= 1
    assert watchlist.loc[0, "symbol"] == "AAA"


def test_build_meta_ranking_handles_sparse_inputs_and_uses_trade_signal_fallback():
    features = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "date": pd.to_datetime(["2024-06-20", "2024-06-20"]),
            "close": [100.0, 60.0],
            "return_20d": [0.10, 0.03],
            "return_5d": [0.04, 0.01],
            "volume_zscore_20d": [1.0, 0.2],
            "above_ma20": [True, True],
            "above_ma50": [True, False],
            "above_ma200": [False, False],
        }
    )
    trade_cards = pd.DataFrame(
        {
            "symbol": ["AAA"],
            "date": [pd.Timestamp("2024-06-20")],
            "close": [100.0],
            "breakout_20d": [True],
            "eligible": [True],
            "volatility_regime": ["Normal Vol"],
            "volatility_rule": ["Allowed"],
            "setup_quality_score": [70],
            "trade_edge_score": [75],
            "action": ["Valid Breakout Setup"],
        }
    )

    ranked = build_meta_ranking(features=features, trade_cards=trade_cards, stealth=pd.DataFrame())

    assert len(ranked) == 2
    assert ranked["meta_score"].between(0, 100).all()
    aaa = ranked[ranked["symbol"] == "AAA"].iloc[0]
    assert bool(aaa["breakout_20d"]) is True
    assert aaa["volatility_regime"] == "Normal Vol"
