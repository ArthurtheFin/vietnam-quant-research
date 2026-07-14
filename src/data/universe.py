"""Single source of truth for "the tracked universe, minus exclusions" --
audit/PATH_TO_100.md Data Quality item: the price pipeline
(scripts/update_prices_daily.py) and disclosure pipeline
(src/data/disclosure_ingest.py, scripts/crawl_disclosure.py) each had their
own universe-symbol function, and only one of them applied
config/excluded_symbols.csv (GEE was excluded from disclosure crawling but
NOT from disclosure symbol validation -- a real inconsistency: a GEE
disclosure record would validate as "known" even though GEE is excluded
from the eligible universe everywhere else).

Every pipeline that needs "the current tracked universe" should import
`tracked_universe_symbols` from here instead of defining its own.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.dataset_config import OFFICIAL_PRICE_RAW_DIR

UNIVERSE_RAW_DIR = Path(OFFICIAL_PRICE_RAW_DIR)
EXCLUDED_SYMBOLS_PATH = Path("config/excluded_symbols.csv")


def tracked_universe_symbols(
    raw_dir: str | Path = UNIVERSE_RAW_DIR,
    excluded_path: str | Path = EXCLUDED_SYMBOLS_PATH,
) -> list[str]:
    """Every symbol with a data/full_history_v2/raw/{symbol}.parquet file,
    minus config/excluded_symbols.csv. Returns a sorted list; callers that
    want a set can just wrap this."""
    raw_dir = Path(raw_dir)
    symbols = {p.stem.upper() for p in raw_dir.glob("*.parquet")} if raw_dir.exists() else set()
    excluded_path = Path(excluded_path)
    if excluded_path.exists():
        excluded = set(pd.read_csv(excluded_path)["symbol"].astype(str).str.upper())
        symbols -= excluded
    return sorted(symbols)
