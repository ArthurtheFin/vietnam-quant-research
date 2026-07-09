import os

import numpy as np
import pandas as pd
import pytest

from src.analytics.reversal_quality_score import (
    DEFAULT_SIGNS,
    DEFAULT_WEIGHTS,
    compute_factor_ic,
    derive_factor_weights,
    score_reversal_quality,
)


def test_derive_factor_weights_proportional_to_abs_ic_with_correct_signs():
    mean_ic = {"distance_ma20": -0.4, "return_20d": -0.2, "realized_vol_20d": 0.1}
    weights, signs = derive_factor_weights(mean_ic)
    assert weights == pytest.approx({"distance_ma20": 4 / 7, "return_20d": 2 / 7, "realized_vol_20d": 1 / 7})
    assert signs == {"distance_ma20": -1, "return_20d": -1, "realized_vol_20d": 1}


def test_derive_factor_weights_handles_all_zero_ic_without_dividing_by_zero():
    weights, signs = derive_factor_weights({"a": 0.0, "b": 0.0})
    assert weights == {"a": 0.0, "b": 0.0}
    assert signs == {"a": 1, "b": 1}


def test_compute_factor_ic_recovers_known_negative_relationship():
    n = 12
    distance = np.linspace(-0.1, 0.1, n)
    forward = -distance  # perfectly monotonic decreasing -> Spearman IC = -1
    d0 = pd.Timestamp("2024-01-02")
    d1 = pd.Timestamp("2024-01-03")
    features = pd.concat(
        [
            pd.DataFrame(
                {
                    "symbol": [f"S{i}" for i in range(n)],
                    "date": d0,
                    "distance_ma20": distance,
                    "forward_return_20d": forward,
                }
            ),
            pd.DataFrame(
                {
                    "symbol": [f"S{i}" for i in range(n)],
                    "date": d1,
                    "distance_ma20": distance,
                    "forward_return_20d": forward,
                }
            ),
        ],
        ignore_index=True,
    )
    mean_ic = compute_factor_ic(
        features,
        factors=["distance_ma20"],
        rebalance_period=1,
        require_above_ma200=False,
        min_eligible=5,
    )
    assert mean_ic["distance_ma20"] == pytest.approx(-1.0, abs=1e-9)


def test_compute_factor_ic_on_empty_frame_returns_zeros():
    mean_ic = compute_factor_ic(pd.DataFrame(), factors=["distance_ma20", "return_20d"])
    assert mean_ic == {"distance_ma20": 0.0, "return_20d": 0.0}


def test_score_reversal_quality_ranks_low_raw_values_highest():
    features = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC"],
            "date": pd.to_datetime(["2024-06-20"] * 3),
            "distance_ma20": [-0.05, 0.0, 0.08],  # AAA least overbought
            "return_20d": [-0.02, 0.01, 0.10],  # AAA just pulled back
            "realized_vol_20d": [0.15, 0.20, 0.30],  # AAA calmest
        }
    )
    scored = score_reversal_quality(features)
    ranked = scored.sort_values("reversal_quality_score", ascending=False)["symbol"].tolist()
    assert ranked == ["AAA", "BBB", "CCC"]


def test_score_reversal_quality_treats_missing_factor_value_as_neutral():
    features = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "date": pd.to_datetime(["2024-06-20"] * 2),
            "distance_ma20": [-0.05, 0.05],
            "return_20d": [np.nan, 0.02],
            "realized_vol_20d": [0.10, 0.20],
        }
    )
    scored = score_reversal_quality(features).set_index("symbol")["reversal_quality_score"]
    assert not scored.isna().any()
    # AAA: full weight on distance_ma20 (rank 1.0) + realized_vol_20d (rank 1.0)
    # + neutral 0.5 on the missing return_20d.
    expected_aaa = (DEFAULT_WEIGHTS["distance_ma20"] * 1.0 + DEFAULT_WEIGHTS["return_20d"] * 0.5 + DEFAULT_WEIGHTS["realized_vol_20d"] * 1.0) * 100.0
    assert scored["AAA"] == pytest.approx(expected_aaa)


DATA_PATH = "data/processed/stock_features.parquet"


@pytest.mark.skipif(not os.path.exists(DATA_PATH), reason="requires real data/processed/stock_features.parquet")
def test_full_history_calibration_matches_strategy_research_report():
    from src.data.loaders import read_parquet

    features = read_parquet(DATA_PATH)
    features["date"] = pd.to_datetime(features["date"])
    mean_ic = compute_factor_ic(features)
    weights, signs = derive_factor_weights(mean_ic)
    assert signs == DEFAULT_SIGNS
    for name, expected in DEFAULT_WEIGHTS.items():
        assert weights[name] == pytest.approx(expected, abs=0.01)
