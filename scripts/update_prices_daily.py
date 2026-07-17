"""Daily incremental price update for data/full_history_v2 (live mode, v1).

Closes the root cause found in audit/ELIGIBILITY_GATE_STALE_DATA_DIAGNOSIS.md:
data/full_history_v2 was fetched in two un-reconciled batches (a main run
capped 2026-07-06, a 48-symbol supplement capped 2026-07-09/10) with no
mechanism to keep the whole universe current afterward, which caused the
eligibility gate's data_age_days check to misclassify the 411-symbol main
cohort as stale relative to the tiny fresher subset.

Usage:
    python scripts/update_prices_daily.py --universe
    python scripts/update_prices_daily.py --symbols HPG MWG

Not a scheduler -- run this by hand, or point a simple cron/launchd entry at
it once a day (see PUSH_REVIEW.md's operating-procedure note: run this
*before* generating watchlists). No concurrency, no complex orchestration.

For each symbol, fetches from its own current max(date) in
data/full_history_v2/raw/{symbol}.parquet through the latest actual trading
date (detected from VNINDEX, same pattern as scripts/update_daily_data.py),
using ONLY the single-call `get_daily_ohlc` method -- the exact mechanism
proven immune to the historical raw/adjusted-close mixing bug in
docs/reports/data/docs/reports/data/BACKFILL_DESIGN_REPORT.md (that bug lives only in the chunked
`fetch_symbol_history`/`get_daily_ohlc_chunked` fallback path, which this
script never calls; see docs/reports/data/docs/reports/data/DATA_BASELINE.md). Never re-fetches or overwrites
history before the symbol's existing max(date) -- new rows are merged in,
existing rows outside the re-fetched window are left untouched.

Checkpointed via data/full_history_v2/manifest.json (updated after every
symbol, same file the original backfill used), so a killed/resumed run
skips symbols already updated to the target date this run. Each symbol's
newly-fetched window is quality-flagged (session-count vs. the requested
window, |return| > 20% outliers) -- informational, does not block the
append. Logs one JSON line per run to
data/full_history_v2/daily_price_update_log.jsonl.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
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

import pandas as pd

from src.data.dataset_config import OFFICIAL_PRICE_RAW_DIR
from src.data.loaders import read_parquet, save_parquet
from src.utils.logger import get_logger
from src.validation.trading_status import (
    COVERAGE_RATIO_PATH,
    TRADING_STATUS_PATH,
    compute_current_gaps,
    refresh_coverage_ratios,
    update_trading_status_table,
)

logger = get_logger(__name__)

RAW_DIR = Path(OFFICIAL_PRICE_RAW_DIR)
MANIFEST_PATH = Path("data/full_history_v2/manifest.json")
LOG_PATH = Path("data/full_history_v2/daily_price_update_log.jsonl")
REQUEST_SLEEP_SECONDS = 1.2


def get_universe_symbols(raw_dir: Path = RAW_DIR) -> list[str]:
    """Delegates to src.data.universe.tracked_universe_symbols -- the single
    source of truth shared with disclosure_ingest.py's load_universe_symbols
    and scripts/crawl_disclosure.py's get_universe_symbols (audit
    PATH_TO_100.md Data Quality item). Previously read manifest.json's keys
    directly, which did not apply config/excluded_symbols.csv."""
    from src.data.universe import tracked_universe_symbols

    return tracked_universe_symbols(raw_dir=raw_dir)


def detect_latest_trading_date(client) -> pd.Timestamp | None:
    """VNINDEX-based detection, via get_daily_index (the index endpoint --
    get_daily_ohlc is stock-only and returns empty for index codes)."""
    five_days_ago = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    today_str = date.today().strftime("%Y-%m-%d")
    try:
        vnindex_df = client.get_daily_index("VNINDEX", five_days_ago, today_str, page_size=100, max_pages=2)
    except Exception as exc:
        logger.error("Could not detect latest trading date from VNINDEX: %s", exc)
        return None
    if vnindex_df.empty:
        return None
    return pd.to_datetime(vnindex_df["tradingdate"], dayfirst=True, errors="coerce").max()


def _quality_flags(new_rows: pd.DataFrame) -> list[str]:
    """Informational only -- does not block the append."""
    flags: list[str] = []
    if new_rows.empty:
        return flags
    close = pd.to_numeric(new_rows["close"], errors="coerce")
    ret = close.pct_change()
    n_outliers = int((ret.abs() > 0.20).sum())
    if n_outliers:
        flags.append(f"OUTLIER_RETURN_GT_20PCT:{n_outliers}")
    if pd.to_numeric(new_rows["volume"], errors="coerce").le(0).all():
        flags.append("ALL_ZERO_VOLUME_IN_WINDOW")
    return flags


def update_one_symbol(
    symbol: str,
    client,
    latest_trading_date: pd.Timestamp,
    raw_dir: Path,
) -> dict:
    path = raw_dir / f"{symbol}.parquet"
    if not path.exists():
        return {"symbol": symbol, "status": "MISSING_RAW_FILE", "new_rows": 0}

    old_df = read_parquet(path)
    old_df["date"] = pd.to_datetime(old_df["date"])
    old_max = old_df["date"].max()

    if pd.isna(old_max) or old_max >= latest_trading_date:
        return {"symbol": symbol, "status": "ALREADY_CURRENT", "new_rows": 0, "date_max": str(old_max.date()) if not pd.isna(old_max) else None}

    fetch_start = old_max.strftime("%Y-%m-%d")
    fetch_end = latest_trading_date.strftime("%Y-%m-%d")
    try:
        # Single direct call only -- never get_daily_ohlc_chunked/fetch_symbol_history
        # (the chunked fallback path is where the raw/adjusted-close mixing bug lived).
        new_df = client.get_daily_ohlc(symbol, fetch_start, fetch_end, page_size=1000, max_pages=3)
    except Exception as exc:
        return {"symbol": symbol, "status": "FETCH_ERROR", "error": str(exc), "new_rows": 0}

    if new_df.empty:
        return {"symbol": symbol, "status": "EMPTY_RESPONSE", "new_rows": 0, "date_max": str(old_max.date())}

    date_col = "tradingdate" if "tradingdate" in new_df.columns else "date"
    new_df = new_df.copy()
    new_df["date"] = pd.to_datetime(new_df[date_col], dayfirst=True, errors="coerce")
    new_df = new_df.dropna(subset=["date"])

    merged = pd.concat([old_df[old_df["date"] < new_df["date"].min()], new_df], ignore_index=True)
    merged = merged.sort_values("date").drop_duplicates(subset="date", keep="last").reset_index(drop=True)
    new_max = merged["date"].max()

    if new_max <= old_max:
        # Fetch succeeded but returned no session past the existing max --
        # e.g. a long-inactive/suspended symbol with no new matched-volume
        # trading day. Not an error, not a change: leave the file/manifest
        # untouched so a repeat run reports this the same clean way (no
        # false "UPDATED" churn in the log for symbols that never trade).
        return {"symbol": symbol, "status": "NO_NEW_DATA", "new_rows": 0, "date_max": str(old_max.date())}

    save_parquet(merged, path)
    flags = _quality_flags(new_df)
    n_new_rows = len(merged) - len(old_df[old_df["date"] < new_df["date"].min()])
    return {
        "symbol": symbol,
        "status": "UPDATED",
        "new_rows": int(len(new_df)),
        "total_rows": int(len(merged)),
        "date_max": str(new_max.date()),
        "quality_flags": flags,
    }


def run_daily_price_update(
    symbols: list[str],
    client=None,
    raw_dir: Path = RAW_DIR,
    manifest_path: Path = MANIFEST_PATH,
    log_path: Path = LOG_PATH,
    request_sleep: float = REQUEST_SLEEP_SECONDS,
    status_path: Path = TRADING_STATUS_PATH,
    coverage_ratio_path: Path = COVERAGE_RATIO_PATH,
) -> dict:
    import time as _time

    if client is None:
        from src.data.ssi_client import SSIDataClient
        client = SSIDataClient()

    latest_trading_date = detect_latest_trading_date(client)
    if latest_trading_date is None:
        summary = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "status": "ABORTED_NO_LATEST_DATE",
            "n_symbols_attempted": 0,
        }
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        return summary

    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    results: list[dict] = []
    t0 = _time.time()
    for i, symbol in enumerate(symbols):
        result = update_one_symbol(symbol, client, latest_trading_date, raw_dir)
        results.append(result)
        if result["status"] == "UPDATED":
            manifest.setdefault(symbol, {})
            manifest[symbol]["row_count"] = result["total_rows"]
            manifest[symbol]["date_max"] = result["date_max"]
            manifest[symbol]["daily_update_at"] = datetime.now(timezone.utc).isoformat()
            if result.get("quality_flags"):
                manifest[symbol]["quality_flags"] = result["quality_flags"]
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        logger.info(
            "[%.0fs] (%s/%s) %s: %s",
            _time.time() - t0, i + 1, len(symbols), symbol, result["status"],
        )
        if result["status"] not in ("ALREADY_CURRENT", "MISSING_RAW_FILE"):
            _time.sleep(request_sleep)

    # Recompute every symbol's gap-to-latest and update the point-in-time
    # trading_status table (audit PATH_TO_100.md Universe/Eligibility item)
    # -- ALL symbols, not just ones touched this run, since a symbol's
    # status can change (e.g. ACTIVE -> STALE_SHORT) purely from time
    # passing without it being individually re-fetched.
    current_gaps = compute_current_gaps(raw_dir, latest_trading_date)
    trading_status_result = update_trading_status_table(current_gaps, status_path=status_path)

    # Coverage-ratio proxy (audit PATH_TO_100.md Universe/Eligibility item):
    # expensive (scans every symbol's full raw history), so refreshed once
    # here per run rather than computed inside the eligibility gate.
    refresh_coverage_ratios(raw_dir, latest_trading_date, path=coverage_ratio_path)

    n_updated = sum(1 for r in results if r["status"] == "UPDATED")
    n_already_current = sum(1 for r in results if r["status"] == "ALREADY_CURRENT")
    n_no_new_data = sum(1 for r in results if r["status"] == "NO_NEW_DATA")
    n_errors = sum(1 for r in results if r["status"] == "FETCH_ERROR")
    n_empty = sum(1 for r in results if r["status"] == "EMPTY_RESPONSE")
    n_missing = sum(1 for r in results if r["status"] == "MISSING_RAW_FILE")
    total_new_rows = sum(r.get("new_rows", 0) for r in results)
    quality_flagged = [r["symbol"] for r in results if r.get("quality_flags")]

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "latest_trading_date": str(latest_trading_date.date()),
        "n_symbols_attempted": len(symbols),
        "n_updated": n_updated,
        "n_already_current": n_already_current,
        "n_no_new_data": n_no_new_data,
        "n_fetch_errors": n_errors,
        "n_empty_response": n_empty,
        "n_missing_raw_file": n_missing,
        "total_new_rows": total_new_rows,
        "quality_flagged_symbols": quality_flagged,
        "fetch_error_symbols": [r["symbol"] for r in results if r["status"] == "FETCH_ERROR"],
        "trading_status_new_rows": trading_status_result["n_new_rows"],
        "elapsed_seconds": round(_time.time() - t0, 1),
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--symbols", nargs="+", help="Symbols to update, e.g. HPG MWG")
    group.add_argument("--universe", action="store_true", help="Update the full tracked universe")
    args = parser.parse_args(argv)

    symbols = args.symbols if args.symbols else get_universe_symbols()
    logger.info("Daily price update: %s symbol(s)", len(symbols))
    summary = run_daily_price_update(symbols)
    logger.info("Daily price update complete: %s", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
