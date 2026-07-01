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
