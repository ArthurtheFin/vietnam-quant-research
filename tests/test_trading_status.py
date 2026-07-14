from __future__ import annotations

import pandas as pd
import pytest

from src.validation.trading_status import (
    classify_trading_status,
    compute_coverage_ratio,
    compute_current_gaps,
    excluded_symbols_by_status,
    latest_trading_status,
    low_coverage_symbols,
    refresh_coverage_ratios,
    status_as_of,
    update_trading_status_table,
)


def _write_symbol(raw_dir, symbol, dates):
    raw_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": pd.to_datetime(dates), "close": [100.0] * len(dates)}).to_parquet(raw_dir / f"{symbol}.parquet")


def test_classify_trading_status_thresholds():
    assert classify_trading_status(0) == "ACTIVE"
    assert classify_trading_status(2) == "ACTIVE"
    assert classify_trading_status(3) == "STALE_SHORT"
    assert classify_trading_status(10) == "STALE_SHORT"
    assert classify_trading_status(11) == "INACTIVE_LONG"
    assert classify_trading_status(1634) == "INACTIVE_LONG"


def test_compute_current_gaps_from_raw_tier(tmp_path):
    raw_dir = tmp_path / "raw"
    _write_symbol(raw_dir, "AAA", ["2026-07-13"])
    _write_symbol(raw_dir, "BBB", ["2026-07-06"])
    _write_symbol(raw_dir, "CCC", ["2022-01-21"])

    gaps = compute_current_gaps(raw_dir, pd.Timestamp("2026-07-13"))
    gaps = gaps.set_index("symbol")

    assert gaps.loc["AAA", "status"] == "ACTIVE"
    assert gaps.loc["BBB", "gap_days"] == 7
    assert gaps.loc["BBB", "status"] == "STALE_SHORT"
    assert gaps.loc["CCC", "status"] == "INACTIVE_LONG"


def test_update_appends_only_on_status_change(tmp_path):
    status_path = tmp_path / "trading_status.parquet"

    day1 = pd.DataFrame([
        {"symbol": "AAA", "last_trading_date": pd.Timestamp("2026-07-13"), "gap_days": 0, "status": "ACTIVE"},
        {"symbol": "BBB", "last_trading_date": pd.Timestamp("2026-07-06"), "gap_days": 7, "status": "STALE_SHORT"},
    ])
    result1 = update_trading_status_table(day1, status_path=status_path, run_at=pd.Timestamp("2026-07-13", tz="UTC"))
    assert result1 == {"n_new_rows": 2, "n_unchanged": 0}

    # Day 2: AAA's status is unchanged (still ACTIVE, just a later date) --
    # must NOT append a new row. BBB's status changed (now INACTIVE_LONG) --
    # must append.
    day2 = pd.DataFrame([
        {"symbol": "AAA", "last_trading_date": pd.Timestamp("2026-07-14"), "gap_days": 0, "status": "ACTIVE"},
        {"symbol": "BBB", "last_trading_date": pd.Timestamp("2026-07-06"), "gap_days": 20, "status": "INACTIVE_LONG"},
    ])
    result2 = update_trading_status_table(day2, status_path=status_path, run_at=pd.Timestamp("2026-07-14", tz="UTC"))
    assert result2 == {"n_new_rows": 1, "n_unchanged": 1}

    full = pd.read_parquet(status_path)
    assert len(full) == 3  # 2 from day1 + 1 (BBB transition) from day2

    current = latest_trading_status(status_path)
    current = current.set_index("symbol")
    assert current.loc["AAA", "status"] == "ACTIVE"
    assert current.loc["BBB", "status"] == "INACTIVE_LONG"


def test_status_as_of_reconstructs_point_in_time(tmp_path):
    status_path = tmp_path / "trading_status.parquet"
    day1 = pd.DataFrame([{"symbol": "AAA", "last_trading_date": pd.Timestamp("2026-01-01"), "gap_days": 0, "status": "ACTIVE"}])
    update_trading_status_table(day1, status_path=status_path, run_at=pd.Timestamp("2026-01-01", tz="UTC"))

    day2 = pd.DataFrame([{"symbol": "AAA", "last_trading_date": pd.Timestamp("2026-01-01"), "gap_days": 20, "status": "INACTIVE_LONG"}])
    update_trading_status_table(day2, status_path=status_path, run_at=pd.Timestamp("2026-06-01", tz="UTC"))

    # As of a date BEFORE the transition, AAA must still read ACTIVE.
    before = status_as_of(pd.Timestamp("2026-03-01"), status_path=status_path)
    assert before.set_index("symbol").loc["AAA", "status"] == "ACTIVE"

    # As of a date AFTER the transition, AAA must read INACTIVE_LONG.
    after = status_as_of(pd.Timestamp("2026-07-01"), status_path=status_path)
    assert after.set_index("symbol").loc["AAA", "status"] == "INACTIVE_LONG"


def test_excluded_symbols_by_status_returns_only_inactive_long(tmp_path):
    status_path = tmp_path / "trading_status.parquet"
    current = pd.DataFrame([
        {"symbol": "AAA", "last_trading_date": pd.Timestamp("2026-07-13"), "gap_days": 0, "status": "ACTIVE"},
        {"symbol": "BBB", "last_trading_date": pd.Timestamp("2026-07-06"), "gap_days": 7, "status": "STALE_SHORT"},
        {"symbol": "CCC", "last_trading_date": pd.Timestamp("2022-01-21"), "gap_days": 1634, "status": "INACTIVE_LONG"},
    ])
    update_trading_status_table(current, status_path=status_path, run_at=pd.Timestamp("2026-07-13", tz="UTC"))

    excluded = excluded_symbols_by_status(status_path=status_path)
    assert excluded == {"CCC"}


def test_missing_status_file_returns_empty_no_error(tmp_path):
    status_path = tmp_path / "does_not_exist.parquet"
    assert latest_trading_status(status_path).empty
    assert excluded_symbols_by_status(status_path) == set()


def test_compute_coverage_ratio_full_and_zero_coverage(tmp_path):
    raw_dir = tmp_path / "raw"
    latest = pd.Timestamp("2026-07-13")
    # AAA trades every weekday over a wider raw range (a superset of the 60
    # *expected* holiday-filtered sessions, since holidays reach further
    # back than 60 raw business days) -> ratio should be 1.0.
    full_dates = pd.bdate_range(end=latest, periods=90)
    _write_symbol(raw_dir, "AAA", [d.strftime("%Y-%m-%d") for d in full_dates])
    # BBB hasn't traded in years -> ratio should be 0.0.
    _write_symbol(raw_dir, "BBB", ["2022-01-21"])

    coverage = compute_coverage_ratio(raw_dir, latest, window_sessions=60).set_index("symbol")
    assert coverage.loc["AAA", "coverage_ratio"] == pytest.approx(1.0)
    assert coverage.loc["BBB", "coverage_ratio"] == 0.0


def test_compute_coverage_ratio_respects_tet_holiday(tmp_path):
    """v2 convention: a no-row day is a no-trade day, but Tet closures must
    not count against a symbol at all (config/vn_market_holidays.csv is
    already Tet-aware from this session's earlier calendar work)."""
    raw_dir = tmp_path / "raw"
    # A symbol that trades every session except the real 2026 Tet week
    # (2026-02-16..20) should show full coverage over a window spanning it.
    dates = [d for d in pd.bdate_range("2026-01-01", "2026-03-01") if not (pd.Timestamp("2026-02-16") <= d <= pd.Timestamp("2026-02-20"))]
    _write_symbol(raw_dir, "AAA", [d.strftime("%Y-%m-%d") for d in dates])

    latest = pd.Timestamp("2026-03-01")
    coverage = compute_coverage_ratio(raw_dir, latest, window_sessions=30).set_index("symbol")
    assert coverage.loc["AAA", "coverage_ratio"] == pytest.approx(1.0)


def test_refresh_and_low_coverage_symbols_roundtrip(tmp_path):
    raw_dir = tmp_path / "raw"
    coverage_path = tmp_path / "coverage_ratios.parquet"
    latest = pd.Timestamp("2026-07-13")
    full_dates = pd.bdate_range(end=latest, periods=90)
    _write_symbol(raw_dir, "AAA", [d.strftime("%Y-%m-%d") for d in full_dates])
    _write_symbol(raw_dir, "BBB", ["2022-01-21"])

    refresh_coverage_ratios(raw_dir, latest, path=coverage_path, window_sessions=60)

    assert coverage_path.exists()
    low = low_coverage_symbols(path=coverage_path, min_coverage_ratio=0.30)
    assert low == {"BBB"}


def test_low_coverage_symbols_missing_snapshot_returns_empty(tmp_path):
    assert low_coverage_symbols(path=tmp_path / "does_not_exist.parquet") == set()
