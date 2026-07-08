import numpy as np
import pandas as pd

from src.analytics.correlation import (
    build_return_matrix,
    compute_correlation_matrix,
    rolling_pair_correlation,
    top_correlation_pairs,
)
from src.backtest.simulator import (
    backtest_entries_with_fixed_stop,
    filter_non_overlapping_signals,
    summarize_trades,
    sweep_fixed_stop_losses,
)
from src.models.monte_carlo import monte_carlo_path_summary, simulate_trade_exits


def test_build_return_matrix_computes_returns_if_missing():
    df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "BBB", "BBB"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"]),
            "close": [10.0, 11.0, 20.0, 18.0],
        }
    )

    matrix = build_return_matrix(df)

    assert list(matrix.columns) == ["AAA", "BBB"]
    assert round(matrix.loc[pd.Timestamp("2024-01-02"), "AAA"], 4) == 0.1
    assert round(matrix.loc[pd.Timestamp("2024-01-02"), "BBB"], 4) == -0.1


def test_top_correlation_pairs_returns_unique_pairs():
    corr = pd.DataFrame(
        [[1.0, 0.8, -0.2], [0.8, 1.0, 0.7], [-0.2, 0.7, 1.0]],
        columns=["AAA", "BBB", "CCC"],
        index=["AAA", "BBB", "CCC"],
    )

    pairs = top_correlation_pairs(corr, top_n=5, min_abs_correlation=0.5)

    assert len(pairs) == 2
    assert set(pairs["symbol_a"] + "-" + pairs["symbol_b"]) == {"AAA-BBB", "BBB-CCC"}


def test_rolling_pair_correlation_has_expected_columns():
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 4 + ["BBB"] * 4,
            "date": pd.date_range("2024-01-01", periods=4, freq="D").tolist() * 2,
            "return_1d": [0.01, 0.02, 0.03, 0.04, 0.01, 0.01, 0.02, 0.05],
        }
    )

    rolling = rolling_pair_correlation(df, "AAA", "BBB", window=2)

    assert list(rolling.columns) == ["date", "symbol_a", "symbol_b", "rolling_correlation"]
    assert rolling["symbol_a"].iloc[0] == "AAA"
    assert rolling["symbol_b"].iloc[0] == "BBB"


def test_filter_non_overlapping_signals_respects_holding_period():
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 5,
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "breakout_20d": [True, True, False, True, True],
        }
    )

    out = filter_non_overlapping_signals(df, "breakout_20d", holding_period=2)

    assert list(out["date"]) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-04")]


def test_backtest_entries_with_fixed_stop_exits_on_stop():
    entries = pd.DataFrame(
        {
            "symbol": ["AAA"],
            "date": [pd.Timestamp("2024-01-01")],
            "volatility_regime": ["Normal Vol"],
        }
    )
    prices = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "close": [100.0, 98.0, 110.0],
            "low": [99.0, 89.0, 109.0],
            "high": [101.0, 100.0, 111.0],
        }
    )

    trades = backtest_entries_with_fixed_stop(entries, prices, holding_period=2, stop_loss=-0.05, cost=0.0)

    assert trades.loc[0, "exit_reason"] == "stop_loss"
    assert round(float(trades.loc[0, "net_return"]), 4) == -0.05


def test_sweep_fixed_stop_losses_returns_summary_and_trade_map():
    entries = pd.DataFrame({"symbol": ["AAA"], "date": [pd.Timestamp("2024-01-01")]})
    prices = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "close": [100.0, 102.0, 103.0],
            "low": [99.0, 101.0, 102.0],
            "high": [101.0, 103.0, 104.0],
        }
    )

    summary, trade_map = sweep_fixed_stop_losses(entries, prices, stop_losses=[None, -0.05], holding_period=2, cost=0.0)

    assert len(summary) == 2
    assert set(trade_map.keys()) == {None, -0.05}


def test_simulate_trade_exits_and_path_summary():
    paths = np.array([[101.0, 106.0], [99.0, 95.0], [100.0, 102.0]])

    exits = simulate_trade_exits(paths, entry=100.0, stop=97.0, target=105.0)
    summary = monte_carlo_path_summary(paths, start_price=100.0)

    assert list(exits["exit_type"]) == ["target", "stop", "time"]
    assert summary["day"].tolist() == [0, 1, 2]
    assert round(float(summary.loc[0, "mean_price"]), 4) == 100.0


def test_summarize_trades_reports_profit_factor():
    trades = pd.DataFrame({"net_return": [0.05, -0.02, 0.01], "exit_reason": ["time_exit", "stop_loss", "time_exit"]})

    summary = summarize_trades(trades)

    assert round(summary["profit_factor"], 4) == 3.0
    assert round(summary["stop_rate"], 4) == 0.3333


def test_backtest_entry_uses_next_bar_open_not_signal_close():
    """I4: entry must be the next session's open, not the close that produced the signal."""
    from src.backtest.simulator import backtest_entries_with_fixed_stop

    dates = pd.date_range("2025-01-01", periods=8, freq="B")
    prices = pd.DataFrame(
        {
            "symbol": ["AAA"] * len(dates),
            "date": dates,
            # signal day close = 100; next day gaps to open 105 and everything closes at 110
            "open": [100, 100, 105, 110, 110, 110, 110, 110],
            "high": [101, 101, 111, 111, 111, 111, 111, 111],
            "low": [99, 99, 104, 109, 109, 109, 109, 109],
            "close": [100, 100, 110, 110, 110, 110, 110, 110],
        }
    )
    entries = pd.DataFrame([{"symbol": "AAA", "date": dates[1]}])  # signal at close=100
    trades = backtest_entries_with_fixed_stop(
        entries_df=entries, price_df=prices, holding_period=3, stop_loss=None, cost=0.0
    )
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_price"] == 105.0, (
        f"entry must be next open 105, got {trade['entry_price']} — "
        "close-of-signal-day entry is untradeable (same-bar bias)"
    )
    assert abs(trade["gross_return"] - (110.0 / 105.0 - 1)) < 1e-9


def test_forward_returns_from_next_open_excludes_gap():
    """I4: open-based forward returns must not credit the overnight gap to the strategy."""
    from src.backtest.engine import attach_forward_returns_from_next_open

    dates = pd.date_range("2025-01-01", periods=10, freq="B")
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * len(dates),
            "date": dates,
            "open": [100, 105] + [110] * 8,
            "close": [100] + [110] * 9,
        }
    )
    out = attach_forward_returns_from_next_open(df, horizons=[5])
    first = out.iloc[0]
    # close-based would be 110/100-1 = 10%; open-based is 110/105-1 ≈ 4.76%
    assert abs(first["forward_return_open_5d"] - (110.0 / 105.0 - 1)) < 1e-9


def _synthetic_breakout_features(n_symbols: int = 4, n_days: int = 260, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-02", periods=n_days)
    rows = []
    for k in range(n_symbols):
        price = 100.0
        for d in dates:
            drift = rng.normal(0.0015, 0.02)
            price = max(1.0, price * (1 + drift))
            rows.append(
                {
                    "symbol": f"SYM{k}",
                    "date": d,
                    "open": price * (1 + rng.normal(0, 0.004)),
                    "high": price * 1.015,
                    "low": price * 0.985,
                    "close": price,
                    "volume": 1_000_000,
                    "volume_zscore_20d": rng.normal(1.5, 0.5),
                }
            )
    return pd.DataFrame(rows)


def test_breakout_stop_selection_is_out_of_sample():
    """I3: the stop is chosen on train entries; reported stats come from validation."""
    from src.backtest.breakout_research import run_breakout_research

    features = _synthetic_breakout_features()
    results = run_breakout_research(features, validation_split=0.7, min_validation_trades=1)

    sel = results["stop_selection"]
    assert sel["split_date"] is not None, "a time split must exist"
    assert sel["selected_on"] == "train"
    assert sel["train_entries"] + sel["validation_entries"] == len(results["non_overlap_entries"])
    # reported trades are the validation trades of the train-selected stop
    assert len(results["best_fixed_trades"]) == sel["validation_trades"]
    if sel["validation_trades"] > 0:
        split = pd.Timestamp(sel["split_date"])
        assert (pd.to_datetime(results["best_fixed_trades"]["entry_date"]) > split).all()


def test_breakout_eligibility_unvalidated_on_thin_validation():
    """I3: too few held-out trades must be flagged, not passed off as edge."""
    from src.backtest.breakout_research import run_breakout_research

    features = _synthetic_breakout_features()
    results = run_breakout_research(features, validation_split=0.7, min_validation_trades=10_000)
    eligibility = results["eligibility"]
    if not eligibility.empty:
        assert (eligibility["edge_tier"] == "Unvalidated").all()
        assert (~eligibility["eligible"]).all()
