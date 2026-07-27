"""Guard against notebooks silently overwriting shared production data files.

Incident this fixes (docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md,
NV1): running `notebooks/02_market_research/05_volatility_regime.ipynb` or
`06_market_regime.ipynb` by hand -- via `jupyter nbconvert --execute` or a
normal interactive session -- silently overwrote the real
`data/processed/stock_features.parquet` / `market_features.parquet` with
incomplete or stale-logic data, because each notebook `os.chdir()`s to the
project root and then calls `save_parquet()` with a relative path that
happens to match the canonical production path. There was no warning, no
prompt, nothing to distinguish it from `scripts/generate_features.py`'s own
(correct) write to the same path.

`PROTECTED_PATHS` covers exactly the three canonical paths defined once in
`src.data.dataset_config` (not re-typed here, so
`tests/test_dataset_config.py`'s hardcode scanner keeps this file honest).
Only `scripts/generate_features.py` is meant to write to them; anything else
-- a notebook run by hand, an ad-hoc script -- must opt in explicitly.
"""
from __future__ import annotations

import os
from pathlib import Path

from src.data.dataset_config import (
    NOTEBOOK_OUTPUT_DIR,
    OFFICIAL_CLEAN_OHLCV_PATH,
    OFFICIAL_FEATURES_PATH,
    OFFICIAL_MARKET_FEATURES_PATH,
    PIPELINE_OWNED_DIRS,
)

ALLOW_PRODUCTION_WRITE_ENV = "ALLOW_PRODUCTION_WRITE"

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    return p.resolve()


# Single source of truth for *which* paths are protected -- derived from
# dataset_config.py's constants, not re-typed as string literals.
#
# The three exact paths stay listed explicitly: they are the canonical
# generate_features.py outputs and carry their own incident history
# (MARKET_REGIME_AUDIT.md). They are also inside PROTECTED_DIRS now, so this
# set is redundant for matching -- kept because the error message and
# tests/test_dataset_config.py's scanner both key off these constants.
PROTECTED_PATHS = frozenset(
    _resolve(p)
    for p in (OFFICIAL_CLEAN_OHLCV_PATH, OFFICIAL_FEATURES_PATH, OFFICIAL_MARKET_FEATURES_PATH)
)

# Whole directories the automated pipeline owns (AUDIT_NOTEBOOKS_REPORT.md
# OPEN_AUTO #2/#3). Path-exact protection was not enough: the incident was a
# notebook writing data/signals/alpha_scores.parquet and reports/top_watchlist.csv,
# neither of which was in PROTECTED_PATHS.
PROTECTED_DIRS = tuple(_resolve(d) for d in PIPELINE_OWNED_DIRS)

# The sanctioned escape valve -- notebooks write here freely.
NOTEBOOK_OUTPUT_PATH = _resolve(NOTEBOOK_OUTPUT_DIR)


def _is_under(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def running_in_notebook() -> bool:
    """True when executing inside a Jupyter kernel (interactive or nbconvert).

    Deliberately fail-open: anything we cannot positively identify as a Jupyter
    kernel is treated as "not a notebook", so a plain `python scripts/...` run
    can never be blocked by a misdetection. A false negative here just restores
    the old behaviour; a false positive would silently stop the nightly pipeline
    from writing, which is the exact class of failure this module exists to
    prevent.

    `ZMQInteractiveShell` is the Jupyter kernel shell -- covers both an
    interactive notebook and `jupyter nbconvert --execute`. A plain IPython
    terminal (`TerminalInteractiveShell`) is not a notebook and is not blocked.
    """
    try:
        from IPython import get_ipython
    except Exception:
        return False
    try:
        shell = get_ipython()
    except Exception:
        return False
    return shell is not None and type(shell).__name__ == "ZMQInteractiveShell"


class ProductionWriteBlocked(RuntimeError):
    """Raised when something outside the official pipeline tries to
    overwrite a protected production data file without opting in."""


def is_protected_path(path: str | Path) -> bool:
    """True if `path` is a canonical production file or sits inside a
    pipeline-owned directory (`data/processed`, `data/signals`, `data/output`,
    `reports`). `notebooks/outputs/` is never protected."""
    resolved = _resolve(path)
    if _is_under(resolved, NOTEBOOK_OUTPUT_PATH):
        return False
    if resolved in PROTECTED_PATHS:
        return True
    return any(_is_under(resolved, d) for d in PROTECTED_DIRS)


def guard_notebook_write(path: str | Path) -> bool:
    """Whether a write to `path` from the current process must be skipped.

    The rule (AUDIT_NOTEBOOKS_REPORT.md OPEN_AUTO #2/#3): a notebook may not
    write anything the automated pipeline produces or consumes. Applied at the
    `save_parquet`/`save_csv_atomic` layer so it holds for every notebook
    without each one needing its own guard call -- notebooks 07/09/14/15/16 all
    write pipeline-owned paths and none of them had one.

    Returns True (caller should skip the write) only when ALL of:
      - we are positively inside a Jupyter kernel, and
      - the target is pipeline-owned, and
      - ALLOW_PRODUCTION_WRITE=1 was not set.

    Skips rather than raises so `make check-notebooks` stays green: the
    established idiom in 05/06 is guard -> catch -> print -> continue, and
    turning every such notebook red would just get the guard disabled.
    """
    if not running_in_notebook():
        return False
    if is_production_write_allowed():
        return False
    return is_protected_path(path)


def is_production_write_allowed() -> bool:
    """Whether the environment has explicitly opted into production writes
    (`ALLOW_PRODUCTION_WRITE=1`). Does not check whether a specific path is
    protected -- pair with `is_protected_path`/`guard_production_write`."""
    return os.environ.get(ALLOW_PRODUCTION_WRITE_ENV) == "1"


def guard_production_write(path: str | Path, allow: bool | None = None) -> None:
    """Raise `ProductionWriteBlocked` if `path` is a protected production
    file and the write hasn't been explicitly allowed.

    No-op (returns normally) for any path that isn't one of the protected
    paths -- safe to call unconditionally before any `save_parquet()`.

    `allow`, if given, overrides the environment check (so a caller that
    already knows it's authorized -- e.g. a future production script -- can
    pass `allow=True` directly instead of setting an env var). Default
    (`None`) falls back to `is_production_write_allowed()`.
    """
    if not is_protected_path(path):
        return
    if allow is None:
        allow = is_production_write_allowed()
    if not allow:
        raise ProductionWriteBlocked(
            f"Refusing to write {path} -- this is a shared production file "
            f"read by ~20 other scripts/modules (build_portfolio_stack.py, "
            f"run_alpha_scoring.py, final_watchlist.py, ...). The canonical "
            f"way to regenerate it is `python scripts/generate_features.py`, "
            f"not this notebook. If you really mean to overwrite it by hand "
            f"(e.g. debugging), set {ALLOW_PRODUCTION_WRITE_ENV}=1 before "
            f"starting the kernel, or pass allow=True to "
            f"guard_production_write(). See "
            f"docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md for the "
            f"incident this guards against."
        )
