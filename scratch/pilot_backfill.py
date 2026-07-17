"""Pilot backfill (Task 3 of docs/reports/data/BACKFILL_DESIGN_REPORT.md): fetch full
2020-01-01 -> present history for 20 symbols via the existing SSI FCData
client, writing to data/pilot_backfill/raw/ (NEVER touches
data/processed/ or data/signals/ -- existing data is not overwritten).

20 symbols = 5 reference (HPG, SSI, STB, TCB, VPB -- confirmed missing
2021 data in docs/reports/data/DATA_AUDIT_REPORT.md) + 15 random, spread evenly across
liquidity tiers of the CURRENT universe (fixed seed=42, see chat for the
selection script).
"""
from __future__ import annotations

import time

import pandas as pd

from src.data.ssi_client import SSIDataClient
from src.data.loaders import save_parquet

REFERENCE_SYMBOLS = ["HPG", "SSI", "STB", "TCB", "VPB"]
RANDOM_SYMBOLS = ["SVD", "HAS", "PTL", "AG1", "YBM", "VNE", "APG", "LIX", "SRC", "SJD",
                  "LCG", "TVC", "ITD", "HHP", "DGW"]
ALL_SYMBOLS = REFERENCE_SYMBOLS + RANDOM_SYMBOLS

START_DATE = "2020-01-01"
END_DATE = "2026-07-06"

client = SSIDataClient()
t0 = time.time()
results = {}
for sym in ALL_SYMBOLS:
    try:
        df = client.get_daily_ohlc(sym, START_DATE, END_DATE, page_size=1000, max_pages=10)
        if df.empty:
            print(f"{sym}: EMPTY response")
            results[sym] = 0
            continue
        df["date"] = pd.to_datetime(df["tradingdate"], format="%d/%m/%Y")
        df = df.sort_values("date").reset_index(drop=True)
        save_parquet(df, f"data/pilot_backfill/raw/{sym}.parquet")
        results[sym] = len(df)
        print(f"[{time.time()-t0:.0f}s] {sym}: {len(df)} rows, "
              f"{df['date'].min().date()} -> {df['date'].max().date()}")
    except Exception as exc:
        print(f"{sym}: ERROR {exc}")
        results[sym] = -1

print(f"\nDone in {time.time()-t0:.0f}s. Summary: {results}")
