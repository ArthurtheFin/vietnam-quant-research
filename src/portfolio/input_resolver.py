from __future__ import annotations

from pathlib import Path

import numpy as np
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

    # Apply eligibility filtering in portfolio input resolver
    cf_path = base / "data/output/cashflow_board.parquet"
    wcc_path = base / "data/output/watchlist_cashflow_confirmation.parquet"
    
    cf_df = read_parquet(cf_path) if cf_path.exists() else pd.DataFrame()
    wcc_df = read_parquet(wcc_path) if wcc_path.exists() else pd.DataFrame()
    
    clean_candidates = []
    rejected_reasons = {}
    
    for idx, row in candidates.iterrows():
        sym = row["symbol"]
        
        vol = row.get("volume")
        if pd.isna(vol) or vol is None or (isinstance(vol, float) and np.isnan(vol)):
            if "volume" not in features.columns and "volume" not in latest.columns:
                vol = 100000.0
            else:
                vol = np.nan
        cf_status = "OK"
        cf_state = "NEUTRAL"
        
        if not cf_df.empty and sym in cf_df["symbol"].values:
            cf_row = cf_df[cf_df["symbol"] == sym].iloc[0]
            if pd.isna(vol) or vol is None or np.isnan(vol):
                vol = cf_row.get("volume")
            cf_status = cf_row.get("cashflow_data_status", "OK")
            cf_state = cf_row.get("cashflow_state", "NEUTRAL")
            
        confirm_status = "WATCH"
        if not wcc_df.empty and sym in wcc_df["symbol"].values:
            wcc_row = wcc_df[wcc_df["symbol"] == sym].iloc[0]
            confirm_status = wcc_row.get("confirmation_status", "WATCH")
            
        reasons = []
        if pd.isna(vol) or vol <= 0:
            reasons.append("ZERO_VOLUME_OR_MISSING_DATA")
        if pd.isna(row["close"]) or row["close"] <= 0:
            reasons.append("INVALID_CLOSE")
        if cf_status in ("ZERO_VOLUME", "MISSING_DATA", "CHECK_REQUIRED"):
            reasons.append("CASHFLOW_CHECK_REQUIRED")
        if confirm_status in ("CHECK_REQUIRED", "REJECT"):
            reasons.append("CASHFLOW_CHECK_REQUIRED")
            
        watchlist_df = source.data
        if not watchlist_df.empty and "symbol" in watchlist_df.columns and sym in watchlist_df["symbol"].values:
            w_row = watchlist_df[watchlist_df["symbol"] == sym].iloc[0]
            if w_row.get("eligibility_status") == "REJECTED":
                reasons.append("MARKED_REJECTED_IN_WATCHLIST")
                
        if reasons:
            rejected_reasons[sym] = "; ".join(sorted(set(reasons)))
        else:
            clean_candidates.append(row)
            
    if clean_candidates:
        candidates = pd.DataFrame(clean_candidates)
    else:
        candidates = pd.DataFrame(columns=candidates.columns)

    metadata = {
        **source.metadata(),
        "features_path": relative_path(base / features_path, base),
        "features_latest_date": None if latest_timestamp(features) is None else latest_timestamp(features).date().isoformat(),
        "used_symbols": sorted(candidates["symbol"].tolist()) if not candidates.empty else [],
        "missing_symbols": missing_symbols,
        "rejected_symbols_portfolio_gate": rejected_reasons,
        "generated_at": utc_now_iso(),
    }
    return candidates.reset_index(drop=True), metadata
