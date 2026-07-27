"""A notebook must never write an artifact the automated pipeline owns.

AUDIT_NOTEBOOKS_REPORT.md OPEN_AUTO #2/#3: notebook 12 overwrote
`data/signals/alpha_scores.parquet` and `reports/top_watchlist.csv` by hand,
two hours after the nightly pipeline produced them, leaving
`reports/alpha_scoring_metadata.json`'s lineage claim describing a file whose
on-disk schema no longer matched (`alpha_score_shadow_v1` dropped,
`rolling_beta_60d` added).

Two layers stop that now, and this module tests both:

1. `src/data/loaders.save_parquet` / `save_csv_atomic` consult
   `production_guard.guard_notebook_write()` and skip pipeline-owned writes
   when running inside a Jupyter kernel. Covers every notebook at once --
   07/09/12/14/15/16 all wrote into `data/signals/` and none of them had
   their own guard call.

2. That layer can only help if the notebook goes *through* it. A bare
   `df.to_csv(...)` / `df.to_parquet(...)` bypasses it completely -- which is
   exactly what notebook 12 did. `test_no_raw_writes_into_pipeline_dirs`
   is the static scan that keeps that from coming back.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from src.data.dataset_config import NOTEBOOK_OUTPUT_DIR, PIPELINE_OWNED_DIRS
from src.data.loaders import save_csv_atomic, save_parquet
from src.data import production_guard

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_WRITE_RE = re.compile(r"\.to_(csv|parquet)\s*\(")
# A pipeline-owned path written as a literal, e.g. "data/signals/x.parquet",
# or built from a variable whose name ends in _dir (reports_dir / "x.csv").
PIPELINE_DIR_RE = re.compile("|".join(re.escape(d) for d in PIPELINE_OWNED_DIRS))


def _notebooks() -> list[Path]:
    paths = sorted(PROJECT_ROOT.glob("notebooks/**/*.ipynb"))
    return [p for p in paths if ".ipynb_checkpoints" not in p.parts]


def _code_cells(path: Path):
    nb = json.loads(path.read_text(encoding="utf-8"))
    for index, cell in enumerate(nb.get("cells", [])):
        if cell.get("cell_type") == "code":
            yield index, "".join(cell.get("source", []))


def test_notebooks_are_discovered():
    # Guards against the scan silently becoming a no-op if the tree moves.
    assert len(_notebooks()) >= 20


def test_no_raw_writes_into_pipeline_dirs():
    """No notebook may call .to_csv()/.to_parquet() targeting a pipeline dir.

    Raw writes bypass save_parquet/save_csv_atomic and therefore bypass the
    notebook guard. Use the loaders, or write to notebooks/outputs/.
    """
    offenders: list[str] = []
    for path in _notebooks():
        for index, source in _code_cells(path):
            for match in RAW_WRITE_RE.finditer(source):
                # Look at the call itself plus a little context, since the
                # directory usually comes from a `*_dir` variable defined a
                # line or two above.
                window = source[max(0, match.start() - 400) : match.start() + 200]
                if PIPELINE_DIR_RE.search(window):
                    rel = path.relative_to(PROJECT_ROOT)
                    offenders.append(f"{rel} cell[{index}]: {match.group(0)}")
    assert not offenders, (
        "Notebook writes straight into a pipeline-owned directory, bypassing the "
        f"guarded loaders. Write to {NOTEBOOK_OUTPUT_DIR}/ instead:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "target",
    [
        "data/signals/alpha_scores.parquet",
        "data/output/client_ready_watchlist.parquet",
        "data/processed/stock_features.parquet",
        "reports/top_watchlist.csv",
    ],
)
def test_pipeline_owned_paths_are_protected(target):
    assert production_guard.is_protected_path(target)


@pytest.mark.parametrize(
    "target",
    [
        "notebooks/outputs/monte_carlo_exits.parquet",
        "notebooks/outputs/nested/thing.csv",
        "docs/reports/whatever.md",
        "data/full_history_v2/raw/AAA.parquet",
    ],
)
def test_non_pipeline_paths_are_not_protected(target):
    assert not production_guard.is_protected_path(target)


def test_scripts_are_never_treated_as_notebooks():
    """Fail-open check: the guard must not fire in a plain python process.

    A false positive here would silently stop the nightly pipeline from
    writing -- the exact failure class production_guard exists to prevent.
    """
    assert production_guard.running_in_notebook() is False
    assert production_guard.guard_notebook_write("data/signals/alpha_scores.parquet") is False


def test_notebook_write_to_pipeline_path_is_skipped(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(production_guard, "running_in_notebook", lambda: True)
    monkeypatch.delenv(production_guard.ALLOW_PRODUCTION_WRITE_ENV, raising=False)
    target = PROJECT_ROOT / "data/signals/__guard_probe__.parquet"
    assert not target.exists()

    save_parquet(pd.DataFrame({"a": [1]}), target)

    assert not target.exists(), "guard should have skipped the write"
    assert "KHONG ghi" in capsys.readouterr().out


def test_notebook_write_to_notebooks_outputs_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(production_guard, "running_in_notebook", lambda: True)
    monkeypatch.delenv(production_guard.ALLOW_PRODUCTION_WRITE_ENV, raising=False)
    target = PROJECT_ROOT / NOTEBOOK_OUTPUT_DIR / "__guard_probe__.parquet"
    try:
        save_parquet(pd.DataFrame({"a": [1]}), target)
        assert target.exists()
    finally:
        target.unlink(missing_ok=True)


def test_allow_production_write_env_reopens_the_door(monkeypatch):
    """The documented escape hatch: refreshing breakout eligibility by hand
    (OPEN_AUTO #1) requires notebook 07 to write into data/signals/."""
    monkeypatch.setattr(production_guard, "running_in_notebook", lambda: True)
    monkeypatch.setenv(production_guard.ALLOW_PRODUCTION_WRITE_ENV, "1")
    assert production_guard.guard_notebook_write("data/signals/alpha_scores.parquet") is False


def test_csv_writer_is_guarded_too(monkeypatch, capsys):
    monkeypatch.setattr(production_guard, "running_in_notebook", lambda: True)
    monkeypatch.delenv(production_guard.ALLOW_PRODUCTION_WRITE_ENV, raising=False)
    target = PROJECT_ROOT / "reports/__guard_probe__.csv"
    assert not target.exists()

    save_csv_atomic(pd.DataFrame({"a": [1]}), target)

    assert not target.exists()
    assert "KHONG ghi" in capsys.readouterr().out
