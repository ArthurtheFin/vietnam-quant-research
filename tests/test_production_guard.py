"""Regression tests for the notebook-overwrite incident
(docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md NV1): a notebook run by
hand must never silently overwrite a shared production data file."""
from __future__ import annotations

import pytest

from src.data.dataset_config import OFFICIAL_FEATURES_PATH, OFFICIAL_MARKET_FEATURES_PATH
from src.data.production_guard import (
    ALLOW_PRODUCTION_WRITE_ENV,
    ProductionWriteBlocked,
    guard_production_write,
    is_production_write_allowed,
    is_protected_path,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(ALLOW_PRODUCTION_WRITE_ENV, raising=False)


def test_protected_paths_match_dataset_config():
    assert is_protected_path(OFFICIAL_FEATURES_PATH)
    assert is_protected_path(OFFICIAL_MARKET_FEATURES_PATH)


def test_non_production_path_is_never_protected():
    assert not is_protected_path("notebooks/outputs/scratch_thing.parquet")
    assert not is_protected_path("docs/reports/whatever.md")


def test_pipeline_owned_dirs_are_protected():
    """Scope widened from 3 exact paths to whole pipeline-owned directories
    (AUDIT_NOTEBOOKS_REPORT.md OPEN_AUTO #2/#3).

    `data/signals/monte_carlo_exits.parquet` was asserted UNprotected here
    before. That assertion encoded the narrow original scope -- and that scope
    is exactly what let notebook 12 overwrite data/signals/alpha_scores.parquet
    and reports/top_watchlist.csv, neither of which was in PROTECTED_PATHS.
    Anything a pipeline step produces or reads is protected now; notebooks
    write to notebooks/outputs/ instead.
    """
    assert is_protected_path("data/signals/monte_carlo_exits.parquet")
    assert is_protected_path("data/signals/alpha_scores.parquet")
    assert is_protected_path("data/output/client_ready_watchlist.parquet")
    assert is_protected_path("reports/top_watchlist.csv")


def test_write_blocked_by_default():
    assert is_production_write_allowed() is False
    with pytest.raises(ProductionWriteBlocked):
        guard_production_write(OFFICIAL_MARKET_FEATURES_PATH)


def test_write_allowed_via_env_var(monkeypatch):
    monkeypatch.setenv(ALLOW_PRODUCTION_WRITE_ENV, "1")
    assert is_production_write_allowed() is True
    guard_production_write(OFFICIAL_MARKET_FEATURES_PATH)  # must not raise


def test_write_allowed_via_explicit_flag():
    guard_production_write(OFFICIAL_FEATURES_PATH, allow=True)  # must not raise


def test_guard_is_a_noop_for_unprotected_paths():
    # No env var set, allow=None -- would raise for a protected path, but
    # this path isn't protected so it must pass silently either way.
    guard_production_write("notebooks/outputs/anything.parquet")


def test_mock_notebook_run_does_not_write_production_file():
    """Simulates the exact pattern used in 05/06_market_regime.ipynb's save
    cell: guard-then-save. Confirms that without ALLOW_PRODUCTION_WRITE=1,
    the save call is never reached."""
    save_calls = []

    def notebook_save_cell(path, allow=None):
        guard_production_write(path, allow=allow)
        save_calls.append(path)  # stand-in for save_parquet(df, path)

    with pytest.raises(ProductionWriteBlocked):
        notebook_save_cell(OFFICIAL_MARKET_FEATURES_PATH)
    assert save_calls == [], "save_parquet must not run when the guard blocks the write"

    notebook_save_cell(OFFICIAL_MARKET_FEATURES_PATH, allow=True)
    assert save_calls == [OFFICIAL_MARKET_FEATURES_PATH], "save_parquet must run once allowed"
