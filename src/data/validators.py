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


def _ohlc_relationship_violations(df: pd.DataFrame) -> dict[str, int | None]:
    """Full OHLC relationship, not just high<low (audit PATH_TO_100.md Data
    Quality item): high must be >= both open and close, low must be <=
    both open and close."""
    if not {"open", "high", "low", "close"}.issubset(df.columns):
        return {"high_below_open_or_close": None, "low_above_open_or_close": None}
    o = pd.to_numeric(df["open"], errors="coerce")
    h = pd.to_numeric(df["high"], errors="coerce")
    l = pd.to_numeric(df["low"], errors="coerce")
    c = pd.to_numeric(df["close"], errors="coerce")
    return {
        "high_below_open_or_close": int((h < pd.concat([o, c], axis=1).max(axis=1)).fillna(False).sum()),
        "low_above_open_or_close": int((l > pd.concat([o, c], axis=1).min(axis=1)).fillna(False).sum()),
    }


def _calendar_gap_symbols(df: pd.DataFrame, min_gap_sessions: int = 10) -> dict[str, object]:
    """Symbols with an abnormally large contiguous gap (>= min_gap_sessions
    expected trading sessions, holidays/weekends already excluded) inside
    their own [min_date, max_date] range -- a genuine mid-history data hole,
    not the ordinary start/end-of-listing edge. Uses
    config/vn_market_holidays.csv (the same single source of truth as the
    freshness gate and disclosure backfill rule, audit PATH_TO_100.md
    Universe/Eligibility item)."""
    if not {"symbol", "date"}.issubset(df.columns) or df.empty:
        return {"symbols_with_calendar_gap": 0, "calendar_gap_symbols": []}

    from src.validation.freshness_check import load_market_holidays

    holidays = load_market_holidays()
    flagged: list[str] = []
    for symbol, group in df.groupby("symbol"):
        dates = pd.to_datetime(group["date"], errors="coerce").dropna().sort_values().unique()
        if len(dates) < 2:
            continue
        expected = pd.bdate_range(dates[0], dates[-1])
        expected = [d for d in expected if d.date() not in holidays]
        observed = set(pd.Timestamp(d) for d in dates)
        max_gap = 0
        current_gap = 0
        for day in expected:
            if day in observed:
                current_gap = 0
            else:
                current_gap += 1
                max_gap = max(max_gap, current_gap)
        if max_gap >= min_gap_sessions:
            flagged.append(str(symbol))
    return {
        "symbols_with_calendar_gap": len(flagged),
        "calendar_gap_symbols": sorted(flagged)[:25],
    }


def _return_outliers_beyond_price_band(df: pd.DataFrame) -> dict[str, object]:
    """Count of close-to-close returns exceeding the exchange price band
    (audit PATH_TO_100.md Data Quality item: "return vuot bien do san khong
    kem corp-action flag"). Informational, not a rejection -- these rows
    are exactly what src.features.returns.add_returns's G4 mechanism flags
    as suspect_corporate_action downstream; this check exists so an
    abnormally high *rate* of such rows (more than genuine splits/dividends
    would explain) is visible at the raw-validation stage too, not only
    after feature generation."""
    if not {"symbol", "date", "close"}.issubset(df.columns) or df.empty:
        return {"return_outliers_beyond_price_band": None}

    from src.backtest.simulator import load_price_bands

    bands, default_band = load_price_bands()
    work = df.sort_values(["symbol", "date"]).copy()
    close = pd.to_numeric(work["close"], errors="coerce").where(pd.to_numeric(work["close"], errors="coerce") > 0)
    daily_ret = close.groupby(work["symbol"]).pct_change(1, fill_method=None)
    if "market" in work.columns:
        band_series = work["market"].astype(str).str.upper().map(bands).fillna(default_band)
    else:
        band_series = pd.Series(default_band, index=work.index)
    outliers = (daily_ret.abs() > band_series + 0.02).fillna(False)
    return {"return_outliers_beyond_price_band": int(outliers.sum())}


def _dtype_schema_drift(df: pd.DataFrame) -> dict[str, object]:
    """dtype/schema drift check (audit PATH_TO_100.md Data Quality item):
    numeric columns that contain genuinely non-numeric garbage (not just
    already-missing values), and a date column that doesn't parse."""
    drift: dict[str, int] = {}
    numeric_cols = [c for c in ("open", "high", "low", "close", "volume", "value") if c in df.columns]
    for col in numeric_cols:
        raw_na = df[col].isna()
        coerced_na = pd.to_numeric(df[col], errors="coerce").isna()
        n_bad = int((coerced_na & ~raw_na).sum())
        if n_bad:
            drift[col] = n_bad
    if "date" in df.columns:
        raw_na = df["date"].isna()
        coerced_na = pd.to_datetime(df["date"], errors="coerce").isna()
        n_bad = int((coerced_na & ~raw_na).sum())
        if n_bad:
            drift["date"] = n_bad
    return {"dtype_schema_drift": drift}


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
    checks.update(_ohlc_relationship_violations(df))
    checks.update(_calendar_gap_symbols(df))
    checks.update(_return_outliers_beyond_price_band(df))
    checks.update(_dtype_schema_drift(df))
    return checks
