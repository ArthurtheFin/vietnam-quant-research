"""Daily incremental update for the disclosure pipeline (live mode, v1).

Usage:
    python scripts/update_disclosure_daily.py --universe
    python scripts/update_disclosure_daily.py --symbols HPG MWG

Not a scheduler -- run this by hand, or point a simple cron/launchd entry at
it once a day. No concurrency, no complex orchestration: a single script run
is enough for v1.

Each run re-fetches every symbol's current disclosure history (one polite
request per symbol, same >=2.5s pacing as the bulk crawler in
scripts/crawl_disclosure.py) and appends the new raw page snapshot to the
immutable raw tier -- nothing is ever overwritten. It then ingests ONLY
genuinely new rows (by natural key, checked against both the events and
error tables) with is_backfilled=False. This is the point where the live
branch of the ROUND 3 point-in-time rule (available_at = max(disclosure_date,
ingested_at)) starts actually running, instead of every row being backfilled.

Logs one JSON line per run to data/disclosure/daily_update_log.jsonl:
run_at, symbols attempted, fetch errors, new valid/rejected/unknown-symbol
counts.
"""
import argparse
import json
from datetime import datetime, timezone
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

from scripts.crawl_disclosure import get_universe_symbols
from src.data.disclosure_client import (
    DisclosureFetchError,
    DisclosurePoliteClient,
    DisclosureRateLimitedError,
)
from src.data.disclosure_crawler import RAW_DIR, crawl_symbol
from src.data.disclosure_ingest import EVENTS_PATH, ERRORS_PATH, UNIVERSE_DIR, ingest_new_events_live
from src.data.disclosure_parser import parse_raw_symbol_dir
from src.utils.logger import get_logger

logger = get_logger(__name__)

LOG_PATH = Path("data/disclosure/daily_update_log.jsonl")


def run_daily_update(
    symbols: list[str],
    client: DisclosurePoliteClient | None = None,
    raw_dir: Path = RAW_DIR,
    events_path: Path = EVENTS_PATH,
    errors_path: Path = ERRORS_PATH,
    universe_dir: Path = UNIVERSE_DIR,
    log_path: Path = LOG_PATH,
) -> dict:
    client = client or DisclosurePoliteClient()
    n_new_valid = n_new_rejected = n_new_unknown = 0
    n_fetch_errors = 0
    fetch_error_symbols: list[str] = []

    for raw_symbol in symbols:
        symbol = raw_symbol.upper()
        try:
            crawl_symbol(symbol, client, raw_dir=raw_dir)
        except DisclosureRateLimitedError as exc:
            logger.error("Rate limited -- stopping daily update run early at %s: %s", symbol, exc)
            fetch_error_symbols.append(symbol)
            n_fetch_errors += 1
            break
        except DisclosureFetchError as exc:
            logger.error("%s: fetch failed, skipping this symbol for today: %s", symbol, exc)
            fetch_error_symbols.append(symbol)
            n_fetch_errors += 1
            continue

        parsed = parse_raw_symbol_dir(raw_dir / symbol)
        result = ingest_new_events_live(parsed, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
        n_new_valid += result["n_new_valid"]
        n_new_rejected += result["n_new_rejected"]
        n_new_unknown += result["n_new_unknown_symbol"]
        if result["n_new_valid"] or result["n_new_rejected"]:
            logger.info(
                "%s: %s new valid, %s new rejected",
                symbol, result["n_new_valid"], result["n_new_rejected"],
            )

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "n_symbols_attempted": len(symbols),
        "n_fetch_errors": n_fetch_errors,
        "fetch_error_symbols": fetch_error_symbols,
        "n_new_valid": n_new_valid,
        "n_new_rejected": n_new_rejected,
        "n_new_unknown_symbol": n_new_unknown,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbols", nargs="+", help="Symbols to update, e.g. HPG MWG")
    group.add_argument("--universe", action="store_true", help="Update the full current universe")
    args = parser.parse_args(argv)

    symbols = args.symbols if args.symbols else get_universe_symbols()
    logger.info("Daily disclosure update: %s symbol(s)", len(symbols))
    summary = run_daily_update(symbols)
    logger.info("Daily update complete: %s", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
