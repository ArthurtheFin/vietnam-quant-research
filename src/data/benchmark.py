from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.data.loaders import read_symbol_files, save_parquet
from src.features.returns import add_returns


def _normalize_ratio_change(series: pd.Series, close_return: pd.Series | None = None) -> pd.Series:
    ratio = pd.to_numeric(series, errors="coerce")
    if close_return is not None:
        is_pct = (ratio.abs() > 0.15) | (
            close_return.notna() & (close_return != 0) & ((ratio / close_return).abs() > 5.0)
        )
    else:
        is_pct = ratio.abs() > 0.15
    return ratio.where(~is_pct, ratio / 100.0)


def _clean_index_return_series(group: pd.DataFrame) -> pd.Series:
    close = pd.to_numeric(group.get("close"), errors="coerce")
    close_return = close.pct_change()

    ratio_return = pd.Series(np.nan, index=group.index, dtype=float)
    if "ratio_change" in group.columns:
        ratio_return = _normalize_ratio_change(group["ratio_change"], close_return)
    if {"change", "prior_close"}.issubset(group.columns):
        prior_close = pd.to_numeric(group["prior_close"], errors="coerce")
        change = pd.to_numeric(group["change"], errors="coerce")
        ratio_return = ratio_return.fillna(change.div(prior_close.replace(0, np.nan)))

    cleaned_return = close_return.copy()
    if ratio_return.notna().any():
        suspicious_close = cleaned_return.isna() | ~np.isfinite(cleaned_return) | (cleaned_return.abs() > 0.30)
        suspicious_gap = cleaned_return.notna() & ratio_return.notna() & ((cleaned_return - ratio_return).abs() > 0.20)
        cleaned_return = cleaned_return.where(~(suspicious_close | suspicious_gap), ratio_return)

    return cleaned_return.fillna(ratio_return)


def standardize_index_history(df: pd.DataFrame, index_id: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out = out.rename(
        columns={
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
        }
    )
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce", dayfirst=True)
    if "symbol" not in out.columns and index_id:
        out["symbol"] = str(index_id).upper()
    if "symbol" in out.columns:
        out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    for col in ["close", "prior_close", "change", "ratio_change", "volume", "value", "advances", "declines", "nochanges"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def load_index_files(folder: str | Path = "data/raw/index_ohlcv") -> pd.DataFrame:
    frames = []
    for path in sorted(Path(folder).glob("*.parquet")):
        df = pd.read_parquet(path)
        if df.empty:
            continue
        frames.append(standardize_index_history(df))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def prepare_index_features(index_df: pd.DataFrame, horizons: list[int] | None = None) -> pd.DataFrame:
    if index_df.empty:
        return pd.DataFrame()
    horizons = horizons or [1, 5, 10, 20]

    out = standardize_index_history(index_df)
    out["date"] = pd.to_datetime(out["date"])
    out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    out = out.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Clean scaled index values (> 5000)
    for col in ["close", "prior_close"]:
        if col in out.columns:
            val = pd.to_numeric(out[col], errors="coerce")
            out[col] = np.where(val > 5000.0, val / 100.0, val)

    cleaned_returns = []
    for _, group in out.groupby("symbol", sort=False):
        cleaned_returns.append(_clean_index_return_series(group))
    out["return_1d"] = pd.concat(cleaned_returns).sort_index()

    synthetic_price = []
    for _, group in out.groupby("symbol", sort=False):
        raw_close = pd.to_numeric(group["close"], errors="coerce")
        seed = raw_close.dropna()
        seed_price = float(seed.iloc[0]) if not seed.empty else 1000.0
        if not np.isfinite(seed_price) or seed_price <= 0:
            seed_price = 1000.0
        clean_price = (1.0 + group["return_1d"].fillna(0.0)).cumprod() * seed_price
        synthetic_price.append(clean_price)
    out["close_raw"] = out["close"]
    out["close"] = pd.concat(synthetic_price).sort_index()

    out = add_returns(out, horizons=horizons, price_col="close")
    return out


def build_benchmark_file(
    index_id: str = "VNINDEX",
    raw_dir: str | Path = "data/raw/index_ohlcv",
    output_path: str | Path = "data/processed/benchmark_vnindex.parquet",
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    raw_df = load_index_files(raw_dir)
    if raw_df.empty:
        return pd.DataFrame()

    index_id = str(index_id).upper()
    features = prepare_index_features(raw_df, horizons=horizons)
    benchmark = features[features["symbol"] == index_id].copy()
    if benchmark.empty:
        return pd.DataFrame()

    save_parquet(benchmark, output_path)
    return benchmark
