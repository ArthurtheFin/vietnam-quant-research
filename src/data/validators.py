from __future__ import annotations

import re

import pandas as pd


PRIMARY_EQUITY_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,3}$")


def standardize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize common FCData OHLCV columns to a clean schema."""
    if df.empty:
        return df
    out = df.copy()
    # common aliases after lowercasing
    aliases = {
        "tradingdate": "date",
        "trading_date": "date",
        "time": "time",
        "symbol": "symbol",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "totalvol": "volume",
        "value": "value",
        "totalval": "value",
        "closeprice": "close",
        "openprice": "open",
        "highprice": "high",
        "lowprice": "low",
        "stockcode": "symbol",
        "stocksymbol": "symbol",
    }
    out = out.rename(columns={c: aliases.get(c, c) for c in out.columns})
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce", dayfirst=True)
    for col in ["open", "high", "low", "close", "volume", "value"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "symbol" in out.columns:
        out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    return out


def is_primary_equity_symbol(symbol: object, max_len: int = 3) -> bool:
    if pd.isna(symbol):
        return False
    value = str(symbol).strip().upper()
    if not value or len(value) > int(max_len):
        return False
    return bool(PRIMARY_EQUITY_SYMBOL_RE.fullmatch(value))


def primary_equity_symbol_mask(
    df: pd.DataFrame,
    symbol_col: str = "symbol",
    max_len: int = 3,
) -> pd.Series:
    if symbol_col not in df.columns:
        return pd.Series(False, index=df.index, dtype=bool)
    return df[symbol_col].map(lambda value: is_primary_equity_symbol(value, max_len=max_len)).astype(bool)


def filter_primary_equity_symbols(
    df: pd.DataFrame,
    symbol_col: str = "symbol",
    max_len: int = 3,
) -> pd.DataFrame:
    if df.empty or symbol_col not in df.columns:
        return df.copy()
    mask = primary_equity_symbol_mask(df, symbol_col=symbol_col, max_len=max_len)
    return df.loc[mask].copy()


def validate_ohlcv(df: pd.DataFrame, require_value: bool = False) -> dict:
    required = ["symbol", "date", "open", "high", "low", "close", "volume"]
    if require_value:
        required.append("value")
    missing_cols = [c for c in required if c not in df.columns]
    primary_mask = primary_equity_symbol_mask(df) if "symbol" in df.columns else pd.Series(False, index=df.index, dtype=bool)
    checks = {
        "rows": len(df),
        "missing_columns": missing_cols,
        "duplicate_symbol_date": int(df.duplicated(["symbol", "date"]).sum()) if set(["symbol", "date"]).issubset(df.columns) else None,
        "missing_close": int(df["close"].isna().sum()) if "close" in df.columns else None,
        "non_positive_close": int((pd.to_numeric(df["close"], errors="coerce") <= 0).fillna(False).sum()) if "close" in df.columns else None,
        "negative_volume": int((df["volume"] < 0).sum()) if "volume" in df.columns else None,
        "invalid_high_low": int((pd.to_numeric(df["high"], errors="coerce") < pd.to_numeric(df["low"], errors="coerce")).fillna(False).sum()) if {"high", "low"}.issubset(df.columns) else None,
        "missing_market": int(df["market"].isna().sum()) if "market" in df.columns else None,
        "non_primary_symbol_rows": int((~primary_mask).sum()) if "symbol" in df.columns else None,
        "non_primary_symbols": sorted(df.loc[~primary_mask, "symbol"].dropna().astype(str).str.upper().unique().tolist())[:25] if "symbol" in df.columns else [],
    }
    return checks
