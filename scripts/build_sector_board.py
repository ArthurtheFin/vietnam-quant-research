from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from src.analytics.sector_board import (
    build_sector_board,
    load_sector_board_inputs,
    write_sector_outputs,
)
from src.utils.logger import get_logger


LOGGER = get_logger("build_sector_board")


def main() -> int:
    inputs = load_sector_board_inputs(PROJECT_ROOT)
    stock_features = inputs["stock_features"]
    if stock_features.empty:
        raise SystemExit("stock_features is missing or empty. Run the daily pipeline / generate_features before building Sector Board.")

    board, leaders, metadata = build_sector_board(
        stock_features=inputs["stock_features"],
        benchmark_vnindex=inputs["benchmark_vnindex"],
        client_ready=inputs["client_ready"],
        trading_watchlist=inputs["trading_watchlist"],
        research_candidates=inputs["research_candidates"],
        sector_map=inputs["sector_map"],
        sector_map_metadata=inputs["sector_map_metadata"],
    )
    payload = write_sector_outputs(
        sector_board=board,
        sector_leaders=leaders,
        metadata=metadata,
        base_dir=PROJECT_ROOT,
    )

    LOGGER.info("Sector Board status: %s", payload.get("status"))
    LOGGER.info("Sector Board latest date: %s", payload.get("latest_date"))
    LOGGER.info("Sector count: %s", payload.get("n_sectors"))
    LOGGER.info(
        "Sector map coverage: mapped=%s total=%s coverage=%.2f%% unknown_ratio=%.2f%%",
        payload.get("mapped_symbols"),
        payload.get("total_symbols"),
        float(payload.get("mapping_coverage", 0.0)) * 100.0,
        float(payload.get("unknown_ratio", 0.0)) * 100.0,
    )
    if payload.get("warnings"):
        LOGGER.warning("Sector Board warnings: %s", "; ".join(str(item) for item in payload["warnings"]))
    LOGGER.info("Sector Board generated files: %s", ", ".join(payload.get("generated_files", [])))
    return 0 if payload.get("status") != "ERROR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
