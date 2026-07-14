from __future__ import annotations

import pandas as pd

from src.data.universe import tracked_universe_symbols


def _seed_raw(tmp_path, symbols):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    for sym in symbols:
        pd.DataFrame({"date": [pd.Timestamp("2026-01-01")]}).to_parquet(raw_dir / f"{sym}.parquet")
    return raw_dir


def _seed_excluded(tmp_path, symbols):
    path = tmp_path / "excluded_symbols.csv"
    pd.DataFrame({"symbol": symbols, "reason": ["test"] * len(symbols)}).to_csv(path, index=False)
    return path


def test_tracked_universe_symbols_applies_exclusion(tmp_path):
    raw_dir = _seed_raw(tmp_path, ["AAA", "BBB", "GEE"])
    excluded_path = _seed_excluded(tmp_path, ["GEE"])

    result = tracked_universe_symbols(raw_dir=raw_dir, excluded_path=excluded_path)

    assert result == ["AAA", "BBB"]


def test_tracked_universe_symbols_no_exclusion_file_returns_everything(tmp_path):
    raw_dir = _seed_raw(tmp_path, ["AAA", "BBB"])
    result = tracked_universe_symbols(raw_dir=raw_dir, excluded_path=tmp_path / "does_not_exist.csv")
    assert result == ["AAA", "BBB"]


def test_missing_raw_dir_returns_empty(tmp_path):
    result = tracked_universe_symbols(raw_dir=tmp_path / "does_not_exist", excluded_path=tmp_path / "also_missing.csv")
    assert result == []


def test_disclosure_and_price_and_crawl_universe_functions_agree_on_real_data():
    """The actual regression this task fixes: all three pipeline entry
    points (disclosure symbol validation, disclosure crawling, daily price
    update) must return the exact same universe on the real project data
    -- in particular, GEE must be excluded from all three, not just some."""
    from scripts.crawl_disclosure import get_universe_symbols as crawl_get_universe_symbols
    from scripts.update_prices_daily import get_universe_symbols as price_get_universe_symbols
    from src.data.disclosure_ingest import load_universe_symbols

    disclosure_universe = load_universe_symbols()
    crawl_universe = set(crawl_get_universe_symbols())
    price_universe = set(price_get_universe_symbols())

    assert disclosure_universe == crawl_universe == price_universe
    assert "GEE" not in disclosure_universe
    assert "GEE" not in crawl_universe
    assert "GEE" not in price_universe
