from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.loaders import read_parquet
from src.utils.pipeline_io import latest_timestamp, relative_path, resolve_watchlist_source, utc_now_iso


def load_default_portfolio_candidates(
    base_dir: str | Path = ".",
    features_path: str = "data/processed/stock_features.parquet",
) -> tuple[pd.DataFrame, dict[str, object]]:
    base = Path(base_dir)
    source = resolve_watchlist_source(base)
    features = read_parquet(base / features_path)

    if source.is_empty:
        metadata = {
            **source.metadata(),
            "missing_symbols": [],
            "features_path": relative_path(base / features_path, base),
            "features_latest_date": None,
        }
        return pd.DataFrame(), metadata

    if features.empty or "symbol" not in features.columns:
        metadata = {
            **source.metadata(),
            "missing_symbols": source.symbols,
            "features_path": relative_path(base / features_path, base),
            "features_latest_date": None,
            "generated_at": utc_now_iso(),
        }
        return pd.DataFrame(), metadata

    work = features.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    latest = work.sort_values(["symbol", "date"]).groupby("symbol", as_index=False).tail(1).reset_index(drop=True)
    latest["symbol"] = latest["symbol"].astype(str).str.upper()

    source_symbols = [str(symbol).strip().upper() for symbol in source.symbols]
    candidates = latest[latest["symbol"].isin(source_symbols)].copy()
    available_symbols = set(candidates["symbol"].tolist())
    missing_symbols = sorted(set(source_symbols) - available_symbols)

    metadata = {
        **source.metadata(),
        "features_path": relative_path(base / features_path, base),
        "features_latest_date": None if latest_timestamp(features) is None else latest_timestamp(features).date().isoformat(),
        "used_symbols": sorted(available_symbols),
        "missing_symbols": missing_symbols,
        "generated_at": utc_now_iso(),
    }
    return candidates.reset_index(drop=True), metadata
