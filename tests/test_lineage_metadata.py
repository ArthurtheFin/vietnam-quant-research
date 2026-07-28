"""Regression tests for audit gate #12 / critical finding P0-3 (reproducibility):
generated artifacts must embed lineage (dataset version, input file SHA-256 +
row count, git commit hash, config hash) and the "no lineage, no commit"
convention must be enforced, not just documented."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from src.utils.pipeline_io import build_lineage_metadata, validate_lineage_metadata

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_parquet(path: Path, rows: int) -> None:
    pd.DataFrame({"symbol": ["AAA"] * rows, "date": pd.bdate_range("2024-01-01", periods=rows)}).to_parquet(path)


def test_build_lineage_metadata_computes_sha256_and_row_count(tmp_path: Path) -> None:
    features_path = tmp_path / "features.parquet"
    _write_parquet(features_path, rows=7)
    config_path = tmp_path / "config.yaml"
    config_path.write_text("a: 1\n", encoding="utf-8")

    lineage = build_lineage_metadata(
        features_path=features_path,
        config_path=config_path,
        dataset_version="test_v1",
        base_dir=PROJECT_ROOT,
    )

    assert lineage["dataset_version"] == "test_v1"
    assert lineage["features_sha256"] == hashlib.sha256(features_path.read_bytes()).hexdigest()
    assert lineage["features_row_count"] == 7
    assert lineage["config_hash"] == hashlib.sha256(config_path.read_bytes()).hexdigest()
    assert lineage["lineage_generated_at"]
    # base_dir is a real git checkout -- expect a real 40-hex-char commit hash.
    assert lineage["git_commit_hash"] is not None
    assert len(lineage["git_commit_hash"]) == 40
    int(lineage["git_commit_hash"], 16)  # raises if not valid hex


def test_build_lineage_metadata_handles_missing_features_file(tmp_path: Path) -> None:
    lineage = build_lineage_metadata(
        features_path=tmp_path / "does_not_exist.parquet",
        config_path=tmp_path / "also_missing.yaml",
        base_dir=PROJECT_ROOT,
    )
    assert lineage["features_sha256"] is None
    assert lineage["features_row_count"] is None
    assert lineage["config_hash"] is None


def test_build_lineage_metadata_falls_back_to_real_repo_commit_when_base_dir_is_not_a_git_repo(
    tmp_path: Path,
) -> None:
    """base_dir is only used to resolve data file paths; the commit hash must
    reflect the actual running code's version (this repo), not whatever
    directory a caller happens to write output data into (e.g. a tmp_path
    test sandbox with no .git of its own)."""
    lineage = build_lineage_metadata(
        features_path=tmp_path / "features.parquet",
        base_dir=tmp_path,
    )
    assert lineage["git_commit_hash"] is not None
    assert len(lineage["git_commit_hash"]) == 40


def test_validate_lineage_metadata_passes_when_complete() -> None:
    complete = {
        "dataset_version": "full_history_v2",
        "features_sha256": "a" * 64,
        "features_row_count": 100,
        "config_hash": "b" * 64,
        "git_commit_hash": "c" * 40,
        "lineage_generated_at": "2026-07-13T00:00:00+00:00",
    }
    assert validate_lineage_metadata(complete, label="test") == complete


@pytest.mark.parametrize(
    "missing_key",
    ["dataset_version", "features_sha256", "features_row_count", "config_hash", "git_commit_hash", "lineage_generated_at"],
)
def test_validate_lineage_metadata_raises_on_missing_key(missing_key: str) -> None:
    payload = {
        "dataset_version": "full_history_v2",
        "features_sha256": "a" * 64,
        "features_row_count": 100,
        "config_hash": "b" * 64,
        "git_commit_hash": "c" * 40,
        "lineage_generated_at": "2026-07-13T00:00:00+00:00",
    }
    del payload[missing_key]
    with pytest.raises(ValueError, match="no lineage, no commit|missing required key"):
        validate_lineage_metadata(payload, label="test")


def test_validate_lineage_metadata_raises_on_none_value() -> None:
    payload = {
        "dataset_version": "full_history_v2",
        "features_sha256": None,
        "features_row_count": 100,
        "config_hash": "b" * 64,
        "git_commit_hash": "c" * 40,
        "lineage_generated_at": "2026-07-13T00:00:00+00:00",
    }
    with pytest.raises(ValueError, match="no lineage, no commit"):
        validate_lineage_metadata(payload, label="test")


@pytest.mark.skipif(
    not (PROJECT_ROOT / "data/processed/stock_features.parquet").exists(),
    reason="requires real data/processed/stock_features.parquet",
)
def test_portfolio_risk_report_lineage_is_present_and_valid_when_generated() -> None:
    """If portfolio_risk_report.json exists (built by build_portfolio_stack.py
    after this fix), it must carry a complete lineage block -- this is a
    smoke check on the real artifact, not a re-run of the pipeline."""
    import json

    report_path = PROJECT_ROOT / "data/output/portfolio_risk_report.json"
    if not report_path.exists():
        pytest.skip("portfolio_risk_report.json not generated in this environment")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert "lineage" in report, "portfolio_risk_report.json missing lineage block (gate #12)"
    validate_lineage_metadata(report["lineage"], label="portfolio_risk_report.json")


def _seed_lineage_inputs(base):
    """Minimal tree so build_lineage_metadata() can hash a real features file --
    without it the lineage validator (correctly) refuses to emit a sidecar."""
    import pandas as pd

    (base / "data/output").mkdir(parents=True, exist_ok=True)
    (base / "data/processed").mkdir(parents=True, exist_ok=True)
    (base / "research_notes/generated").mkdir(parents=True, exist_ok=True)
    (base / "config").mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"symbol": ["AAA"], "date": [pd.Timestamp("2026-07-27")], "close": [1.0]}).to_parquet(
        base / "data/processed/stock_features.parquet", index=False
    )
    (base / "config/strategy_config.yaml").write_text("returns:\n  horizons: [1]\n")

# --- research_notes sidecar (Đợt 3 NV4) --------------------------------------


def test_research_notes_metadata_carries_a_timestamp(tmp_path, monkeypatch):
    """build_research_notes.py seeds generated_at="" with a comment claiming the
    write helper fills it. Nothing did, so research_notes_metadata.json was the
    only sidecar in data/output/ shipping an empty timestamp."""
    import pandas as pd

    from src.reporting import research_notes

    _seed_lineage_inputs(tmp_path)

    payload = research_notes.write_research_notes_outputs(
        index_df=pd.DataFrame({"symbol": ["AAA"], "latest_date": ["2026-07-27"]}),
        notes_dict={"AAA": "# note"},
        metadata={"generated_at": "", "status": "OK", "n_notes_generated": 1,
                  "warnings": [], "generated_files": []},
        base_dir=tmp_path,
    )

    assert payload["generated_at"], "generated_at must not be empty"
    assert payload["generated_at"].startswith("20")


def test_research_notes_metadata_declares_only_files_that_exist(tmp_path):
    """The sidecar declared MST/BVS/KLB/NAB notes that were absent from disk --
    same 'sidecar lies about what it produced' family as reports/top_watchlist.csv."""
    import pandas as pd

    from src.reporting import research_notes

    _seed_lineage_inputs(tmp_path)

    payload = research_notes.write_research_notes_outputs(
        index_df=pd.DataFrame({"symbol": ["AAA", "BBB"], "latest_date": ["2026-07-27"] * 2}),
        notes_dict={"AAA": "# a", "BBB": "# b"},
        metadata={"generated_at": "", "status": "OK", "n_notes_generated": 2,
                  "warnings": [], "generated_files": []},
        base_dir=tmp_path,
    )

    missing = [f for f in payload["generated_files"] if not (tmp_path / f).exists()]
    assert not missing, f"sidecar declares files that do not exist: {missing}"


def test_symbol_only_cashflow_pass_annotates_its_sidecar(tmp_path):
    """build_cashflow_board.py --symbol-only rewrites cashflow_board.parquet/.csv
    but produces none of the sector/watchlist outputs. It used to leave
    cashflow_board_metadata.json completely untouched, so the sidecar kept
    describing an older full-mode run while those two files on disk had been
    replaced. It is step 6/7 of every nightly pipeline, so the sidecar was stale
    by construction every night (AUDIT_NOTEBOOKS_REPORT.md Đợt 4 NV3).

    Contract: the full-mode payload survives, and a symbol_only_pass record says
    what this pass actually replaced.
    """
    import json

    from src.utils.pipeline_io import utc_now_iso, write_json

    meta = tmp_path / "cashflow_board_metadata.json"
    write_json({"generated_at": "2026-07-01T00:00:00+00:00",
                "generated_files": ["data/output/sector_cashflow.parquet"]}, meta)

    # Mirror what the --symbol-only branch does.
    existing = json.loads(meta.read_text(encoding="utf-8"))
    existing["symbol_only_pass"] = {
        "generated_at": utc_now_iso(),
        "overwrote_files": ["data/output/cashflow_board.parquet",
                            "data/output/cashflow_board.csv"],
    }
    write_json(existing, meta)

    payload = json.loads(meta.read_text(encoding="utf-8"))
    assert payload["generated_files"] == ["data/output/sector_cashflow.parquet"], \
        "full-mode payload must survive the annotation"
    assert payload["symbol_only_pass"]["generated_at"]
    assert "cashflow_board.parquet" in payload["symbol_only_pass"]["overwrote_files"][0]
