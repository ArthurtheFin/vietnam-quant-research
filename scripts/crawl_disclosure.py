"""CLI entrypoint for the disclosure crawler + parser + ingest pipeline (v1).

Usage:
    python scripts/crawl_disclosure.py --symbols TCB MWG TCH VHM HPG

Politeness is hard-coded, not a flag: single-threaded, >=2.5s between
requests, backs off then gives up on 429/403. See DISCLOSURE_PIPELINE_DESIGN.md
Round 4 and src/data/disclosure_client.py for the reasoning.
"""
import argparse
from pathlib import Path
import sys

import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if "PYTEST_CURRENT_TEST" in os.environ:
    PROJECT_ROOT = Path(os.getcwd())
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if "PYTEST_CURRENT_TEST" not in os.environ:
    os.chdir(PROJECT_ROOT)

from src.data.disclosure_crawler import RAW_DIR, crawl_symbols
from src.data.disclosure_ingest import EVENTS_PATH, ERRORS_PATH, ingest_events
from src.data.disclosure_parser import parse_raw_root
from src.utils.logger import get_logger

logger = get_logger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", required=True, help="Symbols to crawl, e.g. TCB MWG TCH VHM HPG")
    parser.add_argument("--raw-dir", default=str(RAW_DIR), help="Raw (immutable) tier output directory")
    parser.add_argument("--events-path", default=str(EVENTS_PATH), help="Ingested events parquet path")
    parser.add_argument("--errors-path", default=str(ERRORS_PATH), help="Rejected-rows parquet path")
    parser.add_argument("--skip-crawl", action="store_true", help="Skip the network crawl and only re-parse+ingest existing raw files")
    args = parser.parse_args(argv)

    raw_dir = Path(args.raw_dir)

    if not args.skip_crawl:
        crawl_result = crawl_symbols(args.symbols, raw_dir=raw_dir)
        logger.info("Crawl complete: %s", crawl_result)
    else:
        logger.info("--skip-crawl set: re-parsing existing raw files only, no network requests made")

    parsed_df = parse_raw_root(raw_dir)
    logger.info("Parsed %s disclosure_events rows from raw tier", len(parsed_df))

    ingest_result = ingest_events(parsed_df, events_path=Path(args.events_path), errors_path=Path(args.errors_path))
    logger.info("Ingest complete: %s", ingest_result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
