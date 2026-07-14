from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from src.analytics.sector_board import audit_sector_mapping, load_sector_map
from src.data.dataset_config import OFFICIAL_FEATURES_PATH
from src.data.loaders import read_parquet
from src.utils.logger import get_logger
from src.utils.pipeline_io import build_lineage_metadata, relative_path, validate_lineage_metadata, write_json


LOGGER = get_logger("audit_sector_map")


def main() -> int:
    sector_map_file = PROJECT_ROOT / "config/sector_map.csv"
    if not sector_map_file.exists():
        raise SystemExit("config/sector_map.csv is missing. Import the provided sector map before running audit.")

    stock_features = read_parquet(PROJECT_ROOT / OFFICIAL_FEATURES_PATH)
    if stock_features.empty:
        raise SystemExit("stock_features is missing or empty. Run generate_features or the daily pipeline before auditing sector coverage.")

    sector_map, sector_map_meta = load_sector_map(PROJECT_ROOT)
    summary, missing_report = audit_sector_mapping(
        stock_features=stock_features,
        sector_map=sector_map,
        sector_map_source=sector_map_meta.get("source_path"),
    )

    output_dir = PROJECT_ROOT / "data/output"
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = output_dir / "sector_map_coverage.json"
    missing_path = output_dir / "sector_map_missing_symbols.csv"

    summary["lineage"] = validate_lineage_metadata(
        build_lineage_metadata(OFFICIAL_FEATURES_PATH, base_dir=PROJECT_ROOT),
        label="sector_map_coverage.json",
    )
    write_json(summary, coverage_path)
    missing_report.to_csv(missing_path, index=False)

    LOGGER.info("Sector map source: %s", summary.get("sector_map_source"))
    LOGGER.info(
        "Coverage summary: total=%s mapped=%s missing=%s coverage=%.2f%% unknown_ratio=%.2f%%",
        summary.get("total_symbols"),
        summary.get("mapped_symbols"),
        summary.get("missing_symbols"),
        float(summary.get("mapping_coverage", 0.0)) * 100.0,
        float(summary.get("unknown_ratio", 0.0)) * 100.0,
    )
    LOGGER.info("Coverage output: %s", relative_path(coverage_path, PROJECT_ROOT))
    LOGGER.info("Missing symbol report: %s", relative_path(missing_path, PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
