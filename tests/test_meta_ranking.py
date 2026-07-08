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


def test_thin_evidence_caps_priority_bucket():
    """G5: a symbol backed by <=1 of 3 signal sources cannot be Prime/High Conviction
    no matter how high the raw component scores read (old code had no such cap)."""
    from src.analytics.meta_ranking import score_meta_ranking

    data = pd.DataFrame(
        [
            {
                "symbol": "THIN", "date": pd.Timestamp("2024-06-20"),
                "trade_edge_score": 95.0, "setup_quality_score": 95.0,
                "net_accumulation_score": 95.0, "breakout_quality_score": 95.0,
                "relative_strength_score": 95.0, "breadth_support_score": 95.0,
                "sector_support_score": 95.0, "market_support_score": 95.0,
                "liquidity_score": 95.0, "fakeout_risk_score": 5.0,
                "overextension_risk_score": 5.0, "upper_wick_risk_score": 5.0,
                "volatility_spike_risk_score": 5.0, "exhaustion_volume_risk_score": 5.0,
                "tail_risk_score": 5.0, "return_20d": 0.30, "return_5d": 0.10,
                "volume_zscore_20d": 2.0, "avg_value_20d": 50_000_000_000.0,
                "atr_pct_14": 0.01, "above_ma20": True, "above_ma50": True, "above_ma200": True,
                "action": "Valid Breakout Setup", "volatility_rule": "Allowed",
                "volatility_regime": "Low Vol", "edge_tier": "Strong Edge",
                "breakout_20d": True, "watchlist_flag": True, "eligible": True,
                "watchlist_eligible": True,
                "insufficient_evidence": True,  # only 1 of 3 sources present
            },
            {
                "symbol": "FULL", "date": pd.Timestamp("2024-06-20"),
                "trade_edge_score": 95.0, "setup_quality_score": 95.0,
                "net_accumulation_score": 95.0, "breakout_quality_score": 95.0,
                "relative_strength_score": 95.0, "breadth_support_score": 95.0,
                "sector_support_score": 95.0, "market_support_score": 95.0,
                "liquidity_score": 95.0, "fakeout_risk_score": 5.0,
                "overextension_risk_score": 5.0, "upper_wick_risk_score": 5.0,
                "volatility_spike_risk_score": 5.0, "exhaustion_volume_risk_score": 5.0,
                "tail_risk_score": 5.0, "return_20d": 0.30, "return_5d": 0.10,
                "volume_zscore_20d": 2.0, "avg_value_20d": 50_000_000_000.0,
                "atr_pct_14": 0.01, "above_ma20": True, "above_ma50": True, "above_ma200": True,
                "action": "Valid Breakout Setup", "volatility_rule": "Allowed",
                "volatility_regime": "Low Vol", "edge_tier": "Strong Edge",
                "breakout_20d": True, "watchlist_flag": True, "eligible": True,
                "watchlist_eligible": True,
                "insufficient_evidence": False,  # all 3 sources present
            },
        ]
    )
    ranked = score_meta_ranking(data)
    thin = ranked.set_index("symbol").loc["THIN"]
    full = ranked.set_index("symbol").loc["FULL"]

    assert thin["meta_score"] >= 75.0, "test setup must actually reach the Prime threshold"
    assert thin["priority_bucket"] == "Secondary Watchlist", "thin evidence must cap the bucket"
    assert full["priority_bucket"] == "Prime Candidate", "full evidence must NOT be capped"


def test_synergy_bonus_does_not_double_count_action_label():
    """G6: action label is already priced via action_score; synergy must not add it twice."""
    from src.analytics.meta_ranking import score_meta_ranking

    base = {
        "symbol": "AAA", "date": pd.Timestamp("2024-06-20"),
        "trade_edge_score": 50.0, "setup_quality_score": 50.0,
        "net_accumulation_score": 50.0, "breakout_quality_score": 50.0,
        "relative_strength_score": 50.0, "breadth_support_score": 50.0,
        "sector_support_score": 50.0, "market_support_score": 50.0,
        "liquidity_score": 50.0, "fakeout_risk_score": 35.0,
        "overextension_risk_score": 35.0, "upper_wick_risk_score": 30.0,
        "volatility_spike_risk_score": 35.0, "exhaustion_volume_risk_score": 30.0,
        "tail_risk_score": 25.0, "return_20d": 0.05, "return_5d": 0.02,
        "volume_zscore_20d": 0.5, "avg_value_20d": 10_000_000_000.0,
        "atr_pct_14": 0.03, "above_ma20": True, "above_ma50": True, "above_ma200": True,
        "volatility_rule": "Allowed", "volatility_regime": "Low Vol", "edge_tier": "Valid Edge",
        "breakout_20d": False, "watchlist_flag": False, "eligible": False,
        "watchlist_eligible": False, "insufficient_evidence": False,
    }
    no_signal = pd.DataFrame([{**base, "symbol": "NOSIG", "action": "No Signal"}])
    valid_setup = pd.DataFrame([{**base, "symbol": "VALID", "action": "Valid Breakout Setup"}])

    r_no = score_meta_ranking(no_signal).iloc[0]
    r_valid = score_meta_ranking(valid_setup).iloc[0]

    # action_score alone must account for the entire meta_score delta between the
    # two rows -- old code added a further +3.0 synergy bonus on top of action_score.
    action_score_delta = r_valid["action_score"] - r_no["action_score"]
    meta_score_delta = r_valid["meta_score"] - r_no["meta_score"]
    expected_delta = 0.30 * 0.10 * action_score_delta  # breakout_component weight 0.30, action_score weight 0.10
    assert abs(meta_score_delta - expected_delta) < 1e-6, (
        f"meta_score delta {meta_score_delta} must equal action_score's own weighted "
        f"contribution {expected_delta}, not include an extra synergy bonus"
    )


def test_signal_age_warning_flags_source_date_mismatch():
    """G3: sources merged per-symbol without checking they agree on trading day."""
    from src.analytics.meta_ranking import prepare_meta_ranking_dataset

    features = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "date": pd.to_datetime(["2024-06-20", "2024-06-20"]),
            "close": [100.0, 60.0],
            "return_20d": [0.10, 0.03],
        }
    )
    trade_cards = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            # AAA's trade card is 10 days stale relative to features; BBB's is fresh
            "date": pd.to_datetime(["2024-06-10", "2024-06-20"]),
            "close": [98.0, 60.0],
            "breakout_20d": [True, False],
            "action": ["Valid Breakout Setup", "No Signal"],
        }
    )
    merged = prepare_meta_ranking_dataset(features=features, trade_cards=trade_cards, stealth=pd.DataFrame())
    row = merged.set_index("symbol")
    assert bool(row.loc["AAA", "signal_age_warning"]) is True
    assert row.loc["AAA", "source_date_spread_days"] == 10
    assert bool(row.loc["BBB", "signal_age_warning"]) is False


def test_meta_ranking_save_drops_forward_columns():
    """D5: a forward-looking column must be stripped before saving, not scored."""
    import tempfile

    from src.analytics.meta_ranking import save_meta_ranking_outputs

    data = pd.DataFrame(
        [{"symbol": "AAA", "date": pd.Timestamp("2024-06-20"), "meta_score": 80.0,
          "trade_edge_score": 0.0, "net_accumulation_score": 0.0, "priority_bucket": "Prime Candidate",
          "forward_return_5d": 0.05}]
    )
    with tempfile.TemporaryDirectory() as tmp:
        paths = save_meta_ranking_outputs(data, out_dir=tmp)
        saved = pd.read_parquet(paths["ranked"])
        assert "forward_return_5d" not in saved.columns, "forward column must be dropped before saving"


def test_final_watchlist_score_rejects_forward_columns():
    """D5: forward-looking columns must never reach the live scoring function."""
    import pytest

    from src.screening.final_watchlist import _score, DEFAULT_FINAL_WATCHLIST_CONFIG

    df = pd.DataFrame([{"symbol": "AAA", "forward_return_5d": 0.05}])
    with pytest.raises(ValueError, match="forward-looking"):
        _score(df, DEFAULT_FINAL_WATCHLIST_CONFIG)

