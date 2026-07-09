"""Tests for the upgraded market regime detector: crash severity, breakout
signal, and the index_above_ma50/200 data-feed bug fix (audit follow-up,
requested strategy research)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.regime import (
    add_index_trend_features,
    add_market_regime,
    classify_breakout_signal,
    classify_crash_severity,
    classify_market_regime,
)


def _make_benchmark(prices: list[float], start: str = "2022-01-01") -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=len(prices))
    return pd.DataFrame({"date": dates, "close": prices})


def test_crash_severity_detects_deep_drawdown():
    """A 2022-style deep drawdown (-29% off a 60d high) must classify as Crash,
    not just the generic 'Risk-off' bucket that also holds ordinary chop."""
    prices = [100.0] * 60 + [70.0] * 30  # sharp drop, holds low (real drawdown)
    benchmark = _make_benchmark(prices)
    market_features = pd.DataFrame({"date": benchmark["date"]})

    out = add_market_regime(market_features, benchmark=benchmark, drawdown_window=60)
    tail = out.iloc[-1]
    assert tail["crash_severity"] == "Crash"
    assert tail["index_drawdown_pct"] <= -0.20


def test_crash_severity_does_not_fire_on_ordinary_correction():
    """A mild -12% pullback must classify as Correction, not Crash -- these
    must be distinguishable (2022 vs 2023-2026 in the real data)."""
    prices = [100.0] * 60 + [88.0] * 30  # -12% drawdown
    benchmark = _make_benchmark(prices)
    market_features = pd.DataFrame({"date": benchmark["date"]})

    out = add_market_regime(market_features, benchmark=benchmark, drawdown_window=60)
    tail = out.iloc[-1]
    assert tail["crash_severity"] == "Correction"


def test_crash_severity_normal_near_highs():
    prices = [100.0 + i * 0.1 for i in range(90)]  # grinding new highs
    benchmark = _make_benchmark(prices)
    market_features = pd.DataFrame({"date": benchmark["date"]})

    out = add_market_regime(market_features, benchmark=benchmark, drawdown_window=60)
    assert out.iloc[-1]["crash_severity"] == "Normal"


def test_breakout_signal_requires_near_high_and_breadth_confirmation():
    prices = [100.0 + i * 0.15 for i in range(90)]  # near new highs
    benchmark = _make_benchmark(prices)
    market_features = pd.DataFrame({
        "date": benchmark["date"],
        "pct_above_ma50": [0.65] * 90,
        "advance_decline_ratio": [1.5] * 90,
        "up_down_volume_ratio": [1.4] * 90,
    })

    out = add_market_regime(market_features, benchmark=benchmark, drawdown_window=60)
    assert out.iloc[-1]["breakout_signal"] == "Breakout"


def test_breakout_signal_absent_without_breadth_confirmation():
    """Being near highs alone (weak breadth/AD/volume) must NOT count as a breakout."""
    prices = [100.0 + i * 0.15 for i in range(90)]
    benchmark = _make_benchmark(prices)
    market_features = pd.DataFrame({
        "date": benchmark["date"],
        "pct_above_ma50": [0.40] * 90,
        "advance_decline_ratio": [0.9] * 90,
        "up_down_volume_ratio": [0.8] * 90,
    })

    out = add_market_regime(market_features, benchmark=benchmark, drawdown_window=60)
    assert out.iloc[-1]["breakout_signal"] == "Normal"


def test_index_above_ma_bug_fix_makes_risk_on_reachable():
    """Before the fix, index_above_ma50/200 were always False (calculate_
    market_breadth never touches the index price), capping the legacy score
    at 3/5 and making 'Risk-on' structurally unreachable. With a real
    sustained uptrend benchmark, Risk-on must now be reachable."""
    prices = [100.0 + i * 0.3 for i in range(260)]  # long, strong uptrend
    benchmark = _make_benchmark(prices)
    market_features = pd.DataFrame({
        "date": benchmark["date"],
        "pct_above_ma50": [0.70] * 260,
        "advance_decline_ratio": [1.5] * 260,
        "volatility_percentile": [0.3] * 260,
    })

    out = add_market_regime(market_features, benchmark=benchmark)
    assert (out["index_above_ma50"].tail(30)).all()
    assert (out["index_above_ma200"].tail(30)).all()
    assert "Risk-on" in set(out["market_regime"].tail(30))


def test_market_regime_backward_compatible_without_benchmark():
    """No benchmark provided (old call signature) -> same behavior as before:
    index_above_ma50/200 default False, crash_severity/breakout_signal degrade
    gracefully instead of raising."""
    market_features = pd.DataFrame({
        "date": pd.bdate_range("2024-01-01", periods=10),
        "pct_above_ma50": [0.7] * 10,
        "advance_decline_ratio": [1.4] * 10,
        "volatility_percentile": [0.4] * 10,
    })
    out = add_market_regime(market_features)
    assert (out["index_above_ma50"] == False).all()  # noqa: E712
    assert set(out["crash_severity"]) == {"Unknown"}
    assert set(out["breakout_signal"]) == {"Normal"}
    assert set(out["market_regime"]) == {"Neutral"}  # score capped at 3, same as before the fix


def test_classify_market_regime_unchanged_signature_and_behavior():
    """Direct call (no benchmark involved) must match the pre-upgrade test
    fixture exactly -- this is the existing test_logic_fixes.py case."""
    regime = classify_market_regime(
        pd.Series({
            "pct_above_ma50": 0.7,
            "advance_decline_ratio": 1.4,
            "volatility_percentile": 0.4,
        })
    )
    assert regime == "Neutral"
