import numpy as np
import pandas as pd

from src.analytics.advanced import (
    add_cross_sectional_momentum_rank,
    compute_rolling_beta,
    correlation_matrix_by_regime,
    pair_divergence_zscore,
    screen_pair_divergences,
)
from src.backtest.breakout_research import (
    build_setup_eligibility,
    build_volatility_rules,
    ensure_breakout_features,
)
from src.backtest.simulator import backtest_entries_with_atr_stop, sweep_atr_multiples
from src.reporting.trade_card_pipeline import build_daily_watchlist, build_trade_cards


def test_compute_rolling_beta_with_external_benchmark():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    assets = pd.DataFrame(
        {
            "symbol": ["AAA"] * 5,
            "date": dates,
            "return_1d": [0.01, 0.02, 0.03, 0.04, 0.05],
        }
    )
    benchmark = pd.DataFrame(
        {
            "date": dates,
            "return_1d": [0.01, 0.01, 0.02, 0.02, 0.03],
        }
    )

    beta = compute_rolling_beta(assets, benchmark_df=benchmark, benchmark_symbol="VNINDEX", window=3)

    assert "rolling_beta_3d" in beta.columns
    assert beta["rolling_beta_3d"].notna().sum() >= 1


def test_add_cross_sectional_momentum_rank_creates_rank_columns():
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 3 + ["BBB"] * 3,
            "date": pd.date_range("2024-01-01", periods=3, freq="D").tolist() * 2,
            "close": [10, 11, 12, 10, 10, 10.5],
        }
    )

    ranked = add_cross_sectional_momentum_rank(df, lookback=1)

    assert "momentum_1d" in ranked.columns
    assert "momentum_rank_1d" in ranked.columns
    latest = ranked[ranked["date"] == ranked["date"].max()]
    assert latest.loc[latest["symbol"] == "AAA", "momentum_rank_1d"].iloc[0] == 1


def test_pair_divergence_zscore_outputs_expected_columns():
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 4 + ["BBB"] * 4,
            "date": pd.date_range("2024-01-01", periods=4, freq="D").tolist() * 2,
            "close": [10, 11, 12, 13, 20, 19, 18, 17],
        }
    )

    divergence = pair_divergence_zscore(df, "AAA", "BBB", window=2)

    assert list(divergence.columns) == [
        "date",
        "symbol_a",
        "symbol_b",
        "price_a",
        "price_b",
        "spread",
        "rolling_mean",
        "rolling_std",
        "divergence_zscore",
    ]


def test_pair_divergence_zscore_handles_non_positive_prices():
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 4 + ["BBB"] * 4,
            "date": pd.date_range("2024-01-01", periods=4, freq="D").tolist() * 2,
            "close": [10.0, 0.0, 12.0, 13.0, 20.0, 19.0, 18.0, -1.0],
        }
    )

    divergence = pair_divergence_zscore(df, "AAA", "BBB", window=2)

    assert divergence["spread"].isna().sum() >= 1
    assert np.isfinite(divergence["spread"].dropna()).all()


def test_correlation_matrix_by_regime_filters_regime():
    df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "BBB", "BBB"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"]),
            "return_1d": [0.01, 0.02, 0.01, 0.03],
            "volatility_regime": ["Low Vol", "Low Vol", "Low Vol", "Low Vol"],
        }
    )

    corr = correlation_matrix_by_regime(df, "Low Vol", min_periods=1)

    assert corr.shape == (2, 2)


def test_screen_pair_divergences_returns_ranked_pairs():
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 5 + ["BBB"] * 5 + ["CCC"] * 5,
            "date": pd.date_range("2024-01-01", periods=5, freq="D").tolist() * 3,
            "close": [10, 10.5, 11, 10.8, 11.2, 20, 20.8, 21.5, 21.0, 22.1, 30, 29, 31, 30, 32],
        }
    )

    screened = screen_pair_divergences(df, top_n_pairs=3, min_abs_correlation=0.1, zscore_window=2)

    assert "divergence_zscore" in screened.columns


def test_backtest_entries_with_atr_stop_and_sweep():
    entries = pd.DataFrame(
        {
            "symbol": ["AAA"],
            "date": [pd.Timestamp("2024-01-01")],
            "atr_pct_14": [0.03],
            "volatility_regime": ["Normal Vol"],
        }
    )
    prices = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            # I4 semantics: entry = open of the bar AFTER the signal (100.0 on Jan 2)
            "open": [100.0, 100.0, 108.0],
            "close": [100.0, 96.0, 110.0],
            "low": [99.0, 93.0, 109.0],
            "high": [101.0, 97.0, 111.0],
            "atr_pct_14": [0.03, 0.03, 0.03],
        }
    )

    trades = backtest_entries_with_atr_stop(entries, prices, atr_multiple=2.0, holding_period=2, cost=0.0)
    summary, trade_map = sweep_atr_multiples(entries, prices, atr_multiples=[1.5, 2.0], holding_period=2, cost=0.0)

    assert trades.loc[0, "exit_reason"] == "atr_stop"
    assert len(summary) == 2
    assert set(trade_map.keys()) == {1.5, 2.0}


def test_build_trade_cards_and_watchlist():
    features = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "date": pd.to_datetime(["2024-01-10", "2024-01-10"]),
            "close": [100, 200],
            "breakout_20d": [True, False],
            "above_ma20": [True, True],
            "above_ma50": [True, False],
            "above_ma200": [False, False],
            "volume_zscore_20d": [1.5, 0.2],
            "volatility_regime": ["Low Vol", "Panic Vol"],
        }
    )
    eligibility = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "setup_name": ["breakout_20d", "breakout_20d"],
            "edge_tier": ["Strong Edge", "Avoid"],
            "eligible": [True, False],
            "profit_factor": [2.0, 0.8],
            "avg_return": [0.05, -0.01],
            "median_return": [0.02, -0.02],
            "stop_loss": [-0.1, -0.1],
            "holding_period": [20, 20],
            "cost_assumption": [0.004, 0.004],
        }
    )
    vol_rule = pd.DataFrame(
        {
            "volatility_regime": ["Low Vol", "Panic Vol"],
            "volatility_rule": ["Allowed", "Avoid"],
        }
    )

    trade_cards = build_trade_cards(features, eligibility, vol_rule)
    watchlist = build_daily_watchlist(trade_cards)

    assert trade_cards.loc[0, "action"] == "Valid Breakout Setup"
    assert "trade_edge_score" in watchlist.columns


def test_build_trade_cards_defaults_missing_eligibility_to_insufficient_data():
    features = pd.DataFrame(
        {
            "symbol": ["AAA", "CFPT2529"],
            "date": pd.to_datetime(["2024-01-10", "2024-01-10"]),
            "close": [100, 200],
            "breakout_20d": [False, False],
            "volatility_regime": ["Low Vol", "Low Vol"],
        }
    )
    vol_rule = pd.DataFrame(
        {
            "volatility_regime": ["Low Vol"],
            "volatility_rule": ["Allowed"],
        }
    )

    trade_cards = build_trade_cards(features, eligibility=pd.DataFrame(), vol_rule=vol_rule)

    assert set(trade_cards["symbol"].unique()) == {"AAA"}
    assert trade_cards.loc[0, "edge_tier"] == "Insufficient Data"
    assert trade_cards.loc[0, "action"] == "No Signal"


def test_breakout_research_helpers():
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 30,
            "date": pd.date_range("2024-01-01", periods=30, freq="D"),
            "open": np.linspace(10, 13, 30),
            "high": np.linspace(10.2, 13.2, 30),
            "low": np.linspace(9.8, 12.8, 30),
            "close": np.linspace(10, 13, 30),
            "volume": np.linspace(1000, 2000, 30),
            "value": np.linspace(10000, 26000, 30),
        }
    )
    prepared = ensure_breakout_features(df)
    by_symbol = pd.DataFrame(
        {
            "symbol": ["AAA"],
            "trades": [25],
            "win_rate": [0.6],
            "avg_return": [0.03],
            "median_return": [0.02],
            "best_return": [0.1],
            "worst_return": [-0.05],
            "gross_profit": [0.4],
            "gross_loss": [0.2],
            "profit_factor": [2.0],
            "stop_rate": [0.2],
        }
    )
    by_regime = pd.DataFrame(
        {
            "volatility_regime": ["Low Vol"],
            "trades": [25],
            "win_rate": [0.6],
            "avg_return": [0.03],
            "median_return": [0.02],
            "best_return": [0.1],
            "worst_return": [-0.05],
            "gross_profit": [0.4],
            "gross_loss": [0.2],
            "profit_factor": [2.0],
            "stop_rate": [0.2],
        }
    )

    eligibility = build_setup_eligibility(by_symbol)
    vol_rule = build_volatility_rules(by_regime)

    assert "breakout_20d" in prepared.columns
    assert eligibility.loc[0, "edge_tier"] == "Strong Edge"
    assert vol_rule.loc[0, "volatility_rule"] == "Allowed"
