"""Task 3 re-pilot (Round 3, docs/reports/data/BACKFILL_DESIGN_REPORT.md): re-fetch the same
20 pilot symbols (seed=42, unchanged) through the REAL production fetch
path -- fetch_symbol_history (chunked, with the now-fixed fallback) -- not
the ad hoc direct get_daily_ohlc call the original pilot script used (which
never exercised the buggy fallback path at all, since it fetched the whole
range in one shot). Writes to data/pilot_backfill_v2/raw/, a NEW directory;
does not touch data/pilot_backfill/ (original pilot, kept as before/after
evidence) or any existing processed data.
"""
from __future__ import annotations

import time

from src.data.fetch_daily import fetch_symbol_history
from src.data.ssi_client import SSIDataClient

MARKET_BY_SYMBOL = {
    "HPG": "HOSE", "SSI": "HOSE", "STB": "HOSE", "TCB": "HOSE", "VPB": "HOSE",
    "SVD": "HOSE", "HAS": "HOSE", "PTL": "HOSE", "AG1": "UPCOM", "YBM": "HOSE",
    "VNE": "HOSE", "APG": "HOSE", "LIX": "HOSE", "SRC": "HOSE", "SJD": "HOSE",
    "LCG": "HOSE", "TVC": "HNX", "ITD": "HOSE", "HHP": "HOSE", "DGW": "HOSE",
}

client = SSIDataClient()
t0 = time.time()
for sym, market in MARKET_BY_SYMBOL.items():
    df = fetch_symbol_history(
        client=client,
        symbol=sym,
        start_date="2020-01-01",
        end_date="2026-07-06",
        output_dir="data/pilot_backfill_v2/raw",
        chunk_days=29,
        request_sleep=1.2,
        market=market,
    )
    n_flagged = int((df["quality_flag"] == "chunk_boundary_jump").sum()) if "quality_flag" in df.columns else 0
    print(f"[{time.time()-t0:.0f}s] {sym}: {len(df)} rows, quality_flag hits={n_flagged}")

print(f"\nDone in {time.time()-t0:.0f}s")
