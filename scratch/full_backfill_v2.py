"""Task 4 (docs/reports/data/docs/reports/data/BACKFILL_DESIGN_REPORT.md, Round 2's finalized design): full
2020-01-01 -> present backfill for the entire ~501-symbol current universe.

Uses a single direct `get_daily_ohlc` call per symbol (page_size=1000,
auto-paginated) -- the SAME method as the original Round-1 pilot
(scratch/pilot_backfill.py) and the design's explicit principle ("no
splicing... get_daily_ohlc only"). This deliberately does NOT go through
the chunked `fetch_symbol_history`/fallback path Task 3 exercised --
get_daily_ohlc is the primary, already-adjusted endpoint and doesn't need
chunking or fallback for this range (confirmed in Round 1/3).

Checkpointed and resumable: writes data/full_history_v2/raw/{symbol}.parquet
as each symbol completes, and updates data/full_history_v2/manifest.json
after every symbol. Re-running this script skips any symbol already
recorded with status "ok" in the manifest.

Writes only to data/full_history_v2/ -- does not touch data/processed/,
data/pilot_backfill/, or data/pilot_backfill_v2/.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.data.loaders import save_parquet
from src.data.ssi_client import SSIDataClient

START_DATE = "2020-01-01"
END_DATE = "2026-07-06"
OUTPUT_DIR = Path("data/full_history_v2/raw")
MANIFEST_PATH = Path("data/full_history_v2/manifest.json")


def build_universe() -> pd.DataFrame:
    """501 current symbols, market, and a descending-liquidity sort key,
    all derived from existing data/processed + data/raw/securities --
    no new data source, per Round 1 Task 2 finding."""
    df = pd.read_parquet("data/processed/stock_features.parquet")

    market_by_symbol = (
        df.dropna(subset=["market"]).sort_values("date").groupby("symbol")["market"].last()
    )
    liq_by_symbol = (
        df.dropna(subset=["value_ma20"]).sort_values("date").groupby("symbol")["value_ma20"].last()
    )

    universe = pd.DataFrame({"symbol": df["symbol"].unique()}).set_index("symbol")
    universe["market"] = market_by_symbol
    universe["value_ma20"] = liq_by_symbol

    missing_market = universe[universe["market"].isna()].index.tolist()
    if missing_market:
        for exch in ("HOSE", "HNX", "UPCOM"):
            sec = pd.read_parquet(f"data/raw/securities/{exch}.parquet")
            hits = sec[sec["symbol"].isin(missing_market)][["symbol", "market"]].drop_duplicates("symbol")
            universe.loc[hits["symbol"], "market"] = hits.set_index("symbol")["market"]

    still_missing = universe[universe["market"].isna()].index.tolist()
    if still_missing:
        raise RuntimeError(f"Could not resolve market for: {still_missing}")

    universe["value_ma20"] = universe["value_ma20"].fillna(0.0)
    universe = universe.sort_values("value_ma20", ascending=False).reset_index()
    return universe[["symbol", "market", "value_ma20"]]


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def main() -> None:
    universe = build_universe()
    print(f"Universe: {len(universe)} symbols, sorted by descending value_ma20 liquidity")
    print(f"Markets: {universe['market'].value_counts().to_dict()}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    client = SSIDataClient()

    t0 = time.time()
    n_ok, n_error, n_skipped = 0, 0, 0
    for i, row in universe.iterrows():
        sym, market = row["symbol"], row["market"]
        if manifest.get(sym, {}).get("status") == "ok":
            n_skipped += 1
            continue
        try:
            df = client.get_daily_ohlc(sym, START_DATE, END_DATE, page_size=1000, max_pages=10)
            if df.empty:
                manifest[sym] = {"status": "empty", "row_count": 0,
                                  "fetched_at": datetime.now(timezone.utc).isoformat()}
                print(f"[{time.time()-t0:.0f}s] ({i+1}/{len(universe)}) {sym}: EMPTY response")
                n_error += 1
                save_manifest(manifest)
                continue
            df["date"] = pd.to_datetime(df["tradingdate"], format="%d/%m/%Y")
            df = df.sort_values("date").reset_index(drop=True)
            save_parquet(df, str(OUTPUT_DIR / f"{sym}.parquet"))
            manifest[sym] = {
                "status": "ok",
                "market": market,
                "row_count": len(df),
                "date_min": str(df["date"].min().date()),
                "date_max": str(df["date"].max().date()),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            n_ok += 1
            print(f"[{time.time()-t0:.0f}s] ({i+1}/{len(universe)}) {sym}: {len(df)} rows, "
                  f"{df['date'].min().date()} -> {df['date'].max().date()}")
        except Exception as exc:
            manifest[sym] = {"status": "error", "error": str(exc),
                              "fetched_at": datetime.now(timezone.utc).isoformat()}
            n_error += 1
            print(f"[{time.time()-t0:.0f}s] ({i+1}/{len(universe)}) {sym}: ERROR {exc}")
        save_manifest(manifest)

    print(f"\nDone in {time.time()-t0:.0f}s. ok={n_ok} error/empty={n_error} skipped(resumed)={n_skipped}")


if __name__ == "__main__":
    main()
