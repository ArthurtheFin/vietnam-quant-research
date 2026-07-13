import pandas as pd

from src.analytics.meta_ranking import build_meta_ranking, top_meta_candidates


def test_build_meta_ranking_prefers_mean_reversion_setups():
    """meta_score is now the walk-forward-validated 3-factor mean-reversion
    score (STRATEGY_RESEARCH_REPORT.md sections 3-6): lowest distance_ma20 /
    return_20d / realized_vol_20d ranks highest, not highest momentum. AAA is
    given the best (lowest) technical profile of the three AND the strongest
    breakout/stealth evidence, so it should win on both meta_score and
    setup_style; CCC is given the worst (most overbought/highest-momentum/
    highest-vol) profile, which the OLD momentum-chasing formula would have
    preferred but this one must not."""
    features = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC"],
            "date": pd.to_datetime(["2024-06-20", "2024-06-20", "2024-06-20"]),
            "close": [100.0, 50.0, 30.0],
            "breakout_20d": [True, False, False],
            "distance_ma20": [-0.01, 0.03, 0.10],
            "return_20d": [-0.02, 0.06, 0.20],
            "realized_vol_20d": [0.15, 0.25, 0.40],
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
    no matter how high meta_score reads. THIN and FULL each get their own date,
    accompanied by two filler rows with a worse (more overbought/higher-vol)
    technical profile, so each independently reaches the top of its own
    cross-sectional rank (meta_score ~100, comfortably over the 75 threshold)
    regardless of the other -- with just a 2-row shared date, percentile rank
    caps the loser at 50, which wouldn't exercise this cap at all."""
    from src.analytics.meta_ranking import score_meta_ranking

    def _row(symbol, date, insufficient_evidence, distance_ma20, return_20d, realized_vol_20d):
        return {
            "symbol": symbol, "date": pd.Timestamp(date),
            "trade_edge_score": 95.0, "setup_quality_score": 95.0,
            "net_accumulation_score": 95.0, "breakout_quality_score": 95.0,
            "relative_strength_score": 95.0, "breadth_support_score": 95.0,
            "sector_support_score": 95.0, "market_support_score": 95.0,
            "liquidity_score": 95.0, "fakeout_risk_score": 5.0,
            "overextension_risk_score": 5.0, "upper_wick_risk_score": 5.0,
            "volatility_spike_risk_score": 5.0, "exhaustion_volume_risk_score": 5.0,
            "tail_risk_score": 5.0, "distance_ma20": distance_ma20, "return_20d": return_20d,
            "realized_vol_20d": realized_vol_20d, "return_5d": 0.10,
            "volume_zscore_20d": 2.0, "avg_value_20d": 50_000_000_000.0,
            "atr_pct_14": 0.01, "above_ma20": True, "above_ma50": True, "above_ma200": True,
            "action": "Valid Breakout Setup", "volatility_rule": "Allowed",
            "volatility_regime": "Low Vol", "edge_tier": "Strong Edge",
            "breakout_20d": True, "watchlist_flag": True, "eligible": True,
            "watchlist_eligible": True,
            "insufficient_evidence": insufficient_evidence,
        }

    # reversal_quality_score's 2026-07-13 recalibration flipped distance_ma20's
    # and return_20d's sign to +1 (high raw value now ranks highest) --
    # realized_vol_20d's sign (-1, low ranks highest) is unchanged. THIN/FULL
    # need the best value on all three under the *current* sign convention to
    # clearly win their own 3-row cross-section.
    data = pd.DataFrame(
        [
            _row("THIN", "2024-06-20", True, 0.10, 0.10, 0.05),
            _row("FILLER1A", "2024-06-20", False, 0.02, 0.02, 0.20),
            _row("FILLER1B", "2024-06-20", False, -0.05, -0.05, 0.30),
            _row("FULL", "2024-06-21", False, 0.10, 0.10, 0.05),
            _row("FILLER2A", "2024-06-21", False, 0.02, 0.02, 0.20),
            _row("FILLER2B", "2024-06-21", False, -0.05, -0.05, 0.30),
        ]
    )
    ranked = score_meta_ranking(data)
    thin = ranked.set_index("symbol").loc["THIN"]
    full = ranked.set_index("symbol").loc["FULL"]

    assert thin["meta_score"] >= 75.0, "test setup must actually reach the Prime threshold"
    assert full["meta_score"] >= 75.0, "test setup must actually reach the Prime threshold"
    assert thin["priority_bucket"] == "Secondary Watchlist", "thin evidence must cap the bucket"
    assert full["priority_bucket"] == "Prime Candidate", "full evidence must NOT be capped"


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


def test_merge_alpha_score_v2_only_merges_v2_not_v1_shadow_fields():
    """Audit gate #17: merge_alpha_score_v2 must merge alpha_score (v2, validated)
    and must NOT merge any v1 shadow per-component score. run_meta_ranking.py
    previously merged all 6 v1 fields in as alpha_momentum_score/alpha_rs_score/
    alpha_trend_score/alpha_volume_score/alpha_volatility_score/
    alpha_liquidity_score with zero downstream consumer, leaking straight into
    the saved meta_ranking*.parquet report files (save_meta_ranking_outputs
    applies no column restriction beyond dropping forward-looking columns)."""
    from src.analytics.meta_ranking import merge_alpha_score_v2

    ranked = pd.DataFrame([{"symbol": "AAA", "meta_score": 80.0}, {"symbol": "BBB", "meta_score": 60.0}])
    alpha_scores = pd.DataFrame(
        [
            {
                "symbol": sym, "date": pd.Timestamp("2026-07-01"), "alpha_score": 55.0,
                "momentum_score": 50.0, "rs_score": 50.0, "trend_score": 50.0,
                "volume_score": 50.0, "volatility_score": 50.0, "liquidity_score": 50.0,
            }
            for sym in ("AAA", "BBB")
        ]
    )
    merged = merge_alpha_score_v2(ranked, alpha_scores)

    assert "alpha_score" in merged.columns, "the validated v2 alpha_score must still be merged in"
    forbidden = [
        "alpha_momentum_score", "alpha_rs_score", "alpha_trend_score",
        "alpha_volume_score", "alpha_volatility_score", "alpha_liquidity_score",
        "momentum_score", "rs_score", "trend_score", "volume_score", "volatility_score", "liquidity_score",
    ]
    leaked = [c for c in forbidden if c in merged.columns]
    assert not leaked, f"v1 shadow field(s) {leaked} must not be merged into the meta-ranking dataset"


def test_meta_ranking_report_outputs_never_carry_v1_shadow_fields():
    """End-to-end guard: even if merge_alpha_score_v2's contract is broken later,
    the saved meta_ranking report files must never carry a v1 shadow field."""
    from src.analytics.meta_ranking import merge_alpha_score_v2, save_meta_ranking_outputs

    ranked = pd.DataFrame(
        [{"symbol": "AAA", "date": pd.Timestamp("2026-07-01"), "meta_score": 80.0,
          "trade_edge_score": 0.0, "net_accumulation_score": 0.0, "priority_bucket": "Prime Candidate"}]
    )
    alpha_scores = pd.DataFrame(
        [{"symbol": "AAA", "date": pd.Timestamp("2026-07-01"), "alpha_score": 55.0,
          "momentum_score": 50.0, "rs_score": 50.0, "trend_score": 50.0,
          "volume_score": 50.0, "volatility_score": 50.0, "liquidity_score": 50.0}]
    )
    merged = merge_alpha_score_v2(ranked, alpha_scores)

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        paths = save_meta_ranking_outputs(merged, out_dir=tmp)
        saved = pd.read_parquet(paths["ranked"])
        forbidden = [
            "alpha_momentum_score", "alpha_rs_score", "alpha_trend_score",
            "alpha_volume_score", "alpha_volatility_score", "alpha_liquidity_score",
            "momentum_score", "rs_score", "trend_score", "volume_score", "volatility_score", "liquidity_score",
        ]
        leaked = [c for c in forbidden if c in saved.columns]
        assert not leaked, f"v1 shadow field(s) {leaked} leaked into the saved meta_ranking report"

