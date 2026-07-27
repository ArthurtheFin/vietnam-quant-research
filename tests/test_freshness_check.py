from __future__ import annotations

import pandas as pd

from src.portfolio.input_resolver import load_default_portfolio_candidates
from src.utils.pipeline_io import (
    resolve_watchlist_source,
    validate_pipeline_metadata,
    validate_portfolio_stack_metadata,
)
from src.validation.freshness_check import evaluate_freshness


def _write_frame(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_all_mock_dated_files(tmp_path, rows):
    dated_artifacts = [
        "data/processed/clean_daily_ohlcv.parquet",
        "data/processed/stock_features.parquet",
        "data/signals/setup_signals.parquet",
        "data/signals/alpha_scores.parquet",
        "data/processed/benchmark_vnindex.parquet",
        "data/signals/breakout_20d_trade_cards.parquet",
        "data/signals/stealth_accumulation_latest.parquet",
        "data/signals/meta_ranking.parquet",
        "data/signals/final_watchlist.parquet",
        "data/output/research_candidates.parquet",
        "data/output/trading_watchlist.parquet",
        "data/output/client_ready_watchlist.parquet",
    ]
    for artifact in dated_artifacts:
        _write_frame(tmp_path / artifact, rows)


def test_freshness_check_warns_on_stale_benchmark(tmp_path) -> None:
    _write_frame(
        tmp_path / "data/processed/clean_daily_ohlcv.parquet",
        [{"symbol": "AAA", "date": "2026-06-30", "close": 10.0}],
    )
    _write_frame(
        tmp_path / "data/processed/stock_features.parquet",
        [{"symbol": "AAA", "date": "2026-06-30", "close": 10.0}],
    )
    _write_frame(
        tmp_path / "data/processed/benchmark_vnindex.parquet",
        [{"symbol": "VNINDEX", "date": "2026-06-28", "close": 1000.0}],
    )

    report = evaluate_freshness(base_dir=tmp_path, now=pd.Timestamp("2026-07-02 20:00"))

    assert report["status"] in {"WARNING", "ERROR"}
    assert any("benchmark_vnindex is stale" in message for message in report["warnings"] + report["errors"])


def test_watchlist_source_falls_back_to_trading_watchlist(tmp_path) -> None:
    _write_frame(
        tmp_path / "data/output/trading_watchlist.parquet",
        [{"symbol": "AAA", "date": "2026-06-30", "final_score": 75.0}],
    )

    source = resolve_watchlist_source(base_dir=tmp_path)

    assert source.source_name == "trading_watchlist"
    assert source.symbols == ["AAA"]


def test_watchlist_source_prefers_client_ready_watchlist(tmp_path) -> None:
    _write_frame(
        tmp_path / "data/output/client_ready_watchlist.parquet",
        [{"symbol": "AAA", "date": "2026-06-30", "final_score": 80.0}],
    )
    _write_frame(
        tmp_path / "data/output/trading_watchlist.parquet",
        [{"symbol": "BBB", "date": "2026-06-30", "final_score": 75.0}],
    )
    _write_frame(
        tmp_path / "data/processed/stock_features.parquet",
        [
            {"symbol": "AAA", "date": "2026-06-30", "close": 10.0, "volume": 500_000.0},
            {"symbol": "BBB", "date": "2026-06-30", "close": 11.0, "volume": 500_000.0},
        ],
    )

    candidates, metadata = load_default_portfolio_candidates(base_dir=tmp_path)

    assert metadata["source_name"] == "client_ready_watchlist"
    assert candidates["symbol"].tolist() == ["AAA"]


def test_portfolio_candidates_fall_back_when_client_ready_missing(tmp_path) -> None:
    _write_frame(
        tmp_path / "data/output/trading_watchlist.parquet",
        [{"symbol": "BBB", "date": "2026-06-30", "final_score": 75.0}],
    )
    _write_frame(
        tmp_path / "data/processed/stock_features.parquet",
        [{"symbol": "BBB", "date": "2026-06-30", "close": 11.0, "volume": 500_000.0}],
    )

    candidates, metadata = load_default_portfolio_candidates(base_dir=tmp_path)

    assert metadata["source_name"] == "trading_watchlist"
    assert candidates["symbol"].tolist() == ["BBB"]


def test_metadata_validators_accept_required_keys() -> None:
    pipeline_payload = {
        "run_timestamp": "2026-06-30T00:00:00+00:00",
        "run_mode": "offline",
        "freshness_status": "WARNING",
        "benchmark_status": {"status": "WARNING"},
        "generated_files": [],
        "watchlist_counts": {},
        "portfolio_stack": {"enabled": False},
        "sector_board": {"enabled": False},
        "cashflow_board": {"enabled": False},
        "research_notes": {"enabled": False},
        "online_update": {"enabled": False},
        "universe_update": {"scope": "offline"},
    }
    portfolio_payload = {
        "generated_at": "2026-06-30T00:00:00+00:00",
        "source_watchlist": "client_ready_watchlist",
        "source_file": "data/output/client_ready_watchlist.parquet",
        "symbols_used": ["AAA"],
        "missing_symbols": [],
        "generated_files": ["data/output/portfolio_weights.parquet"],
        "status": "OK",
        "warnings": [],
    }

    assert validate_pipeline_metadata(pipeline_payload) == pipeline_payload
    assert validate_portfolio_stack_metadata(portfolio_payload) == portfolio_payload

def test_freshness_check_allows_empty_trading_watchlist(tmp_path) -> None:
    base_rows = [{"symbol": "AAA", "date": "2026-06-30", "close": 10.0}]
    dated_artifacts = [
        "data/processed/clean_daily_ohlcv.parquet",
        "data/processed/stock_features.parquet",
        "data/signals/setup_signals.parquet",
        "data/signals/alpha_scores.parquet",
        "data/processed/benchmark_vnindex.parquet",
        "data/signals/breakout_20d_trade_cards.parquet",
        "data/signals/stealth_accumulation_latest.parquet",
        "data/signals/meta_ranking.parquet",
        "data/signals/final_watchlist.parquet",
        "data/output/research_candidates.parquet",
        "data/output/client_ready_watchlist.parquet",
    ]
    for artifact in dated_artifacts:
        _write_frame(tmp_path / artifact, base_rows)

    empty_trading = pd.DataFrame(columns=["symbol", "date", "final_score"])
    empty_trading.to_parquet(tmp_path / "data/output/trading_watchlist.parquet", index=False)

    report = evaluate_freshness(base_dir=tmp_path, now=pd.Timestamp("2026-06-30 20:00"))

    assert report["status"] == "OK"
    messages = report["warnings"] + report["errors"]
    assert not any("trading_watchlist" in message for message in messages)


def test_symbol_freshness_ratio_warning(tmp_path) -> None:
    rows = []
    for i in range(8):
        rows.append({"symbol": f"SYM{i}", "date": "2026-06-30", "close": 10.0})
    for i in range(8, 10):
        rows.append({"symbol": f"SYM{i}", "date": "2026-06-29", "close": 10.0})
    _write_all_mock_dated_files(tmp_path, rows)
    _write_frame(tmp_path / "data/output/client_ready_watchlist.parquet", [{"symbol": "SYM0", "date": "2026-06-30", "final_score": 80.0}])
    _write_frame(tmp_path / "data/output/portfolio_weights.parquet", [{"symbol": "SYM0", "date": "2026-06-30", "weight": 0.1}])

    report = evaluate_freshness(base_dir=tmp_path, now=pd.Timestamp("2026-07-02 20:00"), scope="full")
    assert report["symbol_freshness"]["status"] == "WARNING"
    assert report["symbol_freshness"]["stale_symbol_count"] == 2
    assert report["symbol_freshness"]["stale_symbol_ratio"] == 0.20


def test_symbol_freshness_client_ready_stale_error(tmp_path) -> None:
    rows = [
        {"symbol": "AAA", "date": "2026-06-30", "close": 10.0},
        {"symbol": "BBB", "date": "2026-06-29", "close": 10.0},
    ]
    _write_all_mock_dated_files(tmp_path, rows)
    _write_frame(tmp_path / "data/output/client_ready_watchlist.parquet", [{"symbol": "BBB", "final_score": 80.0}])

    report = evaluate_freshness(base_dir=tmp_path, now=pd.Timestamp("2026-07-02 20:00"))
    assert report["symbol_freshness"]["status"] == "ERROR"
    assert "BBB" in report["symbol_freshness"]["stale_client_ready_symbols"]


def test_update_daily_data_summary_warning_on_failed(tmp_path, monkeypatch) -> None:
    import yaml
    import json
    cfg_data = {
        "universe": {
            "start_date": "2020-01-01",
            "watchlist": ["AAA", "BBB"]
        }
    }
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    with open(tmp_path / "config/strategy_config.yaml", "w") as f:
        yaml.dump(cfg_data, f)

    monkeypatch.chdir(tmp_path)

    class MockClient:
        def get_daily_ohlc(self, *args, **kwargs):
            import pandas as pd
            return pd.DataFrame([{"tradingdate": "02/07/2026", "close": 10.0}])

    monkeypatch.setattr("src.data.ssi_client.SSIDataClient", MockClient)

    import sys
    if "scripts.update_daily_data" in sys.modules:
        del sys.modules["scripts.update_daily_data"]
    import scripts.update_daily_data

    def mock_update(client, symbol, *args, **kwargs):
        import pandas as pd
        if symbol == "BBB":
            raise RuntimeError("SSI rate limit 429 quota exceeded")
        return pd.DataFrame([{"symbol": symbol, "date": "2026-07-02"}])

    monkeypatch.setattr(scripts.update_daily_data, "update_symbol_history", mock_update)
    update_main = scripts.update_daily_data.main

    code = update_main(["--scope", "custom", "--symbols", "AAA,BBB"])
    assert code == 0

    summary_file = tmp_path / "data/output/update_daily_data_summary.json"
    assert summary_file.exists()
    with open(summary_file, "r") as f:
        summary = json.load(f)

    assert summary["status"] == "WARNING"
    assert summary["failed_count"] == 1
    assert summary["failed_symbols"] == ["BBB"]
    assert summary["error_category"] == "PROVIDER_RATE_LIMIT_PARTIAL"


def test_update_daily_data_scope_core(tmp_path, monkeypatch) -> None:
    import yaml
    import json
    cfg_data = {"universe": {"start_date": "2020-01-01", "watchlist": ["AAA"]}}
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    with open(tmp_path / "config/strategy_config.yaml", "w") as f:
        yaml.dump(cfg_data, f)

    core_df = pd.DataFrame([
        {"symbol": "CORE1", "reason": "reason", "source": "source", "updated_at": "2026-07-02"},
        {"symbol": "CORE2", "reason": "reason", "source": "source", "updated_at": "2026-07-02"}
    ])
    core_df.to_csv(tmp_path / "config/core_universe.csv", index=False)

    monkeypatch.chdir(tmp_path)

    class MockClient:
        def get_daily_ohlc(self, *args, **kwargs):
            return pd.DataFrame()

    monkeypatch.setattr("src.data.ssi_client.SSIDataClient", MockClient)

    attempted = []
    def mock_update(client, symbol, *args, **kwargs):
        attempted.append(symbol)
        return pd.DataFrame([{"symbol": symbol, "date": "2026-07-02"}])

    import sys
    if "scripts.update_daily_data" in sys.modules:
        del sys.modules["scripts.update_daily_data"]
    import scripts.update_daily_data
    monkeypatch.setattr(scripts.update_daily_data, "update_symbol_history", mock_update)

    code = scripts.update_daily_data.main(["--scope", "core"])
    assert code == 0
    assert sorted(attempted) == ["CORE1", "CORE2"]

    with open(tmp_path / "data/output/update_daily_data_summary.json") as f:
        summary = json.load(f)
    assert summary["update_scope"] == "core"


def test_update_daily_data_scope_tracked(tmp_path, monkeypatch) -> None:
    import yaml
    cfg_data = {"universe": {"start_date": "2020-01-01", "watchlist": ["AAA"]}}
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    with open(tmp_path / "config/strategy_config.yaml", "w") as f:
        yaml.dump(cfg_data, f)

    rows = [
        {"symbol": "S1", "date": "2026-07-01", "close": 10.0},
        {"symbol": "S2", "date": "2026-07-01", "close": 10.0},
        {"symbol": "S3", "date": "2026-07-01", "close": 10.0},
    ]
    _write_frame(tmp_path / "data/processed/clean_daily_ohlcv.parquet", rows)

    monkeypatch.chdir(tmp_path)

    class MockClient:
        def get_daily_ohlc(self, *args, **kwargs):
            return pd.DataFrame()

    monkeypatch.setattr("src.data.ssi_client.SSIDataClient", MockClient)

    attempted = []
    def mock_update(client, symbol, *args, **kwargs):
        attempted.append(symbol)
        return pd.DataFrame([{"symbol": symbol, "date": "2026-07-02"}])

    import sys
    if "scripts.update_daily_data" in sys.modules:
        del sys.modules["scripts.update_daily_data"]
    import scripts.update_daily_data
    monkeypatch.setattr(scripts.update_daily_data, "update_symbol_history", mock_update)

    code = scripts.update_daily_data.main(["--scope", "tracked"])
    assert code == 0
    assert sorted(attempted) == ["S1", "S2", "S3"]


def test_update_daily_data_scope_batch(tmp_path, monkeypatch) -> None:
    import yaml
    import json
    cfg_data = {"universe": {"start_date": "2020-01-01", "watchlist": ["AAA"]}}
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    with open(tmp_path / "config/strategy_config.yaml", "w") as f:
        yaml.dump(cfg_data, f)

    sec_rows = [{"symbol": f"S{i}", "date": "2026-07-01", "close": 10.0} for i in range(1, 7)]
    _write_frame(tmp_path / "data/raw/securities/HOSE.parquet", sec_rows)

    monkeypatch.chdir(tmp_path)

    class MockClient:
        def get_daily_ohlc(self, *args, **kwargs):
            return pd.DataFrame()

    monkeypatch.setattr("src.data.ssi_client.SSIDataClient", MockClient)

    attempted = []
    def mock_update(client, symbol, *args, **kwargs):
        attempted.append(symbol)
        return pd.DataFrame([{"symbol": symbol, "date": "2026-07-02"}])

    import sys
    if "scripts.update_daily_data" in sys.modules:
        del sys.modules["scripts.update_daily_data"]
    import scripts.update_daily_data
    monkeypatch.setattr(scripts.update_daily_data, "update_symbol_history", mock_update)

    code = scripts.update_daily_data.main(["--scope", "batch", "--batch-count", "3", "--batch-id", "1"])
    assert code == 0
    assert sorted(attempted) == ["S3", "S4"]

    with open(tmp_path / "data/output/update_daily_data_summary.json") as f:
        summary = json.load(f)
    assert summary["update_scope"] == "batch"
    assert summary["batch_id"] == 1
    assert summary["batch_count"] == 3
    assert summary["batch_size"] == 2
    assert sorted(summary["skipped_symbols"]) == ["S1", "S2", "S5", "S6"]


def test_freshness_check_scopes(tmp_path) -> None:
    core_df = pd.DataFrame([{"symbol": "CORE1", "reason": "reason", "source": "source", "updated_at": "2026-07-02"}])
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    core_df.to_csv(tmp_path / "config/core_universe.csv", index=False)

    rows = [
        {"symbol": "CORE1", "date": "2026-07-02", "close": 10.0},
        {"symbol": "STALE1", "date": "2026-06-30", "close": 10.0},
    ]
    _write_all_mock_dated_files(tmp_path, rows)
    _write_frame(tmp_path / "data/output/client_ready_watchlist.parquet", [{"symbol": "CORE1", "date": "2026-07-02", "final_score": 80.0}])
    _write_frame(tmp_path / "data/output/portfolio_weights.parquet", [{"symbol": "CORE1", "date": "2026-07-02", "weight": 0.1}])

    report_core = evaluate_freshness(base_dir=tmp_path, now=pd.Timestamp("2026-07-02 20:00"), scope="core")
    assert report_core["status"] == "OK"

    report_full = evaluate_freshness(base_dir=tmp_path, now=pd.Timestamp("2026-07-02 20:00"), scope="full")
    assert report_full["status"] == "WARNING"

    report_batch = evaluate_freshness(base_dir=tmp_path, now=pd.Timestamp("2026-07-02 20:00"), scope="batch")
    assert report_batch["status"] == "OK"


def test_freshness_check_active_stale_always_error(tmp_path) -> None:
    core_df = pd.DataFrame([{"symbol": "CORE1", "reason": "reason", "source": "source", "updated_at": "2026-07-02"}])
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    core_df.to_csv(tmp_path / "config/core_universe.csv", index=False)

    rows = [
        {"symbol": "CORE1", "date": "2026-06-30", "close": 10.0},
        {"symbol": "CORE2", "date": "2026-07-02", "close": 10.0},
    ]
    _write_all_mock_dated_files(tmp_path, rows)
    _write_frame(tmp_path / "data/output/client_ready_watchlist.parquet", [{"symbol": "CORE1", "date": "2026-06-30", "final_score": 80.0}])

    for scope in ("core", "full", "batch"):
        report = evaluate_freshness(base_dir=tmp_path, now=pd.Timestamp("2026-07-02 20:00"), scope=scope)
        assert report["status"] == "ERROR"




def test_full_universe_reads_real_securities_lists(tmp_path) -> None:
    """B1: scope=full must come from exchange listings, not previously-fetched data."""
    import sys
    if "scripts.update_daily_data" in sys.modules:
        del sys.modules["scripts.update_daily_data"]
    import scripts.update_daily_data as udd

    _write_frame(tmp_path / "data/raw/securities/HOSE.parquet",
                 [{"symbol": "AAA"}, {"symbol": "BBB"}])
    _write_frame(tmp_path / "data/raw/securities/HNX.parquet",
                 [{"symbol": "CCC"}, {"symbol": "AAA"}])
    # previously-fetched data must NOT drive scope=full
    _write_frame(tmp_path / "data/processed/clean_daily_ohlcv.parquet",
                 [{"symbol": "OLD1", "date": "2026-07-01", "close": 10.0}])

    symbols = udd.get_full_universe_symbols(tmp_path)
    assert symbols == ["AAA", "BBB", "CCC"]


def test_full_universe_fails_loudly_without_securities_lists(tmp_path) -> None:
    """B1: no securities lists => actionable SystemExit, no silent fallback."""
    import sys
    import pytest
    if "scripts.update_daily_data" in sys.modules:
        del sys.modules["scripts.update_daily_data"]
    import scripts.update_daily_data as udd

    _write_frame(tmp_path / "data/processed/clean_daily_ohlcv.parquet",
                 [{"symbol": "OLD1", "date": "2026-07-01", "close": 10.0}])

    with pytest.raises(SystemExit, match="update_securities"):
        udd.get_full_universe_symbols(tmp_path)


def test_calendar_freshness_detects_frozen_dataset(tmp_path) -> None:
    """B2: a dataset whose max date lags the real trading calendar must not report OK."""
    rows = [{"symbol": "AAA", "date": "2026-07-02", "close": 10.0}]  # Thursday
    _write_frame(tmp_path / "data/processed/clean_daily_ohlcv.parquet", rows)
    _write_frame(tmp_path / "data/processed/stock_features.parquet", rows)

    # Wednesday next week, evening: data is 3 sessions behind (Jul 3, 6, 7... through Jul 8)
    report = evaluate_freshness(base_dir=tmp_path, now=pd.Timestamp("2026-07-08 20:00"))
    assert report["status"] == "ERROR"
    assert any("frozen" in e.lower() for e in report["errors"])
    cal = report["calendar_freshness"]
    assert cal["lag_sessions"] >= 2

    # Same evening as the data date: calendar is satisfied (other artifacts may warn)
    report_ok = evaluate_freshness(base_dir=tmp_path, now=pd.Timestamp("2026-07-02 20:00"))
    assert report_ok["calendar_freshness"]["lag_sessions"] == 0
    assert not any("frozen" in e.lower() for e in report_ok["errors"])


def test_expected_latest_trading_date_calendar_rules() -> None:
    """B2: weekday/holiday/cutoff rules for the expected session."""
    from src.validation.freshness_check import expected_latest_trading_date

    # Wednesday morning (before 16:00) -> Tuesday
    assert expected_latest_trading_date(pd.Timestamp("2026-07-08 09:00")) == pd.Timestamp("2026-07-07")
    # Wednesday evening -> Wednesday
    assert expected_latest_trading_date(pd.Timestamp("2026-07-08 20:00")) == pd.Timestamp("2026-07-08")
    # Monday morning -> previous Friday
    assert expected_latest_trading_date(pd.Timestamp("2026-07-06 09:00")) == pd.Timestamp("2026-07-03")
    # Saturday -> Friday
    assert expected_latest_trading_date(pd.Timestamp("2026-07-04 12:00")) == pd.Timestamp("2026-07-03")
    # Holiday skipping: Sep 2 2026 (Wednesday) is National Day
    holidays = {pd.Timestamp("2026-09-02").date()}
    assert expected_latest_trading_date(pd.Timestamp("2026-09-02 20:00"), holidays) == pd.Timestamp("2026-09-01")


def test_trading_day_count_skips_a_full_tet_period() -> None:
    """audit/PATH_TO_100.md Universe/Eligibility item: any consumer counting
    trading days (available_at+1, event windows, rebalance calendars, the
    freshness gate) must not count through a Tet closure as if it were
    ordinary weekdays. Uses the real config/vn_market_holidays.csv (not a
    synthetic fixture) -- Tet Nguyen Dan 2026 (Binh Ngo) is 2026-02-16
    through 2026-02-20 (Mon-Fri, verified empirically against
    data/full_history_v2 -- see docs/reports/data/DATA_BASELINE.md/config/vn_market_holidays.csv)."""
    from src.validation.freshness_check import (
        expected_latest_trading_date,
        load_market_holidays,
        trading_sessions_behind,
    )

    holidays = load_market_holidays()
    assert pd.Timestamp("2026-02-17").date() in holidays  # sanity: Tet is actually loaded

    # Evening of the first trading day back from Tet (Mon 2026-02-23) ->
    # expected latest session is that same day, not counting the Tet week.
    assert expected_latest_trading_date(pd.Timestamp("2026-02-23 20:00"), holidays) == pd.Timestamp("2026-02-23")
    # Morning of the same day (before 16:00 cutoff) -> previous session is
    # 2026-02-13 (Friday before Tet), skipping the entire holiday week, not
    # 2026-02-22 (Sunday) or 2026-02-20 (would be wrong by a naive
    # weekend-only skip that didn't know about Tet).
    assert expected_latest_trading_date(pd.Timestamp("2026-02-23 09:00"), holidays) == pd.Timestamp("2026-02-13")

    # trading_sessions_behind must count 0 sessions across the Tet week
    # itself (baseline = last pre-Tet session, expected = last Tet holiday
    # day) and exactly 1 once the first post-Tet session is reached.
    assert trading_sessions_behind(pd.Timestamp("2026-02-13"), pd.Timestamp("2026-02-20"), holidays) == 0
    assert trading_sessions_behind(pd.Timestamp("2026-02-13"), pd.Timestamp("2026-02-23"), holidays) == 1


def test_market_holidays_cross_check_against_real_trading_data() -> None:
    """Two-way verification of config/vn_market_holidays.csv against the
    actual full_history_v2 dataset for the range it can be checked against
    (2020-01-02..2026-07-13): every listed holiday must have zero trades
    market-wide, and every market-wide zero-trade weekday must be listed.
    2027 entries are estimates pending official publication and are
    excluded from this check (not verifiable against real data yet)."""
    import glob

    from src.validation.freshness_check import load_market_holidays

    holidays = load_market_holidays()
    data_min, data_max = pd.Timestamp("2020-01-02"), pd.Timestamp("2026-07-13")
    checkable_holidays = {d for d in holidays if data_min.date() <= d <= data_max.date()}

    files = glob.glob("data/full_history_v2/raw/*.parquet")
    if not files:
        pytest.skip("requires real data/full_history_v2/raw")
    all_trading_dates: set = set()
    for f in files:
        df = pd.read_parquet(f, columns=["date"])
        all_trading_dates.update(pd.to_datetime(df["date"]).dt.date.tolist())

    # Direction 1: no listed holiday (in the checkable range) has trades.
    violating_holidays = sorted(d for d in checkable_holidays if d in all_trading_dates)
    assert violating_holidays == [], f"holiday(s) with unexpected trades: {violating_holidays}"

    # Direction 2: no market-wide zero-trade weekday is missing from the list.
    full_range = pd.bdate_range(data_min, data_max)
    missing_holidays = sorted(
        d.date() for d in full_range if d.date() not in all_trading_dates and d.date() not in holidays
    )
    assert missing_holidays == [], f"zero-trade weekday(s) not in holiday list: {missing_holidays}"


def test_missing_volume_column_rejects_instead_of_fabricating(tmp_path) -> None:
    """H4: a features frame with no volume column must reject candidates as
    VOLUME_DATA_MISSING, not fabricate 100,000 shares and let them pass."""
    _write_frame(
        tmp_path / "data/output/client_ready_watchlist.parquet",
        [{"symbol": "AAA", "date": "2026-06-30", "final_score": 80.0}],
    )
    _write_frame(
        tmp_path / "data/processed/stock_features.parquet",
        [{"symbol": "AAA", "date": "2026-06-30", "close": 10.0}],  # no volume column at all
    )

    candidates, metadata = load_default_portfolio_candidates(base_dir=tmp_path)

    assert candidates.empty, "candidate must be rejected, not fabricated a fake volume"
    assert metadata["rejected_symbols_portfolio_gate"]["AAA"] == "VOLUME_DATA_MISSING"


# --- assert_derived_artifact_fresh (AUDIT_NOTEBOOKS_REPORT.md OPEN_AUTO #1) ---------
#
# Regression cover for the 21-day silent staleness: breakout_20d_setup_eligibility
# .parquet is produced only by notebook 07 (by hand) but read every night by
# scripts/generate_trade_cards.py. Neither file has a `date` column, so freshness
# is mtime-based.

import os
import time

import pytest

from src.validation.freshness_check import (
    assert_input_chain_fresh,
    load_upstream_artifact,
    DerivedArtifactStale,
    assert_derived_artifact_fresh,
)


def _touch(path, age_days: float = 0.0):
    path.write_text("x")
    when = time.time() - age_days * 86400.0
    os.utime(path, (when, when))
    return path


def test_derived_artifact_fresh_passes_when_within_limit(tmp_path):
    source = _touch(tmp_path / "setup_signals.parquet", age_days=0)
    derived = _touch(tmp_path / "eligibility.parquet", age_days=3)

    assert_derived_artifact_fresh([derived], source, max_lag_days=7, remedy="rerun nb07")


def test_derived_artifact_stale_raises_with_lag_and_remedy(tmp_path):
    source = _touch(tmp_path / "setup_signals.parquet", age_days=0)
    derived = _touch(tmp_path / "eligibility.parquet", age_days=21)

    with pytest.raises(DerivedArtifactStale) as excinfo:
        assert_derived_artifact_fresh([derived], source, max_lag_days=7, remedy="rerun nb07")

    message = str(excinfo.value)
    assert "21.0 days older" in message
    assert "limit: 7 days" in message
    assert "rerun nb07" in message


def test_derived_artifact_missing_raises(tmp_path):
    source = _touch(tmp_path / "setup_signals.parquet", age_days=0)

    with pytest.raises(DerivedArtifactStale, match="is missing"):
        assert_derived_artifact_fresh(
            [tmp_path / "nope.parquet"], source, max_lag_days=7, remedy="rerun nb07"
        )


def test_negative_limit_disables_the_check(tmp_path):
    source = _touch(tmp_path / "setup_signals.parquet", age_days=0)
    derived = _touch(tmp_path / "eligibility.parquet", age_days=999)

    assert_derived_artifact_fresh([derived], source, max_lag_days=-1, remedy="rerun nb07")


def test_missing_source_is_a_no_op(tmp_path):
    # Nothing to compare against -- a fresh checkout shouldn't fail here.
    assert_derived_artifact_fresh(
        [tmp_path / "nope.parquet"], tmp_path / "absent.parquet",
        max_lag_days=7, remedy="rerun nb07",
    )


def test_every_derived_path_is_checked_not_just_the_first(tmp_path):
    source = _touch(tmp_path / "setup_signals.parquet", age_days=0)
    fresh = _touch(tmp_path / "eligibility.parquet", age_days=1)
    stale = _touch(tmp_path / "volatility_rule.parquet", age_days=40)

    with pytest.raises(DerivedArtifactStale, match="volatility_rule"):
        assert_derived_artifact_fresh([fresh, stale], source, max_lag_days=7, remedy="rerun nb07")


# --- load_upstream_artifact (Đợt 3 NV1) --------------------------------------
#
# Notebook 15 used to do `os.path.exists()` then read, so once the Đợt 2 write
# guard stopped notebook 14 refreshing the file, 15 silently consumed a days-old
# copy. This helper makes every read announce the file's age.


def _write_parquet(path, age_days: float = 0.0):
    pd.DataFrame({"symbol": ["AAA", "BBB"], "weight": [0.6, 0.4]}).to_parquet(path, index=False)
    when = time.time() - age_days * 86400.0
    os.utime(path, (when, when))
    return path


def test_load_upstream_artifact_returns_a_dataframe_not_a_tuple(tmp_path):
    """read_first_existing_parquet returns (df, path); an early version of the
    helper forwarded that tuple straight to callers, so `len(df)` was 2 for any
    file and notebooks got a tuple where they expected a frame."""
    target = _write_parquet(tmp_path / "weights.parquet")

    df, info = load_upstream_artifact(target, producer="nb14", max_age_days=7)

    assert isinstance(df, pd.DataFrame)
    assert df.shape == (2, 2)
    assert info["rows"] == 2


def test_load_upstream_artifact_flags_stale_and_says_the_date(tmp_path, capsys):
    target = _write_parquet(tmp_path / "weights.parquet", age_days=30)

    df, info = load_upstream_artifact(target, producer="nb14", max_age_days=7)

    assert info["status"] == "stale"
    assert info["age_days"] == 30.0
    out = capsys.readouterr().out
    assert "CANH BAO" in out and "BAN CU" in out
    assert not df.empty  # still returned -- caller decides what to do


def test_load_upstream_artifact_ok_when_fresh(tmp_path, capsys):
    target = _write_parquet(tmp_path / "weights.parquet", age_days=1)

    _df, info = load_upstream_artifact(target, producer="nb14", max_age_days=7)

    assert info["status"] == "ok"
    assert "OK" in capsys.readouterr().out


def test_load_upstream_artifact_missing_is_announced_not_silent(tmp_path, capsys):
    df, info = load_upstream_artifact(tmp_path / "nope.parquet", producer="nb14")

    assert info["status"] == "missing"
    assert df.empty
    assert "KHONG TIM THAY" in capsys.readouterr().out


# --- assert_input_chain_fresh (Đợt 3 NV2) ------------------------------------


def _chain(tmp_path, feature_days_back: int = 0):
    (tmp_path / "data/processed").mkdir(parents=True, exist_ok=True)
    end = pd.Timestamp("2026-07-27")
    pd.DataFrame({"symbol": ["AAA"], "date": [end], "close": [1.0]}).to_parquet(
        tmp_path / "data/processed/clean_daily_ohlcv.parquet", index=False
    )
    pd.DataFrame(
        {"symbol": ["AAA"], "date": [end - pd.Timedelta(days=feature_days_back)], "close": [1.0]}
    ).to_parquet(tmp_path / "data/processed/stock_features.parquet", index=False)
    return tmp_path


def test_input_chain_fresh_passes_when_aligned(tmp_path):
    assert_input_chain_fresh(_chain(tmp_path, 0), consumer="probe")


def test_input_chain_fresh_fails_when_features_lag_source(tmp_path):
    with pytest.raises(DerivedArtifactStale) as excinfo:
        assert_input_chain_fresh(_chain(tmp_path, 6), consumer="run_alpha_scoring")
    message = str(excinfo.value)
    assert "run_alpha_scoring" in message
    assert "generate_features.py" in message


def test_input_chain_fresh_is_a_no_op_when_inputs_absent(tmp_path):
    # Emptiness is each caller's own precondition to report, not this guard's.
    assert_input_chain_fresh(tmp_path, consumer="probe")
