import pandas as pd

from src.analytics.entropy import (
    add_entropy_features,
    build_market_entropy_profile,
    classify_entropy_regime,
    detect_entropy_regime_shift,
    rolling_shannon_entropy,
)


def test_rolling_shannon_entropy_returns_normalized_series():
    series = pd.Series([0.01, -0.02, 0.015, -0.01, 0.0, 0.02, -0.015, 0.005] * 10)
    entropy = rolling_shannon_entropy(series, window=20, n_bins=10)
    assert len(entropy) == len(series)
    assert entropy.dropna().between(0, 1).all()


def test_add_entropy_features_creates_regime_columns():
    dates = pd.date_range("2024-01-01", periods=80, freq="D")
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 80 + ["BBB"] * 80,
            "date": list(dates) * 2,
            "close": list(range(100, 180)) + list(range(50, 130)),
        }
    )
    out = add_entropy_features(df, windows=[21, 42])
    assert "entropy_21d" in out.columns
    assert "entropy_42d" in out.columns
    assert "entropy_regime" in out.columns
    assert "entropy_regime_shift" in out.columns


def test_market_entropy_profile_builds_vietnam_style_proxy():
    dates = pd.date_range("2024-01-01", periods=90, freq="D")
    rows = []
    for symbol, base in [("AAA", 100.0), ("BBB", 60.0), ("CCC", 40.0)]:
        for i, date in enumerate(dates):
            rows.append({"symbol": symbol, "date": date, "close": base + i + (i % 5)})
    df = pd.DataFrame(rows)
    out = build_market_entropy_profile(df, windows=[21, 42])
    assert "market_proxy_return_1d" in out.columns
    assert "market_entropy_21d" in out.columns
    assert "market_entropy_regime" in out.columns
    assert out["market_entropy_21d"].notna().sum() > 0


def test_entropy_regime_and_shift_labels():
    entropy = pd.Series([0.2, 0.3, 0.5, 0.8, 0.78, 0.55, 0.25])
    regimes = classify_entropy_regime(entropy, low_threshold=0.35, high_threshold=0.70)
    shifts = detect_entropy_regime_shift(entropy, lookback=1, shift_threshold=0.15)
    assert list(regimes.iloc[[0, 2, 3]]) == ["Structured", "Transitional", "Chaotic"]
    assert "Entropy Expansion" in set(shifts)
    assert "Entropy Compression" in set(shifts)
