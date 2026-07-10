"""Task 4 supplementary fetch: close the recent-tail coverage gap found by
scratch/full_backfill_v2_verify.py for 48 symbols where v2's bulk
`get_daily_ohlc` fetch was missing some sessions that `existing`
(data/processed/stock_features.parquet) already has -- almost all
clustered in the most recent ~1-3 months for illiquid names (a
`get_daily_ohlc` backend-completeness quirk on very recent low-volume
data, not a pagination/code defect).

For each affected symbol, re-fetches a small window (from just before its
earliest missing date through today) via the same single-call
`get_daily_ohlc` method, merges the result into
data/full_history_v2/raw/{symbol}.parquet (de-duplicated by date, existing
rows outside the re-fetched window untouched), and updates
data/full_history_v2/manifest.json with a `supplemented_at` note.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.data.loaders import save_parquet
from src.data.ssi_client import SSIDataClient

MANIFEST_PATH = Path("data/full_history_v2/manifest.json")
RAW_DIR = Path("data/full_history_v2/raw")
TODAY = "2026-07-10"


def find_gap_symbols() -> pd.DataFrame:
    report = pd.read_csv("data/full_history_v2/quality_report.csv")
    fail_syms = report[~report["check_a_pass"]]["symbol"].tolist()

    existing = pd.read_parquet("data/processed/stock_features.parquet")
    existing["date"] = pd.to_datetime(existing["date"])
    existing_by_sym = {s: set(g["date"]) for s, g in existing.groupby("symbol")}

    rows = []
    for sym in fail_syms:
        v2 = pd.read_parquet(RAW_DIR / f"{sym}.parquet")
        v2["date"] = pd.to_datetime(v2["date"])
        v2_dates = set(v2["date"])
        ex_dates = existing_by_sym.get(sym, set())
        if not ex_dates:
            continue
        omin, omax = max(v2["date"].min(), min(ex_dates)), min(v2["date"].max(), max(ex_dates))
        missing = {d for d in ex_dates if omin <= d <= omax} - v2_dates
        if missing:
            rows.append({"symbol": sym, "n_missing": len(missing), "earliest_missing": min(missing)})
    return pd.DataFrame(rows)


def main() -> None:
    gap_df = find_gap_symbols()
    print(f"{len(gap_df)} symbols need a supplementary re-fetch")

    manifest = json.loads(MANIFEST_PATH.read_text())
    client = SSIDataClient()

    for _, row in gap_df.iterrows():
        sym = row["symbol"]
        start = (row["earliest_missing"] - timedelta(days=10)).strftime("%Y-%m-%d")
        try:
            new_df = client.get_daily_ohlc(sym, start, TODAY, page_size=1000, max_pages=3)
            if new_df.empty:
                print(f"{sym}: supplementary fetch EMPTY ({start} -> {TODAY})")
                continue
            new_df["date"] = pd.to_datetime(new_df["tradingdate"], format="%d/%m/%Y")

            old_df = pd.read_parquet(RAW_DIR / f"{sym}.parquet")
            old_df["date"] = pd.to_datetime(old_df["date"])

            merged = pd.concat([old_df[old_df["date"] < new_df["date"].min()], new_df], ignore_index=True)
            merged = merged.sort_values("date").drop_duplicates(subset="date", keep="last").reset_index(drop=True)
            save_parquet(merged, str(RAW_DIR / f"{sym}.parquet"))

            manifest[sym]["row_count"] = len(merged)
            manifest[sym]["date_max"] = str(merged["date"].max().date())
            manifest[sym]["supplemented_at"] = datetime.now(timezone.utc).isoformat()
            manifest[sym]["supplement_window"] = f"{start}..{TODAY}"
            print(f"{sym}: supplementary fetch {start} -> {TODAY}, {len(new_df)} rows fetched, "
                  f"{row['n_missing']} gap-days targeted, new total {len(merged)} rows")
        except Exception as exc:
            print(f"{sym}: ERROR {exc}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print("\nDone. Manifest updated.")


if __name__ == "__main__":
    main()
