from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd
import pytest

import scripts.run_daily_pipeline as daily_pipeline
from src.utils.pipeline_io import compare_run_snapshots, validate_pipeline_metadata, write_run_snapshot


def test_read_artifact_summary_handles_json_without_parquet(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": "2026-06-30T00:00:00+00:00",
        "source_watchlist": "client_ready_watchlist",
        "source_file": "data/output/client_ready_watchlist.parquet",
        "symbols_used": ["AAA", "BBB"],
        "missing_symbols": [],
        "generated_files": ["data/output/portfolio_weights.parquet"],
        "status": "OK",
        "warnings": [],
    }
    metadata_path = output_dir / "portfolio_stack_metadata.json"
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(daily_pipeline, "PROJECT_ROOT", tmp_path)
    summary = daily_pipeline._read_artifact_summary("data/output/portfolio_stack_metadata.json")

    assert summary["exists"] is True
    assert summary["path"] == "data/output/portfolio_stack_metadata.json"
    assert summary["symbol_count"] is None
    assert summary["latest_date"] is None


def test_default_portfolio_stack_metadata_disabled() -> None:
    payload = daily_pipeline._default_portfolio_stack_metadata()
    assert payload == {"enabled": False}


def test_classify_error_detects_rate_limit() -> None:
    category = daily_pipeline._classify_error("429 API calls quota exceeded")
    assert category == "PROVIDER_RATE_LIMIT"


def test_write_run_snapshot_creates_expected_keys(tmp_path: Path) -> None:
    (tmp_path / "data/output").mkdir(parents=True, exist_ok=True)
    metadata = {
        "run_timestamp": "2026-06-30T15:30:00+00:00",
        "run_mode": "offline",
        "flags_used": ["--offline"],
        "freshness_status": "OK",
        "benchmark_status": {"benchmark_latest_date": "2026-06-30"},
        "latest_stock_date": "2026-06-30",
        "watchlist_counts": {
            "research_candidates": {"rows": 5},
            "trading_watchlist": {"rows": 2},
            "client_ready_watchlist": {"rows": 1},
        },
        "warnings": [],
        "errors": [],
        "generated_files": ["data/output/client_ready_watchlist.parquet"],
        "portfolio_stack": {"enabled": False},
        "sector_board": {"enabled": False},
        "online_update": {"enabled": False},
    }
    pd.DataFrame([{"symbol": "AAA", "date": "2026-06-30"}]).to_parquet(
        tmp_path / "data/output/trading_watchlist.parquet",
        index=False,
    )
    pd.DataFrame([{"symbol": "BBB", "date": "2026-06-30"}]).to_parquet(
        tmp_path / "data/output/client_ready_watchlist.parquet",
        index=False,
    )

    path = write_run_snapshot(metadata, base_dir=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.parent.name == "run_history"
    assert set(payload) >= {
        "run_timestamp",
        "run_mode",
        "flags_used",
        "freshness_status",
        "benchmark_latest_date",
        "stock_latest_date",
        "watchlist_counts",
        "trading_watchlist_symbols",
        "client_ready_symbols",
        "portfolio_symbols",
        "warnings",
        "errors",
        "generated_files",
    }


def test_compare_run_snapshots_detects_symbol_changes() -> None:
    previous = {
        "run_timestamp": "2026-06-29T00:00:00+00:00",
        "freshness_status": "WARNING",
        "benchmark_latest_date": "2026-06-29",
        "watchlist_counts": {
            "research_candidates": {"rows": 10},
            "trading_watchlist": {"rows": 5},
            "client_ready_watchlist": {"rows": 3},
        },
        "client_ready_symbols": ["AAA", "BBB", "CCC"],
        "portfolio_symbols": ["AAA", "BBB"],
    }
    current = {
        "run_timestamp": "2026-06-30T00:00:00+00:00",
        "freshness_status": "OK",
        "benchmark_latest_date": "2026-06-30",
        "watchlist_counts": {
            "research_candidates": {"rows": 11},
            "trading_watchlist": {"rows": 4},
            "client_ready_watchlist": {"rows": 3},
        },
        "client_ready_symbols": ["BBB", "CCC", "DDD"],
        "portfolio_symbols": ["BBB", "DDD"],
    }

    diff = compare_run_snapshots(previous=previous, current=current)

    assert diff["client_ready_added"] == ["DDD"]
    assert diff["client_ready_removed"] == ["AAA"]
    assert diff["portfolio_added"] == ["DDD"]
    assert diff["portfolio_removed"] == ["AAA"]
    assert diff["freshness_status_changed"] is True
    assert diff["benchmark_date_changed"] is True


def test_validate_pipeline_metadata_rejects_absolute_paths() -> None:
    payload = {
        "run_timestamp": "2026-06-30T00:00:00+00:00",
        "run_mode": "offline",
        "freshness_status": "OK",
        "benchmark_status": {"status": "OK"},
        "generated_files": ["/abs/path.parquet"],
        "watchlist_counts": {},
        "portfolio_stack": {"enabled": False},
        "sector_board": {"enabled": False},
        "cashflow_board": {"enabled": False},
        "research_notes": {"enabled": False},
        "online_update": {"enabled": False},
        "universe_update": {"scope": "offline"},
    }

    with pytest.raises(ValueError, match="absolute filesystem paths"):
        validate_pipeline_metadata(payload)


def test_resolve_steps_to_run_offline_excludes_online_updates() -> None:
    steps = daily_pipeline._resolve_steps_to_run(mode="offline", update_index=False)
    names = [step["name"] for step in steps]
    assert "update_daily_data" not in names
    assert "update_index_data" not in names


def test_default_sector_board_metadata_disabled() -> None:
    payload = daily_pipeline._default_sector_board_metadata()
    assert payload == {"enabled": False}


def test_default_cashflow_board_metadata_disabled() -> None:
    payload = daily_pipeline._default_cashflow_board_metadata()
    assert payload == {"enabled": False}

def test_run_step_marks_partial_online_failures_as_warning(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(daily_pipeline, "PROJECT_ROOT", tmp_path)

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=["python", "scripts/update_daily_data.py"],
            returncode=0,
            stdout="[FAILED] TPB chunk: 429 API calls quota exceeded",
            stderr="",
        )

    monkeypatch.setattr(daily_pipeline.subprocess, "run", fake_run)
    monkeypatch.setattr(
        daily_pipeline,
        "_read_artifact_summary",
        lambda path: {"path": str(path), "exists": False, "rows": None, "columns": None, "symbol_count": None, "latest_date": None},
    )

    report = daily_pipeline._run_step(
        {
            "name": "update_daily_data",
            "script": "scripts/update_daily_data.py",
            "outputs": ["data/raw"],
        }
    )

    assert report["status"] == "WARNING"
    assert report["error_category"] == "PROVIDER_RATE_LIMIT_PARTIAL"
    assert "partial fetch failures" in report["error_message"]

