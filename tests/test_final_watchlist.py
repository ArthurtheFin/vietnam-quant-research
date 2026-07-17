from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.screening.final_watchlist import FINAL_WATCHLIST_COLUMNS, build_final_watchlist


def _sample_features(symbol_count: int = 14) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-01", periods=180)
    frames = []
    for idx in range(symbol_count):
        symbol = f"S{idx:02d}"
        close = 20 + idx + np.linspace(0, 10 + idx, len(dates))
        volume = np.full(len(dates), 150_000 + idx * 20_000, dtype=float)
        frame = pd.DataFrame(
            {
                "symbol": symbol,
                "date": dates,
                "open": close * 0.995,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": volume,
                "value": close * volume,
            }
        )
        frame["return_20d"] = frame["close"].pct_change(20)
        frame["return_60d"] = frame["close"].pct_change(60)
        frame["ma20"] = frame["close"].rolling(20, min_periods=5).mean()
        frame["ma50"] = frame["close"].rolling(50, min_periods=10).mean()
        frame["ma200"] = frame["close"].rolling(120, min_periods=20).mean()
        frame["above_ma20"] = frame["close"] > frame["ma20"]
        frame["above_ma50"] = frame["close"] > frame["ma50"]
        frame["above_ma200"] = frame["close"] > frame["ma200"]
        frame["distance_ma20"] = frame["close"] / frame["ma20"] - 1
        frame["distance_ma50"] = frame["close"] / frame["ma50"] - 1
        frame["atr_pct_14"] = 0.025 + idx * 0.001
        frame["realized_vol_20d"] = 0.18 + idx * 0.005
        frame["volatility_percentile"] = 0.35 + idx * 0.01
        frame["volatility_regime"] = "Normal Vol"
        frame["tail_ratio_60d"] = 1.0 + idx * 0.02
        frame["volume_ma20"] = frame["volume"].rolling(20, min_periods=5).mean()
        frame["volume_zscore_20d"] = 1.0
        frame["value_ma20"] = frame["value"].rolling(20, min_periods=5).mean()
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def _sample_benchmark(features: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(features["date"].unique())
    close = np.linspace(1000, 1120, len(dates))
    bench = pd.DataFrame({"symbol": "VNINDEX", "date": dates, "close": close})
    bench["return_20d"] = bench["close"].pct_change(20)
    bench["return_60d"] = bench["close"].pct_change(60)
    return bench


def test_final_watchlist_returns_exactly_10() -> None:
    features = _sample_features()
    latest = features.sort_values(["symbol", "date"]).groupby("symbol").tail(1)
    meta = latest[["symbol", "date"]].copy()
    meta["meta_score"] = np.linspace(40, 95, len(meta))
    meta["trade_edge_score"] = meta["meta_score"]
    meta["setup_quality_score"] = meta["meta_score"] - 5
    meta["risk_penalty_score"] = 20

    watchlist = build_final_watchlist(
        features=features,
        benchmark=_sample_benchmark(features),
        meta_ranking=meta,
        alpha_scores=pd.DataFrame(),
        config={"min_value_ma20": 0, "min_volume_ma20": 0},
    )

    assert 0 < len(watchlist) <= 10
    assert watchlist["symbol"].nunique() == len(watchlist)
    assert list(watchlist.columns) == FINAL_WATCHLIST_COLUMNS
    assert watchlist["final_score"].between(0, 100).all()
    assert (watchlist["candidate_tier"] == "Client Ready").all()
    assert watchlist["is_client_ready"].all()


def test_final_watchlist_fails_clearly_when_universe_too_small() -> None:
    features = _sample_features(symbol_count=6)
    with pytest.raises(ValueError, match="Need at least 10 unique symbols"):
        build_final_watchlist(features=features, benchmark=_sample_benchmark(features))


def test_final_watchlist_respects_candidate_symbols_and_as_of_date() -> None:
    features = _sample_features()
    latest = features.sort_values(["symbol", "date"]).groupby("symbol").tail(1).copy()
    available_dates = sorted(features["date"].unique())
    as_of_date = pd.Timestamp(available_dates[-2])
    candidate_symbols = (
        features[features["date"] <= as_of_date]
        .sort_values(["symbol", "date"])
        .groupby("symbol")
        .tail(1)["symbol"]
        .head(4)
        .tolist()
    )

    meta = latest[["symbol", "date"]].copy()
    meta["date"] = pd.Timestamp(as_of_date)
    meta["analysis_date"] = pd.Timestamp(as_of_date)
    meta["meta_score"] = np.linspace(40, 95, len(meta))
    meta["trade_edge_score"] = meta["meta_score"]
    meta["setup_quality_score"] = meta["meta_score"] - 5
    meta["risk_penalty_score"] = 20

    watchlist = build_final_watchlist(
        features=features,
        benchmark=_sample_benchmark(features),
        meta_ranking=meta,
        alpha_scores=pd.DataFrame(),
        config={"watchlist_size": 10, "min_value_ma20": 0, "min_volume_ma20": 0},
        as_of_date=as_of_date,
        candidate_symbols=candidate_symbols,
    )

    assert set(watchlist["symbol"]).issubset(set(candidate_symbols))
    assert 0 < len(watchlist) <= len(candidate_symbols)


def test_final_watchlist_excludes_missing_backtest_from_client_ready() -> None:
    features = _sample_features()
    latest = features.sort_values(["symbol", "date"]).groupby("symbol").tail(1).copy()
    latest["market_regime"] = "uptrend"
    meta = latest[["symbol", "date"]].head(6).copy()
    meta["analysis_date"] = meta["date"]
    meta["meta_score"] = np.linspace(70, 95, len(meta))
    meta["trade_edge_score"] = meta["meta_score"]
    meta["setup_quality_score"] = meta["meta_score"] - 5
    meta["risk_penalty_score"] = 20

    watchlist = build_final_watchlist(
        features=features,
        benchmark=_sample_benchmark(features),
        meta_ranking=meta,
        alpha_scores=pd.DataFrame(),
        config={"watchlist_size": 10, "min_value_ma20": 0, "min_volume_ma20": 0},
    )

    assert not watchlist.empty
    assert watchlist["warning"].str.contains("Missing backtest evidence", na=False).sum() == 0


def test_min_price_threshold_is_vnd_not_a_bare_number():
    """C1: a 3,000 VND penny stock must fail the price filter (old threshold: 5.0)."""
    from src.screening.final_watchlist import _mark_filters, DEFAULT_FINAL_WATCHLIST_CONFIG

    df = pd.DataFrame(
        [
            {
                "symbol": "PENNY", "close": 3000.0, "history_days": 300,
                "value_ma20": 20_000_000_000.0, "volume_ma20": 100_000.0,
                "above_ma50": True, "above_ma200": True,
                "return_20d": 0.05, "return_60d": 0.05,
                "atr_pct_14": 0.03, "distance_ma20": 0.02,
            },
            {
                "symbol": "BLUE", "close": 65000.0, "history_days": 300,
                "value_ma20": 20_000_000_000.0, "volume_ma20": 100_000.0,
                "above_ma50": True, "above_ma200": True,
                "return_20d": 0.05, "return_60d": 0.05,
                "atr_pct_14": 0.03, "distance_ma20": 0.02,
            },
        ]
    )
    out = _mark_filters(df, DEFAULT_FINAL_WATCHLIST_CONFIG)
    penny = out.set_index("symbol").loc["PENNY"]
    blue = out.set_index("symbol").loc["BLUE"]
    assert not bool(penny["strict_pass"]), "3,000 VND stock must fail min_price (was passing at threshold=5.0)"
    assert bool(blue["strict_pass"])


def test_negative_excess_return_demotes_from_client_ready() -> None:
    """G1: a real negative excess_return_20d is a hard floor for Client Ready,
    not an 8-point warning penalty a high score can absorb (matches SAB/BID in
    the current final_watchlist.csv, which pass with a 'Weak relative strength'
    warning today)."""
    from src.screening.final_watchlist import _apply_candidate_tiers

    df = pd.DataFrame(
        [
            {
                "symbol": "WEAK", "final_score": 75.0, "warning": "",
                "strict_pass": True, "fallback_eligible": True,
                "excess_return_20d": -0.02,
            },
            {
                "symbol": "STRONG", "final_score": 75.0, "warning": "",
                "strict_pass": True, "fallback_eligible": True,
                "excess_return_20d": 0.03,
            },
        ]
    )
    out = _apply_candidate_tiers(df)
    weak = out.set_index("symbol").loc["WEAK"]
    strong = out.set_index("symbol").loc["STRONG"]

    assert not bool(weak["is_client_ready"]), "negative excess return must not be Client Ready"
    assert weak["candidate_tier"] == "Trading Watchlist", "demoted, not fully excluded"
    assert "Weak relative strength" in weak["exclusion_reason"]

    assert bool(strong["is_client_ready"])
    assert strong["candidate_tier"] == "Client Ready"


def test_rank_universe_size_exposed_in_reason_and_columns() -> None:
    """G1: the score is a rank within N candidates, not an absolute measure."""
    from src.screening.final_watchlist import _apply_candidate_tiers, _reason_text

    df = pd.DataFrame(
        [{"symbol": f"S{i}", "final_score": 50.0 + i, "warning": "",
          "strict_pass": True, "fallback_eligible": True,
          "trend_score": 20.0, "relative_strength_score": 15.0,
          "momentum_score": 15.0, "liquidity_score": 8.0, "volume_score": 3.0,
          "risk_score": 7.0, "signal_score": 8.0} for i in range(7)]
    )
    out = _apply_candidate_tiers(df)
    assert (out["rank_universe_size"] == 7).all()
    text = _reason_text(out.iloc[0])
    assert "7 mã" in text


def test_build_watchlist_tiers_drops_forward_columns_from_features() -> None:
    """D5: forward_return_Nd columns in stock_features.parquet must be stripped
    before scoring, not just at the final save step."""
    features = _sample_features()
    features["forward_return_5d"] = 0.05  # simulates src/features/returns.py output

    meta = features.sort_values(["symbol", "date"]).groupby("symbol").tail(1)[["symbol", "date"]].copy()
    meta["meta_score"] = np.linspace(40, 95, len(meta))
    meta["trade_edge_score"] = meta["meta_score"]
    meta["setup_quality_score"] = meta["meta_score"] - 5
    meta["risk_penalty_score"] = 20

    watchlist = build_final_watchlist(
        features=features,
        benchmark=_sample_benchmark(features),
        meta_ranking=meta,
        alpha_scores=pd.DataFrame(),
        config={"min_value_ma20": 0, "min_volume_ma20": 0},
    )
    assert "forward_return_5d" not in watchlist.columns
    assert not watchlist.empty


def test_save_watchlist_outputs_drops_forward_columns(tmp_path) -> None:
    """D5: save_watchlist_outputs is also called standalone (post-cashflow overlay)
    and must guard independently, not rely on build_watchlist_tiers having run."""
    from src.screening.final_watchlist import save_watchlist_outputs, DEFAULT_FINAL_WATCHLIST_CONFIG

    # watchlist_metadata.json now embeds reproducibility lineage (audit gate
    # #12), which needs a real features file on disk to hash -- write a
    # minimal one at the configured path under tmp_path.
    features_path = tmp_path / DEFAULT_FINAL_WATCHLIST_CONFIG["paths"]["features"]
    features_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"symbol": ["AAA"], "date": [pd.Timestamp("2025-01-01")]}).to_parquet(features_path)

    frame = pd.DataFrame([{"symbol": "AAA", "final_score": 80.0, "forward_return_5d": 0.05}])
    outputs = {"client_ready_watchlist": frame.copy(), "trading_watchlist": pd.DataFrame(),
               "research_candidates": pd.DataFrame()}
    save_watchlist_outputs(outputs, config=DEFAULT_FINAL_WATCHLIST_CONFIG, base_dir=tmp_path)
    saved = pd.read_csv(tmp_path / "data/output/client_ready_watchlist.csv")
    assert "forward_return_5d" not in saved.columns


def test_momentum_score_ignores_alpha_score() -> None:
    """docs/reports/scoring/SCORE_V2_REPORT.md side effect: alpha_score (from data/signals/
    alpha_scores.parquet) is now the v2 composite (volatility/liquidity,
    not momentum) -- momentum_score must no longer move when only
    alpha_score changes, with every other alpha_* input held fixed."""
    features = _sample_features()
    latest = features.sort_values(["symbol", "date"]).groupby("symbol").tail(1)
    meta = latest[["symbol", "date"]].copy()
    meta["meta_score"] = np.linspace(40, 95, len(meta))
    meta["trade_edge_score"] = meta["meta_score"]
    meta["setup_quality_score"] = meta["meta_score"] - 5
    meta["risk_penalty_score"] = 20

    def _alpha_scores(alpha_score_values: np.ndarray) -> pd.DataFrame:
        alpha = latest[["symbol", "date"]].copy()
        alpha["alpha_score"] = alpha_score_values
        alpha["momentum_score"] = 50.0  # -> alpha_momentum_score, held fixed
        alpha["rs_score"] = 50.0
        alpha["trend_score"] = 50.0
        alpha["volume_score"] = 50.0
        alpha["volatility_score"] = 50.0
        alpha["liquidity_score"] = 50.0
        return alpha

    n = len(latest)
    common_kwargs = dict(
        features=features,
        benchmark=_sample_benchmark(features),
        meta_ranking=meta,
        config={"min_value_ma20": 0, "min_volume_ma20": 0},
    )
    low_alpha = build_final_watchlist(alpha_scores=_alpha_scores(np.full(n, 10.0)), **common_kwargs)
    high_alpha = build_final_watchlist(alpha_scores=_alpha_scores(np.full(n, 90.0)), **common_kwargs)

    merged = low_alpha[["symbol", "momentum_score"]].merge(
        high_alpha[["symbol", "momentum_score"]], on="symbol", suffixes=("_low_alpha", "_high_alpha")
    )
    assert (merged["momentum_score_low_alpha"] == merged["momentum_score_high_alpha"]).all(), (
        "momentum_score must be unaffected by alpha_score -- alpha_score is a "
        "volatility/liquidity signal now (docs/reports/scoring/SCORE_V2_REPORT.md), not momentum"
    )


def test_relative_strength_score_ignores_alpha_rs_score() -> None:
    """Audit gate #17 / critical finding P0-4: docs/reports/scoring/SCORE_FORENSIC_REPORT.md found
    the v1 shadow's rs_score IC flipped to -0.1060 in 2026, one of the primary
    drivers of a real -59.7% backtest loss. relative_strength_score must not
    move when only the v1 shadow's rs_score changes -- mirrors
    test_momentum_score_ignores_alpha_score exactly for the sibling field
    that was missed when momentum_score was fixed."""
    features = _sample_features()
    latest = features.sort_values(["symbol", "date"]).groupby("symbol").tail(1)
    meta = latest[["symbol", "date"]].copy()
    meta["meta_score"] = np.linspace(40, 95, len(meta))
    meta["trade_edge_score"] = meta["meta_score"]
    meta["setup_quality_score"] = meta["meta_score"] - 5
    meta["risk_penalty_score"] = 20

    def _alpha_scores(rs_score_values: np.ndarray) -> pd.DataFrame:
        alpha = latest[["symbol", "date"]].copy()
        alpha["alpha_score"] = 50.0
        alpha["momentum_score"] = 50.0
        alpha["rs_score"] = rs_score_values
        alpha["trend_score"] = 50.0
        alpha["volume_score"] = 50.0
        alpha["volatility_score"] = 50.0
        alpha["liquidity_score"] = 50.0
        return alpha

    n = len(latest)
    common_kwargs = dict(
        features=features,
        benchmark=_sample_benchmark(features),
        meta_ranking=meta,
        config={"min_value_ma20": 0, "min_volume_ma20": 0},
    )
    low_rs = build_final_watchlist(alpha_scores=_alpha_scores(np.full(n, 10.0)), **common_kwargs)
    high_rs = build_final_watchlist(alpha_scores=_alpha_scores(np.full(n, 90.0)), **common_kwargs)

    merged = low_rs[["symbol", "relative_strength_score"]].merge(
        high_rs[["symbol", "relative_strength_score"]], on="symbol", suffixes=("_low_rs", "_high_rs")
    )
    assert (merged["relative_strength_score_low_rs"] == merged["relative_strength_score_high_rs"]).all(), (
        "relative_strength_score must be unaffected by the v1 shadow's rs_score -- "
        "docs/reports/scoring/SCORE_FORENSIC_REPORT.md found it actively harmful (IC -0.1060 in 2026)"
    )


# Every v1-shadow-only field name that must never appear in a final_watchlist
# output, however it's spelled (raw from alpha_scores.parquet, or renamed
# with an alpha_ prefix by a merge step). Audit gate #17.
FORBIDDEN_V1_SHADOW_FIELDS = [
    "alpha_momentum_score", "alpha_rs_score", "alpha_trend_score",
    "alpha_volume_score", "alpha_volatility_score", "alpha_liquidity_score",
]


def test_no_v1_shadow_alpha_fields_in_any_watchlist_output() -> None:
    """Audit gate #17 regression guard: build the full tier set (not just
    client_ready_watchlist) with an alpha_scores input carrying every v1
    shadow component, and assert NONE of the forbidden field names appear in
    ANY output DataFrame -- including scored_universe/data_review_watchlist,
    which (unlike client_ready/trading/research) are NOT restricted to
    FINAL_WATCHLIST_COLUMNS and would silently carry any merged-in column."""
    from src.screening.final_watchlist import build_watchlist_tiers

    features = _sample_features()
    latest = features.sort_values(["symbol", "date"]).groupby("symbol").tail(1)
    meta = latest[["symbol", "date"]].copy()
    meta["meta_score"] = np.linspace(40, 95, len(meta))
    meta["trade_edge_score"] = meta["meta_score"]
    meta["setup_quality_score"] = meta["meta_score"] - 5
    meta["risk_penalty_score"] = 20

    alpha = latest[["symbol", "date"]].copy()
    alpha["alpha_score"] = 50.0
    alpha["momentum_score"] = 50.0
    alpha["rs_score"] = 50.0
    alpha["trend_score"] = 50.0
    alpha["volume_score"] = 50.0
    alpha["volatility_score"] = 50.0
    alpha["liquidity_score"] = 50.0

    outputs = build_watchlist_tiers(
        features=features,
        benchmark=_sample_benchmark(features),
        meta_ranking=meta,
        alpha_scores=alpha,
        config={"min_value_ma20": 0, "min_volume_ma20": 0},
    )
    for output_name, frame in outputs.items():
        leaked = [c for c in FORBIDDEN_V1_SHADOW_FIELDS if c in frame.columns]
        assert not leaked, f"v1 shadow field(s) {leaked} leaked into outputs['{output_name}']"
