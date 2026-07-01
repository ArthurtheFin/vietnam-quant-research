from __future__ import annotations

import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from src.utils.pipeline_io import compare_run_snapshots, load_run_snapshots


def main() -> int:
    snapshots = load_run_snapshots(base_dir=PROJECT_ROOT, limit=2)
    if len(snapshots) < 2:
        print(
            json.dumps(
                {
                    "status": "INSUFFICIENT_HISTORY",
                    "message": "Need at least two run snapshots in data/output/run_history/ to compare.",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    previous, current = snapshots[0], snapshots[1]
    comparison = compare_run_snapshots(previous=previous, current=current)
    print(json.dumps(comparison, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
