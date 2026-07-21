import numpy as np
import pandas as pd

from src.analytics.benchmark import (
    build_market_proxy_benchmark,
    compare_benchmark_to_proxy,
    summarize_benchmark_alignment,
)


def test_build_market_proxy_benchmark_creates_nav():
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 3 + ["BBB"] * 3,
            "date": pd.date_range("2024-01-01", periods=3, freq="D").tolist() * 2,
            "close": [10, 10.5, 11, 20, 19.5, 20.5],
        }
    )
    proxy = build_market_proxy_benchmark(df)
    assert "market_proxy_return_1d" in proxy.columns
    assert "market_proxy_nav" in proxy.columns
    assert len(proxy) == 3


def test_compare_benchmark_to_proxy_with_benchmark_df():
    price_df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 5 + ["BBB"] * 5,
            "date": pd.date_range("2024-01-01", periods=5, freq="D").tolist() * 2,
            "close": [10, 10.2, 10.1, 10.4, 10.6, 20, 20.3, 20.1, 20.5, 20.6],
        }
    )
    benchmark_df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "close": [100, 101, 102, 101, 103],
        }
    )
    comparison, source = compare_benchmark_to_proxy(price_df, benchmark_df=benchmark_df)
    assert source == "benchmark_df"
    assert "benchmark_return_1d" in comparison.columns
    assert "return_spread" in comparison.columns
    assert comparison["benchmark_return_1d"].notna().sum() >= 1


def test_build_market_proxy_benchmark_ignores_zero_close_instead_of_inf():
    """NV2 regression (docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md): a
    symbol with close==0 (data warmup artifact, real cases: 387 rows in
    clean_daily_ohlcv.parquet, 2020-01/02) followed by a positive close used
    to produce pct_change()==inf, poisoning the cross-sectional mean for
    that whole date. Must now come out as NaN (skipped by mean()), not inf."""
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 3 + ["BBB"] * 3,
            "date": pd.date_range("2024-01-01", periods=3, freq="D").tolist() * 2,
            # BBB: 0 -> 20 is the zero-close-then-recover pattern that produced inf.
            "close": [10, 10.5, 11, 0, 20, 20.5],
        }
    )
    proxy = build_market_proxy_benchmark(df)
    assert np.isfinite(proxy["market_proxy_return_1d"].dropna()).all()
    assert not (proxy["market_proxy_return_1d"] == np.inf).any()


def test_summarize_benchmark_alignment_handles_proxy_only():
    price_df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 4,
            "date": pd.date_range("2024-01-01", periods=4, freq="D"),
            "close": [10, 10.1, 10.3, 10.2],
        }
    )
    comparison, source = compare_benchmark_to_proxy(price_df, benchmark_df=pd.DataFrame())
    summary = summarize_benchmark_alignment(comparison)
    assert source == "market_proxy_only"
    assert summary["benchmark_source"] == "market_proxy_only"
    assert summary["coverage_ratio"] == 0.0
