"""Contract tests: invariants between pipeline steps (audit F1/J1/J3)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_module(relative_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cashflow_board_step_precedes_meta_ranking() -> None:
    """F1: the eligibility gate must see a same-day cashflow board."""
    mod = _load_module("scripts/run_daily_pipeline.py", "run_daily_pipeline_contract")
    names = [step["name"] for step in mod.PIPELINE_STEPS]
    assert "build_cashflow_board_symbols" in names, "symbol-level board must be a default step"
    assert "run_meta_ranking" in names
    assert names.index("build_cashflow_board_symbols") < names.index("run_meta_ranking")


def test_cashflow_symbols_step_passes_symbol_only_flag() -> None:
    mod = _load_module("scripts/run_daily_pipeline.py", "run_daily_pipeline_contract2")
    step = next(s for s in mod.PIPELINE_STEPS if s["name"] == "build_cashflow_board_symbols")
    assert "--symbol-only" in step.get("args", [])


def test_notebook_runner_resolves_real_paths() -> None:
    """J1: the runner must list existing notebooks (no stale-path silent no-op)."""
    result = subprocess.run(
        ["bash", str(PROJECT_ROOT / "scripts/run_all_notebooks.sh"), "--list"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert len(paths) >= 15, f"expected >=15 active notebooks, got {len(paths)}"
    for p in paths:
        assert (PROJECT_ROOT / p).is_file(), f"listed notebook does not exist: {p}"
        assert "00_archive" not in p


def test_universe_count_fallback_has_no_hardcoded_guess():
    """B4: run_daily_pipeline.py must not fall back to a hardcoded "501" guess
    for total universe size -- source code must not contain that literal."""
    src = (PROJECT_ROOT / "scripts/run_daily_pipeline.py").read_text()
    assert "or 501" not in src
