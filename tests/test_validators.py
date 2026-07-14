from __future__ import annotations

import pandas as pd

from src.data.validators import validate_ohlcv


def _base_rows(n=5, start="2026-01-05"):
    dates = pd.bdate_range(start, periods=n)
    return pd.DataFrame({
        "symbol": ["AAA"] * n,
        "market": ["HOSE"] * n,
        "date": dates,
        "open": [100.0] * n,
        "high": [105.0] * n,
        "low": [95.0] * n,
        "close": [102.0] * n,
        "volume": [1000.0] * n,
    })


def test_clean_data_has_zero_new_check_violations():
    df = _base_rows()
    checks = validate_ohlcv(df)
    assert checks["high_below_open_or_close"] == 0
    assert checks["low_above_open_or_close"] == 0
    assert checks["symbols_with_calendar_gap"] == 0
    assert checks["dtype_schema_drift"] == {}


def test_high_below_close_is_caught():
    df = _base_rows()
    df.loc[2, "high"] = 90.0  # below both open (100) and close (102)
    checks = validate_ohlcv(df)
    assert checks["high_below_open_or_close"] == 1
    # not caught by the old high<low check (90 > low=95 is false actually;
    # use a value that passes high>=low but still violates high>=close)
    assert checks["invalid_high_low"] == 1  # 90 < 95 low, so this also trips -- expected overlap


def test_high_below_close_but_above_low_only_caught_by_new_check():
    df = _base_rows()
    df.loc[2, "high"] = 101.0  # >= low (95), but < close (102) -- old check misses this
    checks = validate_ohlcv(df)
    assert checks["invalid_high_low"] == 0
    assert checks["high_below_open_or_close"] == 1


def test_low_above_open_is_caught():
    df = _base_rows()
    df.loc[3, "low"] = 101.0  # above both open (100) and close (102)... wait must be below min, so make it above min(open,close)=100
    checks = validate_ohlcv(df)
    assert checks["low_above_open_or_close"] == 1


def test_calendar_gap_detected_for_missing_mid_history_block():
    dates = list(pd.bdate_range("2026-01-05", periods=5)) + list(pd.bdate_range("2026-03-01", periods=5))
    df = pd.DataFrame({
        "symbol": ["AAA"] * 10,
        "market": ["HOSE"] * 10,
        "date": dates,
        "open": [100.0] * 10,
        "high": [105.0] * 10,
        "low": [95.0] * 10,
        "close": [102.0] * 10,
        "volume": [1000.0] * 10,
    })
    checks = validate_ohlcv(df)
    assert checks["symbols_with_calendar_gap"] == 1
    assert "AAA" in checks["calendar_gap_symbols"]


def test_calendar_gap_not_flagged_for_tet_holiday_closure():
    """The gap detector must not flag the real Tet Nguyen Dan closure as an
    abnormal data gap -- config/vn_market_holidays.csv already accounts for
    it (audit/PATH_TO_100.md Universe/Eligibility item)."""
    pre_tet = list(pd.bdate_range("2026-02-01", "2026-02-13"))
    post_tet = list(pd.bdate_range("2026-02-23", "2026-03-06"))
    dates = pre_tet + post_tet
    df = pd.DataFrame({
        "symbol": ["AAA"] * len(dates),
        "market": ["HOSE"] * len(dates),
        "date": dates,
        "open": [100.0] * len(dates),
        "high": [105.0] * len(dates),
        "low": [95.0] * len(dates),
        "close": [102.0] * len(dates),
        "volume": [1000.0] * len(dates),
    })
    checks = validate_ohlcv(df)
    assert checks["symbols_with_calendar_gap"] == 0


def test_return_outlier_beyond_price_band_detected():
    dates = pd.bdate_range("2026-01-05", periods=3)
    df = pd.DataFrame({
        "symbol": ["AAA"] * 3,
        "market": ["HOSE"] * 3,  # HOSE band = 7%
        "date": dates,
        "open": [100.0, 100.0, 150.0],
        "high": [105.0, 105.0, 155.0],
        "low": [95.0, 95.0, 145.0],
        "close": [100.0, 150.0, 151.0],  # +50% day 2 -- well beyond 7% band
        "volume": [1000.0] * 3,
    })
    checks = validate_ohlcv(df)
    assert checks["return_outliers_beyond_price_band"] == 1


def test_dtype_schema_drift_detects_non_numeric_garbage():
    df = _base_rows()
    df["close"] = df["close"].astype(object)
    df.loc[1, "close"] = "not_a_number"
    checks = validate_ohlcv(df)
    assert checks["dtype_schema_drift"] == {"close": 1}


def test_dtype_schema_drift_ignores_genuine_missing_values():
    df = _base_rows()
    df.loc[1, "close"] = None
    checks = validate_ohlcv(df)
    # a genuinely missing value is not "drift" -- already counted by missing_close
    assert checks["dtype_schema_drift"] == {}
    assert checks["missing_close"] == 1


def test_missing_columns_still_reported_with_new_checks_absent():
    df = pd.DataFrame({"symbol": ["AAA"], "date": [pd.Timestamp("2026-01-05")]})
    checks = validate_ohlcv(df)
    assert "open" in checks["missing_columns"]
    assert checks["high_below_open_or_close"] is None
    assert checks["return_outliers_beyond_price_band"] is None
