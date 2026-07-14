from __future__ import annotations

import json

import pandas as pd
import pytest

from scripts.update_prices_daily import run_daily_price_update


class _FakeClient:
    """Stands in for SSIDataClient -- canned DataFrames per symbol, no network
    calls, matching this repo's fake-client testing convention
    (tests/test_update_disclosure_daily.py)."""

    def __init__(self, index_df: pd.DataFrame, ohlc_responses: dict[str, pd.DataFrame], raise_on: dict[str, Exception] | None = None):
        self._index_df = index_df
        self._ohlc_responses = ohlc_responses
        self._raise_on = raise_on or {}
        self.calls: list[str] = []

    def get_daily_index(self, index_id, from_date, to_date, page_size=100, max_pages=2):
        return self._index_df

    def get_daily_ohlc(self, symbol, from_date, to_date, page_size=1000, max_pages=3):
        self.calls.append(symbol)
        if symbol in self._raise_on:
            raise self._raise_on[symbol]
        return self._ohlc_responses.get(symbol, pd.DataFrame())


def _index_df(latest="13/07/2026"):
    return pd.DataFrame({"indexid": ["VNINDEX"], "tradingdate": [latest]})


def _ohlc_df(dates: list[str], closes: list[float], volumes: list[float]):
    return pd.DataFrame({"tradingdate": dates, "close": closes, "volume": volumes})


def _seed_raw_file(raw_dir, symbol, dates: list[str], closes: list[float], volumes: list[float]):
    raw_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"date": pd.to_datetime(dates), "close": closes, "volume": volumes})
    df.to_parquet(raw_dir / f"{symbol}.parquet")


def _seed_manifest(manifest_path, symbols):
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({s: {"status": "ok"} for s in symbols}))


def test_update_appends_new_rows_without_touching_old_history(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    log_path = tmp_path / "log.jsonl"
    status_path = tmp_path / "trading_status.parquet"
    coverage_ratio_path = tmp_path / "coverage_ratios.parquet"
    _seed_raw_file(raw_dir, "VIC", ["2026-07-01", "2026-07-06"], [100.0, 101.0], [1000, 1100])
    _seed_manifest(manifest_path, ["VIC"])

    client = _FakeClient(
        index_df=_index_df("13/07/2026"),
        ohlc_responses={"VIC": _ohlc_df(["06/07/2026", "07/07/2026", "13/07/2026"], [101.0, 102.0, 103.0], [1100, 1200, 1300])},
    )
    summary = run_daily_price_update(["VIC"], client=client, raw_dir=raw_dir, manifest_path=manifest_path, log_path=log_path, status_path=status_path, coverage_ratio_path=coverage_ratio_path, request_sleep=0)

    assert summary["n_updated"] == 1
    assert summary["latest_trading_date"] == "2026-07-13"
    merged = pd.read_parquet(raw_dir / "VIC.parquet")
    assert len(merged) == 4  # 07-01, 07-06, 07-07, 07-13 -- no duplicate for the re-fetched 07-06
    assert merged["date"].max() == pd.Timestamp("2026-07-13")
    # old, untouched-by-refetch row is unchanged
    row_0701 = merged[merged["date"] == pd.Timestamp("2026-07-01")].iloc[0]
    assert row_0701["close"] == 100.0

    manifest = json.loads(manifest_path.read_text())
    assert manifest["VIC"]["date_max"] == "2026-07-13"
    assert manifest["VIC"]["row_count"] == 4

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_second_run_is_a_clean_no_op(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    log_path = tmp_path / "log.jsonl"
    status_path = tmp_path / "trading_status.parquet"
    coverage_ratio_path = tmp_path / "coverage_ratios.parquet"
    _seed_raw_file(raw_dir, "VIC", ["2026-07-06"], [101.0], [1100])
    _seed_manifest(manifest_path, ["VIC"])

    client = _FakeClient(
        index_df=_index_df("13/07/2026"),
        ohlc_responses={"VIC": _ohlc_df(["06/07/2026", "13/07/2026"], [101.0, 103.0], [1100, 1300])},
    )
    run_daily_price_update(["VIC"], client=client, raw_dir=raw_dir, manifest_path=manifest_path, log_path=log_path, status_path=status_path, coverage_ratio_path=coverage_ratio_path, request_sleep=0)
    first_calls = list(client.calls)

    summary2 = run_daily_price_update(["VIC"], client=client, raw_dir=raw_dir, manifest_path=manifest_path, log_path=log_path, status_path=status_path, coverage_ratio_path=coverage_ratio_path, request_sleep=0)

    assert summary2["n_updated"] == 0
    assert summary2["n_already_current"] == 1
    # no new fetch call was made for VIC on the second run
    assert client.calls == first_calls
    merged = pd.read_parquet(raw_dir / "VIC.parquet")
    assert len(merged) == 2  # unchanged from after the first run


def test_long_inactive_symbol_reports_no_new_data_not_updated(tmp_path) -> None:
    """A symbol that hasn't traded in years (e.g. real production case: ASA,
    last trade 2022-01-21) still gets queried each run (it's below the
    target date), but the provider only echoes back the same last session --
    this must be reported as NO_NEW_DATA, not UPDATED, and must not touch
    the file/manifest, so repeated runs are genuinely idempotent (no log
    churn, no spurious manifest rewrite) for symbols that never trade."""
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    log_path = tmp_path / "log.jsonl"
    status_path = tmp_path / "trading_status.parquet"
    coverage_ratio_path = tmp_path / "coverage_ratios.parquet"
    _seed_raw_file(raw_dir, "ASA", ["2022-01-21"], [12500.0], [1363305])
    _seed_manifest(manifest_path, ["ASA"])

    client = _FakeClient(
        index_df=_index_df("13/07/2026"),
        # Provider echoes back only the existing last session -- no new data.
        ohlc_responses={"ASA": _ohlc_df(["21/01/2022"], [12500.0], [1363305])},
    )
    summary1 = run_daily_price_update(["ASA"], client=client, raw_dir=raw_dir, manifest_path=manifest_path, log_path=log_path, status_path=status_path, coverage_ratio_path=coverage_ratio_path, request_sleep=0)
    manifest_after_first = json.loads(manifest_path.read_text())
    summary2 = run_daily_price_update(["ASA"], client=client, raw_dir=raw_dir, manifest_path=manifest_path, log_path=log_path, status_path=status_path, coverage_ratio_path=coverage_ratio_path, request_sleep=0)

    assert summary1["n_updated"] == 0
    assert summary1["n_no_new_data"] == 1
    assert summary2["n_updated"] == 0
    assert summary2["n_no_new_data"] == 1
    # manifest untouched by the NO_NEW_DATA path (no daily_update_at added)
    assert "daily_update_at" not in manifest_after_first.get("ASA", {})
    merged = pd.read_parquet(raw_dir / "ASA.parquet")
    assert len(merged) == 1


def test_fetch_error_is_logged_and_other_symbols_still_proceed(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    log_path = tmp_path / "log.jsonl"
    status_path = tmp_path / "trading_status.parquet"
    coverage_ratio_path = tmp_path / "coverage_ratios.parquet"
    _seed_raw_file(raw_dir, "HPG", ["2026-07-06"], [23000.0], [1_000_000])
    _seed_raw_file(raw_dir, "MWG", ["2026-07-06"], [78000.0], [500_000])
    _seed_manifest(manifest_path, ["HPG", "MWG"])

    client = _FakeClient(
        index_df=_index_df("13/07/2026"),
        ohlc_responses={"MWG": _ohlc_df(["13/07/2026"], [79000.0], [600_000])},
        raise_on={"HPG": RuntimeError("provider error")},
    )
    summary = run_daily_price_update(["HPG", "MWG"], client=client, raw_dir=raw_dir, manifest_path=manifest_path, log_path=log_path, status_path=status_path, coverage_ratio_path=coverage_ratio_path, request_sleep=0)

    assert summary["n_fetch_errors"] == 1
    assert summary["fetch_error_symbols"] == ["HPG"]
    assert summary["n_updated"] == 1  # MWG still went through
    hpg = pd.read_parquet(raw_dir / "HPG.parquet")
    assert len(hpg) == 1  # untouched


def test_quality_flag_on_outlier_return(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    log_path = tmp_path / "log.jsonl"
    status_path = tmp_path / "trading_status.parquet"
    coverage_ratio_path = tmp_path / "coverage_ratios.parquet"
    _seed_raw_file(raw_dir, "VIC", ["2026-07-06"], [100.0], [1000])
    _seed_manifest(manifest_path, ["VIC"])

    client = _FakeClient(
        index_df=_index_df("13/07/2026"),
        # 100 -> 200 is a +100% jump, well past the 20% outlier threshold
        ohlc_responses={"VIC": _ohlc_df(["06/07/2026", "13/07/2026"], [100.0, 200.0], [1000, 1000])},
    )
    summary = run_daily_price_update(["VIC"], client=client, raw_dir=raw_dir, manifest_path=manifest_path, log_path=log_path, status_path=status_path, coverage_ratio_path=coverage_ratio_path, request_sleep=0)

    assert summary["quality_flagged_symbols"] == ["VIC"]
    manifest = json.loads(manifest_path.read_text())
    assert any("OUTLIER_RETURN_GT_20PCT" in f for f in manifest["VIC"]["quality_flags"])
    # flagged, but NOT blocked -- the row is still appended
    merged = pd.read_parquet(raw_dir / "VIC.parquet")
    assert len(merged) == 2


def test_aborts_cleanly_when_latest_trading_date_undetectable(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    log_path = tmp_path / "log.jsonl"
    status_path = tmp_path / "trading_status.parquet"
    coverage_ratio_path = tmp_path / "coverage_ratios.parquet"
    _seed_raw_file(raw_dir, "VIC", ["2026-07-06"], [100.0], [1000])
    _seed_manifest(manifest_path, ["VIC"])

    client = _FakeClient(index_df=pd.DataFrame(), ohlc_responses={})
    summary = run_daily_price_update(["VIC"], client=client, raw_dir=raw_dir, manifest_path=manifest_path, log_path=log_path, status_path=status_path, coverage_ratio_path=coverage_ratio_path, request_sleep=0)

    assert summary["status"] == "ABORTED_NO_LATEST_DATE"
    assert client.calls == []  # never attempted a per-symbol fetch
    assert not status_path.exists()  # aborted before reaching the trading_status update


def test_run_updates_trading_status_table(tmp_path) -> None:
    """The trading_status table update (audit PATH_TO_100.md Universe/
    Eligibility item) must be isolated to the given status_path, not the
    real project data/full_history_v2/trading_status.parquet -- and must
    cover every symbol's current gap, not just ones fetched this run."""
    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.json"
    log_path = tmp_path / "log.jsonl"
    status_path = tmp_path / "trading_status.parquet"
    coverage_ratio_path = tmp_path / "coverage_ratios.parquet"
    _seed_raw_file(raw_dir, "VIC", ["2026-07-06"], [100.0], [1000])
    _seed_raw_file(raw_dir, "ASA", ["2022-01-21"], [12500.0], [1363305])
    _seed_manifest(manifest_path, ["VIC", "ASA"])

    client = _FakeClient(
        index_df=_index_df("13/07/2026"),
        ohlc_responses={
            "VIC": _ohlc_df(["06/07/2026", "13/07/2026"], [100.0, 103.0], [1000, 1300]),
            "ASA": _ohlc_df(["21/01/2022"], [12500.0], [1363305]),
        },
    )
    summary = run_daily_price_update(["VIC", "ASA"], client=client, raw_dir=raw_dir, manifest_path=manifest_path, log_path=log_path, status_path=status_path, coverage_ratio_path=coverage_ratio_path, request_sleep=0)

    assert summary["trading_status_new_rows"] == 2
    status = pd.read_parquet(status_path).set_index("symbol")
    assert status.loc["VIC", "status"] == "ACTIVE"
    assert status.loc["ASA", "status"] == "INACTIVE_LONG"
