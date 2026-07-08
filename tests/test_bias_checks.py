"""Tests for automated (not manual-notebook-only) bias checks (audit D4)."""
from __future__ import annotations

import pandas as pd

from src.data.loaders import save_parquet
from src.validation.bias_checks import run_bias_checks


def test_run_bias_checks_reports_missing_setup_signals(tmp_path) -> None:
    result = run_bias_checks(tmp_path)
    assert result["ran"] is False
    assert "not found" in result["reason"]


def test_run_bias_checks_flags_forward_columns_present(tmp_path) -> None:
    df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "forward_return_5d": [0.05, 0.03],
        }
    )
    save_parquet(df, tmp_path / "data/signals/setup_signals.parquet")

    result = run_bias_checks(tmp_path)
    assert result["ran"] is True
    assert result["target"] == "data/signals/setup_signals.parquet"
    assert result["passed"] is False
    assert "forward_return_5d" in result["details"]


def test_run_bias_checks_passes_when_no_forward_columns(tmp_path) -> None:
    df = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA"],
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "breakout_20d": [True, False],
        }
    )
    save_parquet(df, tmp_path / "data/signals/setup_signals.parquet")

    result = run_bias_checks(tmp_path)
    assert result["ran"] is True
    assert result["passed"] is True
