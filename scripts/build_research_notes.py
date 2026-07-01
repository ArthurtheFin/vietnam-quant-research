from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from src.reporting.research_notes import (
    generate_research_notes,
    load_research_inputs,
    write_research_notes_outputs,
)
from src.utils.logger import get_logger

LOGGER = get_logger("build_research_notes")


def main() -> int:
    LOGGER.info("Loading inputs for Research Notes...")
    inputs = load_research_inputs(PROJECT_ROOT)
    
    client_ready = inputs["client_ready_watchlist"]
    if client_ready.empty:
        LOGGER.warning("client_ready_watchlist is missing or empty. No research notes will be generated.")
        
    template_path = PROJECT_ROOT / "research_notes/templates/stock_research_note_template.md"
    if not template_path.exists():
        raise SystemExit("stock_research_note_template.md is missing. Run directory setup first.")
        
    template_str = template_path.read_text(encoding="utf-8")
    
    LOGGER.info("Generating Research Notes narratives...")
    index_df, notes_dict = generate_research_notes(inputs, template_str)
    
    latest_date = "UNKNOWN"
    if not index_df.empty:
        latest_date = str(index_df["latest_date"].iloc[0])
        
    warnings = []
    # Check for missing input files
    for name, val in inputs.items():
        if isinstance(val, dict):
            if not val:
                warnings.append(f"Missing JSON payload metadata for: {name}")
        elif isinstance(val, Path) or val is None:
            pass
        else:
            if val.empty and name in ("cashflow_board", "watchlist_cashflow_confirmation", "sector_board"):
                warnings.append(f"Parquet table is empty: {name}")
                
    status = "OK"
    if warnings:
        status = "WARNING"
        
    metadata = {
        "generated_at": "", # Filled by write helper using utc_now_iso
        "status": status,
        "latest_date": latest_date,
        "n_notes_generated": len(notes_dict),
        "warnings": warnings,
        "generated_files": [],
    }
    
    LOGGER.info("Writing Research Notes outputs...")
    payload = write_research_notes_outputs(
        index_df=index_df,
        notes_dict=notes_dict,
        metadata=metadata,
        base_dir=PROJECT_ROOT,
    )
    
    LOGGER.info("Research Notes build status: %s", payload.get("status"))
    LOGGER.info("Notes generated: %s", payload.get("n_notes_generated"))
    LOGGER.info("Symbols generated: %s", ", ".join(notes_dict.keys()) if notes_dict else "None")
    
    if payload.get("warnings"):
        LOGGER.warning("Research Notes warnings: %s", "; ".join(payload["warnings"]))
        
    return 0 if payload.get("status") != "ERROR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
