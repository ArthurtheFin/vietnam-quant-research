from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.data.disclosure_client import (
    DisclosureFetchError,
    DisclosurePoliteClient,
    DisclosureRateLimitedError,
)
from src.data.loaders import ensure_parent
from src.utils.logger import get_logger

logger = get_logger(__name__)

RAW_DIR = Path("data/disclosure/raw")
MANIFEST_PATH = RAW_DIR / "manifest.json"
DEFAULT_PAGE_SIZE = 2000
DEFAULT_MAX_PAGES = 20


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(manifest: dict[str, Any], path: Path = MANIFEST_PATH) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _parse_envelope(text: str, symbol: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        logger.error("%s: response was not valid JSON", symbol)
        return None
    data = obj.get("Data")
    if not isinstance(data, dict):
        logger.error("%s: unexpected envelope shape (no 'Data' dict)", symbol)
        return None
    return data


def crawl_symbol(
    symbol: str,
    client: DisclosurePoliteClient,
    raw_dir: Path = RAW_DIR,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    """Fetch one symbol's full disclosure history.

    Requests full history (blank start/end date) with a large page size --
    verified during the pilot that CafeF returns the symbol's entire history
    in a single response for every size of company tried (up to 352 rows for
    MWG). Only paginates further if TotalCount exceeds what came back, so a
    v1 run of this against a handful of large caps costs one request per
    symbol in the common case, not one request per 20-row page.

    Each page response is written verbatim and immutably: raw JSON text plus
    url/fetched_at/status_code, one file per page, never edited after being
    written. Re-parsing (e.g. after the parser's field logic improves) never
    requires re-crawling.
    """
    symbol = symbol.upper()
    pages_written: list[str] = []
    total_count: int | None = None
    rows_seen = 0
    page_index = 1
    while True:
        response = client.fetch(symbol, page_index=page_index, page_size=page_size)
        payload = _parse_envelope(response.text, symbol)
        if payload is None:
            raise DisclosureFetchError(f"{symbol}: page {page_index} did not return a parseable JSON envelope")
        if total_count is None:
            total_count = int(payload.get("TotalCount", 0) or 0)
        rows = payload.get("Data") or []
        rows_seen += len(rows)

        symbol_dir = raw_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        safe_fetched_at = response.fetched_at.replace(":", "").replace("+00:00", "Z")
        out_path = symbol_dir / f"page{page_index:02d}_{safe_fetched_at}.json"
        out_path.write_text(
            json.dumps(
                {
                    "symbol": symbol,
                    "url": response.url,
                    "fetched_at": response.fetched_at,
                    "page_index": page_index,
                    "page_size": page_size,
                    "status_code": response.status_code,
                    "raw_response": response.text,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        pages_written.append(str(out_path))

        if not rows or rows_seen >= total_count or page_index >= max_pages:
            break
        page_index += 1

    return {
        "status": "ok",
        "symbol": symbol,
        "total_count": total_count,
        "rows_seen": rows_seen,
        "pages": pages_written,
    }


def crawl_symbols(
    symbols: list[str],
    client: DisclosurePoliteClient | None = None,
    raw_dir: Path = RAW_DIR,
    manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    """Checkpoint/resume crawl over a list of symbols -- same pattern as the
    full_history_v2 price backfill (scratch/full_backfill_v2.py): one
    manifest entry per symbol, saved to disk after every single symbol (a
    crash loses at most the in-flight one), and a re-run skips anything
    already marked 'status: ok'.

    A repeated 429/403 (DisclosureRateLimitedError) stops the whole crawl
    immediately rather than moving to the next symbol -- per the politeness
    constraint, a block signal applies to the whole run, not just one name.
    """
    client = client or DisclosurePoliteClient()
    manifest = load_manifest(manifest_path)
    n_ok = n_error = n_skipped = 0
    for symbol in symbols:
        symbol = symbol.upper()
        if manifest.get(symbol, {}).get("status") == "ok":
            n_skipped += 1
            continue
        try:
            result = crawl_symbol(symbol, client, raw_dir=raw_dir)
            manifest[symbol] = result
            n_ok += 1
            logger.info(
                "%s: crawled OK (%s rows across %s page(s))",
                symbol, result["rows_seen"], len(result["pages"]),
            )
        except DisclosureRateLimitedError as exc:
            manifest[symbol] = {"status": "error", "symbol": symbol, "error": str(exc)}
            save_manifest(manifest, manifest_path)
            logger.error("Stopping crawl early -- rate limited: %s", exc)
            raise
        except DisclosureFetchError as exc:
            manifest[symbol] = {"status": "error", "symbol": symbol, "error": str(exc)}
            n_error += 1
            logger.error("%s: crawl failed: %s", symbol, exc)
        save_manifest(manifest, manifest_path)
    return {"n_ok": n_ok, "n_error": n_error, "n_skipped": n_skipped, "manifest_path": str(manifest_path)}
