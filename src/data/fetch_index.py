from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from src.data.loaders import read_parquet, save_parquet

if TYPE_CHECKING:
    from src.data.ssi_client import SSIDataClient


def standardize_index(df: pd.DataFrame, index_id: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out = out.rename(columns={
        "tradingdate": "date",
        "indexvalue": "close",
        "priorindexvalue": "prior_close",
        "ratiochange": "ratio_change",
        "allvalue": "value",
        "allqty": "volume",
        "totalvalue": "value",
        "totalqtty": "volume",
        "indexid": "symbol",
        "indexcode": "symbol",
    })
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce", dayfirst=True).dt.date
    if "symbol" not in out.columns and index_id:
        out["symbol"] = index_id.upper()
    if "symbol" in out.columns:
        out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    for col in ["close", "prior_close", "change", "ratio_change", "volume", "value", "advances", "declines", "nochanges"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if {"symbol", "date"}.issubset(out.columns):
        out = out.dropna(subset=["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")
        out = out.sort_values(["symbol", "date"]).reset_index(drop=True)
    return out


def _safe_save_index(df: pd.DataFrame, path: str | Path) -> pd.DataFrame:
    cleaned = standardize_index(df)
    if cleaned.empty:
        return cleaned
    save_parquet(cleaned, path)
    return cleaned


def fetch_index_history(
    client: "SSIDataClient",
    index_id: str,
    start_date: str,
    end_date: str,
    output_dir: str = "data/raw/index_ohlcv",
    save_output: bool = True,
) -> pd.DataFrame:
    df = client.get_daily_index_chunked(index_id, start_date, end_date)
    path = Path(output_dir) / f"{index_id.upper()}.parquet"
    df = standardize_index(df, index_id=index_id)
    if save_output and not df.empty:
        save_parquet(df, path)
    return df


def update_index_history(
    client: "SSIDataClient",
    index_id: str,
    start_date: str,
    end_date: str,
    output_dir: str = "data/raw/index_ohlcv",
    force_refresh: bool = False,
    refresh_recent_days: int = 5,
) -> pd.DataFrame:
    index_id = str(index_id).upper()
    output_path = Path(output_dir) / f"{index_id}.parquet"

    if force_refresh or not output_path.exists():
        fetched = fetch_index_history(
            client,
            index_id=index_id,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            save_output=False,
        )
        if fetched.empty:
            return fetched
        return _safe_save_index(fetched, output_path)

    old = read_parquet(output_path)
    if old.empty:
        fetched = fetch_index_history(
            client,
            index_id=index_id,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            save_output=False,
        )
        if fetched.empty:
            return fetched
        return _safe_save_index(fetched, output_path)

    old = standardize_index(old, index_id=index_id)
    old["date"] = pd.to_datetime(old["date"])
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    last_date = old["date"].max()
    refresh_anchor = last_date - pd.Timedelta(days=max(refresh_recent_days - 1, 0))
    refresh_start_dt = max(start_dt, refresh_anchor)
    refresh_start = refresh_start_dt.strftime("%Y-%m-%d")

    if refresh_start_dt > end_dt:
        print(f"[SKIP] {index_id}: data already up to date.")
        return old

    new = fetch_index_history(
        client=client,
        index_id=index_id,
        start_date=refresh_start,
        end_date=end_date,
        output_dir=output_dir,
        save_output=False,
    )
    if new.empty:
        return old
    new["date"] = pd.to_datetime(new["date"])

    combined = (
        pd.concat([old[old["date"] < refresh_start_dt], new], ignore_index=True)
        .drop_duplicates(["symbol", "date"])
        .sort_values(["symbol", "date"])
        .reset_index(drop=True)
    )
    save_parquet(combined, output_path)
    return combined
