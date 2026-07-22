"""Structural CI check: run every notebook top-to-bottom in an isolated
sandbox and report which ones fail (docs/reports/codebase_audit/NOTEBOOK_AUDIT_FULL.md NV3).

Why this exists: the full notebook audit (2026-07-21) found 4 notebooks
broken by src/ signature drift (ModuleNotFoundError, missing required
argument, missing column) that had gone unnoticed since the code changed --
each was only caught by a manual, one-off audit. This script makes that
check repeatable: run it whenever a function signature that a notebook calls
changes, instead of waiting for the next manual audit to notice.

Isolation: every notebook is executed inside an rsync copy of the repo
(code + data, never .git), never against the real project directory --
same discipline as the manual audit this replaces (see
docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md's "Su co trong luc audit"
for the incident this guards against). The sandbox is refreshed from the
real project before every notebook so one notebook's writes can't
contaminate the next one's input.

Usage:
    python scripts/check_notebooks.py                 # skip live-API notebooks (default)
    python scripts/check_notebooks.py --include-live   # also run the live-API ones
    python scripts/check_notebooks.py --only notebooks/03_alpha_signals/07_breakout_research.ipynb
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KERNEL_NAME = "vnquant"
DEFAULT_TIMEOUT_S = 300

# Notebooks confirmed (2026-07-21/22 audit) to need much longer than the
# default nbconvert timeout because they run a real full-universe grid-search
# backtest, not because anything is wrong -- see NOTEBOOK_AUDIT_FULL.md.
# 19_validation_and_stress_test.ipynb measured at ~51 real minutes (its cell
# stacks run_breakout_research + 3 more sensitivity/cost/risk sweeps in one
# cell/one timeout budget) -- given 4500s here, not 1800s like its siblings.
LONG_TIMEOUT_NOTEBOOKS: dict[str, int] = {
    "notebooks/03_alpha_signals/07_breakout_research.ipynb": 1800,
    "notebooks/03_alpha_signals/09_stealth_accumulation_screen.ipynb": 1800,
    "notebooks/04_watchlist_portfolio/19_validation_and_stress_test.ipynb": 4500,
}

# Notebooks that make live, real (not mocked) external API calls with no
# built-in bound (SSI FCData) -- skipped by default so this check stays fast
# and free of network side effects; pass --include-live to run them anyway.
LIVE_API_NOTEBOOKS: set[str] = {
    "notebooks/00_archive/02_fetch_daily_ohlcv.ipynb",
    "notebooks/01_data_pipeline/01_validate_environment.ipynb",
}


def discover_notebooks() -> list[str]:
    paths = sorted(PROJECT_ROOT.glob("notebooks/**/*.ipynb")) + sorted(
        PROJECT_ROOT.glob("stock-decision-engine/notebooks/*.ipynb")
    )
    return [
        str(p.relative_to(PROJECT_ROOT))
        for p in paths
        if ".ipynb_checkpoints" not in str(p)
    ]


def sync_sandbox(sandbox: Path) -> None:
    subprocess.run(
        [
            "rsync", "-a", "--delete",
            "--exclude=.git/", "--exclude=.claude/",
            f"{PROJECT_ROOT}/", f"{sandbox}/",
        ],
        check=True,
    )


def run_one(sandbox: Path, relpath: str, timeout_s: int) -> tuple[bool, str, float]:
    nbpath = sandbox / relpath
    start = time.monotonic()
    proc = subprocess.run(
        [
            "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
            f"--ExecutePreprocessor.timeout={timeout_s}",
            f"--ExecutePreprocessor.kernel_name={KERNEL_NAME}",
            str(nbpath),
        ],
        capture_output=True, text=True,
    )
    elapsed = time.monotonic() - start
    ok = proc.returncode == 0
    tail = "" if ok else "\n".join(proc.stderr.strip().splitlines()[-15:])
    return ok, tail, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-live", action="store_true",
                         help="also run notebooks that make live external API calls")
    parser.add_argument("--only", action="append", default=None,
                         help="only check this notebook (relative path); may repeat")
    args = parser.parse_args()

    notebooks = args.only if args.only else discover_notebooks()

    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="check_notebooks_") as tmp:
        sandbox = Path(tmp) / "sandbox"
        for relpath in notebooks:
            if not args.include_live and relpath in LIVE_API_NOTEBOOKS and not args.only:
                results.append({"notebook": relpath, "status": "SKIPPED (live API, pass --include-live to run)"})
                continue
            timeout_s = LONG_TIMEOUT_NOTEBOOKS.get(relpath, DEFAULT_TIMEOUT_S)
            print(f"[check_notebooks] syncing sandbox before {relpath} ...", file=sys.stderr)
            sync_sandbox(sandbox)
            print(f"[check_notebooks] running {relpath} (timeout={timeout_s}s) ...", file=sys.stderr)
            ok, tail, elapsed = run_one(sandbox, relpath, timeout_s)
            results.append({
                "notebook": relpath,
                "status": "PASS" if ok else "FAIL",
                "seconds": round(elapsed, 1),
                "error_tail": tail if not ok else None,
            })

    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_skip = sum(1 for r in results if r["status"].startswith("SKIPPED"))

    print("\n=== check_notebooks summary ===")
    for r in results:
        line = f"{r['status']:<8} {r['notebook']}"
        if r.get("seconds") is not None:
            line += f"  ({r['seconds']}s)"
        print(line)
        if r["status"] == "FAIL":
            print("  --- last lines of traceback ---")
            for l in (r["error_tail"] or "").splitlines():
                print(f"  {l}")

    print(f"\n{n_pass} passed, {n_fail} failed, {n_skip} skipped ({len(results)} total)")

    log_path = PROJECT_ROOT / "logs" / "check_notebooks_last_run.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Full results written to {log_path}")

    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
