from pathlib import Path

import numpy as np
import pandas as pd

from src.data.benchmark import build_benchmark_file, prepare_index_features


def test_prepare_index_features_adds_returns():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=6, freq="D"),
            "symbol": ["VNINDEX"] * 6,
            "close": [100, 101, 102, 104, 103, 105],
            "volume": [1, 1, 1, 1, 1, 1],
            "value": [1, 1, 1, 1, 1, 1],
        }
    )
    features = prepare_index_features(df, horizons=[1, 5])
    assert "return_1d" in features.columns
    assert "forward_return_5d" in features.columns
    assert features["symbol"].iloc[0] == "VNINDEX"


def test_build_benchmark_file_saves_selected_index(tmp_path: Path):
    raw_dir = tmp_path / "raw_index"
    raw_dir.mkdir(parents=True)
    output_path = tmp_path / "benchmark_vnindex.parquet"

    raw_df = pd.DataFrame(
        {
            "tradingdate": pd.date_range("2024-01-01", periods=8, freq="D"),
            "indexcode": ["VNINDEX"] * 8,
            "indexvalue": [100, 101, 102, 103, 104, 105, 106, 107],
            "allqty": [1000] * 8,
            "allvalue": [100000] * 8,
        }
    )
    raw_df.to_parquet(raw_dir / "VNINDEX.parquet", index=False)

    benchmark = build_benchmark_file(
        index_id="VNINDEX",
        raw_dir=raw_dir,
        output_path=output_path,
        horizons=[1, 5],
    )

    assert output_path.exists()
    assert not benchmark.empty
    assert set(["symbol", "date", "close", "return_1d", "forward_return_5d"]).issubset(benchmark.columns)
    assert benchmark["symbol"].eq("VNINDEX").all()


def test_prepare_index_features_repairs_scaled_index_history():
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=4, freq="D"),
            "symbol": ["VNINDEX"] * 4,
            "close": [100000.0, 100500.0, 1012.0, 1020.0],
            "ratio_change": [np.nan, 0.005, 0.0069, 0.0079],
            "volume": [1, 1, 1, 1],
            "value": [1, 1, 1, 1],
        }
    )

    features = prepare_index_features(df, horizons=[1])

    repaired = features["return_1d"].dropna()
    assert not repaired.empty
    assert repaired.abs().max() < 0.05
    assert features["close"].iloc[-1] > features["close"].iloc[0]
