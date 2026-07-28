from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

import argparse

from src.analytics.cashflow_board import (
    attach_sector,
    build_cashflow_board,
    compute_symbol_cashflow_metrics,
    load_cashflow_inputs,
    write_cashflow_outputs,
)
from src.data.loaders import save_parquet
from src.screening.final_watchlist import apply_post_cashflow_overlay
from src.utils.logger import get_logger
from src.utils.pipeline_io import utc_now_iso, write_json
from src.validation.freshness_check import DerivedArtifactStale, assert_input_chain_fresh

LOGGER = get_logger("build_cashflow_board")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build cashflow board outputs.")
    parser.add_argument(
        "--symbol-only",
        action="store_true",
        help="Only build the symbol-level cashflow board (no watchlist tiers needed). "
        "Runs before meta ranking so the eligibility gate sees a same-day board (audit F1).",
    )
    args = parser.parse_args(argv)

    LOGGER.info("Loading inputs for Cashflow Board...")
    inputs = load_cashflow_inputs(PROJECT_ROOT)

    stock_features = inputs["stock_features"]
    if stock_features.empty:
        raise SystemExit("stock_features is missing or empty. Run the daily pipeline / generate_features before building Cashflow Board.")

    # Input-chain freshness (CLAUDE.md rule 12 / Đợt 3 NV2) -- emptiness was
    # checked, currency was not.
    try:
        assert_input_chain_fresh(PROJECT_ROOT, consumer="build_cashflow_board")
    except DerivedArtifactStale as exc:
        raise SystemExit(str(exc)) from exc

    if args.symbol_only:
        LOGGER.info("Building symbol-level Cashflow Board (pre-ranking pass)...")
        attached, _attach_meta = attach_sector(stock_features, sector_map=inputs["sector_map"])
        symbol_cf, value_proxy_used = compute_symbol_cashflow_metrics(
            attached, benchmark_df=inputs["benchmark_vnindex"]
        )
        if symbol_cf.empty:
            raise SystemExit("Symbol-level cashflow board is empty; check stock_features content.")
        out_dir = PROJECT_ROOT / "data/output"
        out_dir.mkdir(parents=True, exist_ok=True)
        save_parquet(symbol_cf, out_dir / "cashflow_board.parquet")
        symbol_cf.to_csv(out_dir / "cashflow_board.csv", index=False)
        latest = symbol_cf["date"].max() if "date" in symbol_cf.columns else None
        LOGGER.info(
            "Symbol-only cashflow board written: %s symbols, latest date %s, value proxy used: %s",
            symbol_cf["symbol"].nunique(), latest, value_proxy_used,
        )

        # Keep the sidecar honest (AUDIT_NOTEBOOKS_REPORT.md Đợt 4 NV3). This
        # branch rewrites cashflow_board.parquet/.csv but produces none of the
        # sector/watchlist outputs, so it must not write a full metadata payload
        # -- yet leaving the file untouched meant cashflow_board_metadata.json
        # kept describing an older full-mode run while the two files on disk had
        # been replaced by this pass. It runs as step 6/7 of every nightly
        # pipeline, so the sidecar was stale-by-construction every night.
        # Annotate rather than overwrite: the full-mode payload stays intact for
        # its own outputs, plus a record of what this pass actually replaced.
        metadata_path = out_dir / "cashflow_board_metadata.json"
        if metadata_path.exists():
            try:
                existing = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                existing = {}
            existing["symbol_only_pass"] = {
                "generated_at": utc_now_iso(),
                "latest_date": str(latest) if latest is not None else None,
                "symbol_count": int(symbol_cf["symbol"].nunique()),
                "value_proxy_used": bool(value_proxy_used),
                "overwrote_files": [
                    "data/output/cashflow_board.parquet",
                    "data/output/cashflow_board.csv",
                ],
                "note": (
                    "These two files come from the symbol-only pass, not from the "
                    "full-mode run described by the top-level keys."
                ),
            }
            write_json(existing, metadata_path)
            LOGGER.info("Annotated %s with this symbol-only pass.", metadata_path.name)
        return 0

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

    # Apply post-cashflow eligibility overlay
    apply_post_cashflow_overlay(PROJECT_ROOT)

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
