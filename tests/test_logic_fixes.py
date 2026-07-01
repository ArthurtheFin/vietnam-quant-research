import pandas as pd

from src.data.validators import filter_primary_equity_symbols
from src.data.fetch_daily import update_symbol_history
from src.models.monte_carlo import monte_carlo_trade_stats
from src.models.probability import train_logistic_probability_model
from src.models.regime import classify_market_regime
from src.models.risk_model import position_size_by_risk
from src.models.similarity import find_similar_states


def test_find_similar_states_uses_only_past_rows():
    df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "feature_1": [0.1, 0.2, 0.3],
            "feature_2": [1.0, 1.1, 1.2],
        }
    )

    similar = find_similar_states(df, df.iloc[2], ["feature_1", "feature_2"], top_n=10)

    assert len(similar) == 2
    assert similar["date"].max() < pd.Timestamp("2024-01-03")


def test_monte_carlo_expected_return_respects_first_exit():
    paths = pd.DataFrame([[95, 110], [108, 111]]).to_numpy(dtype=float)

    stats = monte_carlo_trade_stats(paths, entry=100, stop=97, target=105)

    assert round(stats["p_target_before_stop"], 4) == 0.5
    assert round(stats["p_stop_before_target"], 4) == 0.5
    assert round(stats["expected_return"], 4) == 0.01


def test_position_size_by_risk_caps_to_max_position_pct():
    sizing = position_size_by_risk(nav=100_000, entry=100, stop=99, risk_per_trade=0.02, max_position_pct=0.25)

    assert sizing["quantity"] == 250
    assert sizing["position_value"] == 25_000
    assert sizing["capped_by_max_position"] is True




def test_market_regime_uses_generic_volatility_percentile():
    regime = classify_market_regime(
        pd.Series(
            {
                "pct_above_ma50": 0.7,
                "advance_decline_ratio": 1.4,
                "volatility_percentile": 0.4,
            }
        )
    )

    assert regime == "Neutral"


def test_probability_model_uses_chronological_split_by_default():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=8, freq="D"),
            "feature_1": [0, 1, 0, 1, 0, 1, 0, 1],
            "target": [0, 1, 0, 1, 0, 1, 0, 1],
        }
    )

    _, metrics = train_logistic_probability_model(df, ["feature_1"], "target", test_size=0.25)

    assert metrics["split_method"] == "time"
    assert metrics["train_rows"] == 6
    assert metrics["test_rows"] == 2


def test_update_symbol_history_refreshes_recent_days(monkeypatch):
    old = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "close": [10.0, 10.5, 11.0],
        }
    )
    refreshed = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "close": [10.6, 11.1, 11.4],
        }
    )

    monkeypatch.setattr("src.data.fetch_daily.read_parquet", lambda path: old.copy())
    monkeypatch.setattr("src.data.fetch_daily.save_parquet", lambda df, path: path)
    monkeypatch.setattr("src.data.fetch_daily.Path.exists", lambda self: True)

    calls = {}

    def fake_fetch_symbol_history(**kwargs):
        calls["start_date"] = kwargs["start_date"]
        return refreshed.copy()

    monkeypatch.setattr("src.data.fetch_daily.fetch_symbol_history", fake_fetch_symbol_history)

    combined = update_symbol_history(
        client=object(),
        symbol="AAA",
        start_date="2024-01-01",
        end_date="2024-01-04",
        refresh_recent_days=2,
    )

    assert calls["start_date"] == "2024-01-02"
    assert combined["date"].max() == pd.Timestamp("2024-01-04")
    assert float(combined.loc[combined["date"] == pd.Timestamp("2024-01-03"), "close"].iloc[0]) == 11.1


def test_filter_primary_equity_symbols_removes_warrants_and_keeps_three_char_symbols():
    df = pd.DataFrame(
        {
            "symbol": ["AAA", "A32", "CFPT2529", "VNINDEX", None],
            "value": [1, 2, 3, 4, 5],
        }
    )

    filtered = filter_primary_equity_symbols(df)

    assert filtered["symbol"].tolist() == ["AAA", "A32"]
