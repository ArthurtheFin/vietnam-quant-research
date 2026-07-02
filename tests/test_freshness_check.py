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

    report = evaluate_freshness(base_dir=tmp_path)

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
            {"symbol": "AAA", "date": "2026-06-30", "close": 10.0},
            {"symbol": "BBB", "date": "2026-06-30", "close": 11.0},
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
        [{"symbol": "BBB", "date": "2026-06-30", "close": 11.0}],
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

    report = evaluate_freshness(base_dir=tmp_path)

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

    report = evaluate_freshness(base_dir=tmp_path, scope="full")
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

    report = evaluate_freshness(base_dir=tmp_path)
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


def test_update_daily_data_scope_full(tmp_path, monkeypatch) -> None:
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

    code = scripts.update_daily_data.main(["--scope", "full"])
    assert code == 0
    assert sorted(attempted) == ["S1", "S2", "S3"]


def test_update_daily_data_scope_batch(tmp_path, monkeypatch) -> None:
    import yaml
    import json
    cfg_data = {"universe": {"start_date": "2020-01-01", "watchlist": ["AAA"]}}
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    with open(tmp_path / "config/strategy_config.yaml", "w") as f:
        yaml.dump(cfg_data, f)

    rows = [{"symbol": f"S{i}", "date": "2026-07-01", "close": 10.0} for i in range(1, 7)]
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

    report_core = evaluate_freshness(base_dir=tmp_path, scope="core")
    assert report_core["status"] == "OK"

    report_full = evaluate_freshness(base_dir=tmp_path, scope="full")
    assert report_full["status"] == "WARNING"

    report_batch = evaluate_freshness(base_dir=tmp_path, scope="batch")
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
        report = evaluate_freshness(base_dir=tmp_path, scope=scope)
        assert report["status"] == "ERROR"


