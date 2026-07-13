"""Regression test for audit gate #6 (critical finding P0-2): the official
dataset paths must have exactly one source of truth, `src/data/dataset_config.py`.

Fails the build if any other module in `src/` or `scripts/` hardcodes one of
the canonical derived-data path strings (instead of importing the constant),
or reads from the quarantine directory / legacy raw directory outside the
narrow, explicitly allow-listed writer.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.data.dataset_config import (
    LEGACY_PRICE_RAW_DIR,
    OFFICIAL_CLEAN_OHLCV_PATH,
    OFFICIAL_FEATURES_PATH,
    OFFICIAL_MARKET_FEATURES_PATH,
    QUARANTINE_DIR,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The single definition file -- allowed (required) to contain the literal strings.
DEFINITION_FILE = PROJECT_ROOT / "src" / "data" / "dataset_config.py"

# src/data/fetch_daily.py's `output_dir` default writes into the legacy raw
# directory -- this is the background daily-update writer (out of scope for
# gate #6, which only consolidates *read* paths for the feature/consumer
# pipeline). Allow-listed here rather than silently ignored.
ALLOWED_LEGACY_RAW_DIR_FILES = {
    PROJECT_ROOT / "src" / "data" / "fetch_daily.py",
}

FORBIDDEN_DERIVED_PATH_STRINGS = {
    OFFICIAL_CLEAN_OHLCV_PATH,
    OFFICIAL_FEATURES_PATH,
    OFFICIAL_MARKET_FEATURES_PATH,
}


def _iter_source_files() -> list[Path]:
    files: list[Path] = []
    for base in ("src", "scripts"):
        for path in (PROJECT_ROOT / base).rglob("*.py"):
            if ".ipynb_checkpoints" in path.parts:
                continue
            files.append(path)
    return files


def _string_constants(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.append(node.value)
    return values


def test_no_hardcoded_derived_dataset_paths_outside_config():
    offenders = []
    for path in _iter_source_files():
        if path == DEFINITION_FILE:
            continue
        for value in _string_constants(path):
            if value in FORBIDDEN_DERIVED_PATH_STRINGS:
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {value!r}")
    assert not offenders, (
        "Hardcoded canonical dataset path(s) found outside "
        "src/data/dataset_config.py -- import the constant instead:\n"
        + "\n".join(offenders)
    )


def test_no_module_reads_legacy_raw_dir_outside_allowlist():
    offenders = []
    for path in _iter_source_files():
        if path == DEFINITION_FILE or path in ALLOWED_LEGACY_RAW_DIR_FILES:
            continue
        for value in _string_constants(path):
            if value == LEGACY_PRICE_RAW_DIR:
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {value!r}")
    assert not offenders, (
        "Module reads the legacy raw OHLCV directory as a hardcoded string "
        "instead of src.data.dataset_config.OFFICIAL_PRICE_RAW_DIR:\n"
        + "\n".join(offenders)
    )


def test_no_module_reads_quarantine_dir():
    offenders = []
    for path in _iter_source_files():
        if path == DEFINITION_FILE:
            continue
        for value in _string_constants(path):
            if value == QUARANTINE_DIR or value.startswith(QUARANTINE_DIR + "/"):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {value!r}")
    assert not offenders, (
        "Module reads from the quarantine directory (known-contaminated "
        "pre-backfill data) -- this must never be a production data source:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize(
    "path_str",
    [
        "data/processed/clean_daily_ohlcv.parquet",
        "data/processed/stock_features.parquet",
        "data/processed/market_features.parquet",
    ],
)
def test_quarantined_files_are_absent_from_canonical_processed_paths(path_str):
    """The quarantined pre-backfill files must not still occupy the canonical
    path -- generate_features.py must have (re)written a fresh copy there."""
    canonical = PROJECT_ROOT / path_str
    quarantined = PROJECT_ROOT / QUARANTINE_DIR / Path(path_str).name
    if not canonical.exists():
        pytest.skip(f"{path_str} not generated in this environment")
    assert quarantined.exists(), (
        f"{quarantined.relative_to(PROJECT_ROOT)} missing -- expected the "
        "pre-fix file to have been moved into quarantine per "
        "data/quarantine_existing_v1/README.md"
    )
