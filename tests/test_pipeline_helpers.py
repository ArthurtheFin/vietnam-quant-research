from __future__ import annotations

import json
from pathlib import Path

import scripts.run_daily_pipeline as daily_pipeline


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
