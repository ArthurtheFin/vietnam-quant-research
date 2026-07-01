from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from src.analytics.cashflow_board import (
    build_cashflow_board,
    load_cashflow_inputs,
    write_cashflow_outputs,
)
from src.utils.logger import get_logger

LOGGER = get_logger("build_cashflow_board")


def main() -> int:
    LOGGER.info("Loading inputs for Cashflow Board...")
    inputs = load_cashflow_inputs(PROJECT_ROOT)
    
    stock_features = inputs["stock_features"]
    if stock_features.empty:
        raise SystemExit("stock_features is missing or empty. Run the daily pipeline / generate_features before building Cashflow Board.")

    LOGGER.info("Building Cashflow Board...")
    symbol_cf, sector_cf, watchlist_confirm, metadata = build_cashflow_board(
        stock_features=inputs["stock_features"],
        benchmark_vnindex=inputs["benchmark_vnindex"],
        client_ready=inputs["client_ready"],
        trading_watchlist=inputs["trading_watchlist"],
        research_candidates=inputs["research_candidates"],
        sector_map=inputs["sector_map"],
        sector_map_metadata=inputs["sector_map_metadata"],
    )
    
    LOGGER.info("Writing Cashflow Board outputs...")
    payload = write_cashflow_outputs(
        cashflow_board=symbol_cf,
        sector_cashflow=sector_cf,
        watchlist_confirmation=watchlist_confirm,
        metadata=metadata,
        base_dir=PROJECT_ROOT,
    )

    LOGGER.info("Cashflow Board build status: %s", payload.get("status"))
    LOGGER.info("Latest date in data: %s", payload.get("latest_date"))
    LOGGER.info("Symbol count: %s", payload.get("n_symbols"))
    LOGGER.info("Sector count: %s", payload.get("n_sectors"))
    LOGGER.info("Value proxy used: %s", payload.get("value_proxy_used"))
    
    LOGGER.info("Data Quality Warnings: %s", payload.get("n_data_quality_warnings"))
    LOGGER.info("Low Liquidity Symbols: %s", payload.get("n_low_liquidity_symbols"))
    LOGGER.info("Zero Volume Symbols: %s", payload.get("n_zero_volume_symbols"))
    
    confirmation_counts = payload.get("confirmation_counts", {})
    if confirmation_counts:
        LOGGER.info("Watchlist Confirmation Counts: %s", ", ".join(f"{k}={v}" for k, v in confirmation_counts.items()))
        
    sector_score_warnings = payload.get("sector_score_warnings", [])
    if sector_score_warnings:
        LOGGER.warning("Sector Score Warnings:\n  %s", "\n  ".join(sector_score_warnings))
    
    if payload.get("warnings"):
        LOGGER.warning("Cashflow Board warnings: %s", "; ".join(str(item) for item in payload["warnings"]))
        
    LOGGER.info("Generated files: %s", ", ".join(payload.get("generated_files", [])))
    return 0 if payload.get("status") != "ERROR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
