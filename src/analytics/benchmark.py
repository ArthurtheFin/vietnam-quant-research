from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _normalize_ratio_change(series: pd.Series) -> pd.Series:
    ratio = pd.to_numeric(series, errors="coerce")
    return ratio.where(ratio.abs() <= 0.30, ratio / 100.0)


def _clean_benchmark_returns(
    df: pd.DataFrame,
    return_col: str = "return_1d",
    price_col: str = "close",
    date_col: str = "date",
) -> pd.DataFrame:
    out = df.copy()
    if date_col in out.columns:
        out[date_col] = pd.to_datetime(out[date_col])
        out = out.sort_values(date_col).reset_index(drop=True)

    close_return = pd.Series(np.nan, index=out.index, dtype=float)
    if price_col in out.columns:
        close = pd.to_numeric(out[price_col], errors="coerce")
        close_return = close.pct_change()

    ratio_return = pd.Series(np.nan, index=out.index, dtype=float)
    if "ratio_change" in out.columns:
        ratio_return = _normalize_ratio_change(out["ratio_change"])
    if {"change", "prior_close"}.issubset(out.columns):
        prior_close = pd.to_numeric(out["prior_close"], errors="coerce")
        change = pd.to_numeric(out["change"], errors="coerce")
        ratio_return = ratio_return.fillna(change.div(prior_close.replace(0, np.nan)))

    existing_return = pd.Series(np.nan, index=out.index, dtype=float)
    if return_col in out.columns:
        existing_return = pd.to_numeric(out[return_col], errors="coerce")

    cleaned_return = close_return.copy()
    if ratio_return.notna().any():
        suspicious_close = cleaned_return.isna() | ~np.isfinite(cleaned_return) | (cleaned_return.abs() > 0.30)
        suspicious_gap = cleaned_return.notna() & ratio_return.notna() & ((cleaned_return - ratio_return).abs() > 0.20)
        cleaned_return = cleaned_return.where(~(suspicious_close | suspicious_gap), ratio_return)

    cleaned_return = cleaned_return.fillna(ratio_return)
    cleaned_return = cleaned_return.fillna(existing_return.where(existing_return.abs() <= 0.30))
    out[return_col] = cleaned_return

    if price_col in out.columns:
        raw_close = pd.to_numeric(out[price_col], errors="coerce")
        seed = raw_close.dropna()
        seed_price = float(seed.iloc[0]) if not seed.empty else 1000.0
        if not np.isfinite(seed_price) or seed_price <= 0:
            seed_price = 1000.0
        clean_nav = (1.0 + out[return_col].fillna(0.0)).cumprod()
        out[f"{price_col}_raw"] = raw_close
        out[price_col] = clean_nav * seed_price

    return out


def _ensure_return_col(df: pd.DataFrame, return_col: str = "return_1d", price_col: str = "close", date_col: str = "date") -> pd.DataFrame:
    out = _clean_benchmark_returns(df, return_col=return_col, price_col=price_col, date_col=date_col)
    if return_col not in out.columns and price_col in out.columns:
        out[return_col] = pd.to_numeric(out[price_col], errors="coerce").pct_change()
    return out


def load_processed_benchmark(path: str | Path = "data/processed/benchmark_vnindex.parquet") -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if df.empty:
        return df
    return _clean_benchmark_returns(df)


def build_market_proxy_benchmark(
    price_df: pd.DataFrame,
    date_col: str = "date",
    return_col: str = "return_1d",
    price_col: str = "close",
) -> pd.DataFrame:
    """NV2 fix (docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md): when
    `return_col` isn't already present, this used to compute
    `close.pct_change()` with no guard against non-positive prices. 387 rows
    in clean_daily_ohlcv.parquet have close==0 (166 symbols, all in the
    2020-01/02 data-warmup window) -- the day after one of those, pct_change
    divides by zero and returns +inf. A single +inf symbol-day is enough to
    poison the cross-sectional mean() below for that whole date, which
    previously showed up as `market_proxy_return_1d=inf` on 25 real trading
    days and `mean_return_spread=-inf` in
    10_benchmark_diagnostics.ipynb's summary.

    Fix: same convention already used by `add_returns`
    (src/features/returns.py) for the identical non-positive-price problem --
    NaN out any price <= 0 before pct_change(), so the return (and the day's
    close-to-close transition either side of it) becomes NaN instead of inf,
    and the groupby().mean() below skips it like any other missing value.
    """
    if price_df.empty:
        return pd.DataFrame()
    out = price_df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    if return_col not in out.columns:
        out = out.sort_values(["symbol", date_col]).copy()
        valid_prices = out[price_col].where(out[price_col] > 0.0)
        out[return_col] = valid_prices.groupby(out["symbol"]).pct_change(fill_method=None)
    proxy = (
        out.groupby(date_col)[return_col]
        .mean()
        .rename("market_proxy_return_1d")
        .reset_index()
        .sort_values(date_col)
        .reset_index(drop=True)
    )
    proxy["market_proxy_nav"] = (1 + proxy["market_proxy_return_1d"].fillna(0.0)).cumprod()
    return proxy


def compare_benchmark_to_proxy(
    price_df: pd.DataFrame,
    benchmark_df: pd.DataFrame | None = None,
    benchmark_path: str | Path = "data/processed/benchmark_vnindex.parquet",
    benchmark_symbol: str = "VNINDEX",
    date_col: str = "date",
    return_col: str = "return_1d",
    price_col: str = "close",
    window: int = 20,
) -> tuple[pd.DataFrame, str]:
    proxy = build_market_proxy_benchmark(price_df, date_col=date_col, return_col=return_col, price_col=price_col)
    if proxy.empty:
        return pd.DataFrame(), "unavailable"

    if benchmark_df is None:
        benchmark = load_processed_benchmark(benchmark_path)
        source = Path(benchmark_path).name if not benchmark.empty else "market_proxy_only"
    else:
        benchmark = _ensure_return_col(benchmark_df.copy(), return_col=return_col, price_col=price_col, date_col=date_col)
        source = "benchmark_df" if not benchmark.empty else "market_proxy_only"

    if benchmark.empty:
        comparison = proxy.copy()
        comparison["benchmark_return_1d"] = np.nan
        comparison["benchmark_nav"] = np.nan
        comparison["return_spread"] = np.nan
        comparison["tracking_error_20d"] = np.nan
        comparison["rolling_correlation_20d"] = np.nan
        comparison["benchmark_source"] = source
        return comparison, source

    if "symbol" in benchmark.columns:
        bench_symbol_mask = benchmark["symbol"].astype(str).str.upper() == str(benchmark_symbol).upper()
        if bench_symbol_mask.any():
            benchmark = benchmark[bench_symbol_mask].copy()
    benchmark = benchmark[[date_col, return_col]].rename(columns={return_col: "benchmark_return_1d"})
    benchmark["benchmark_nav"] = (1 + benchmark["benchmark_return_1d"].fillna(0.0)).cumprod()

    comparison = proxy.merge(benchmark, on=date_col, how="left")
    comparison["return_spread"] = comparison["benchmark_return_1d"] - comparison["market_proxy_return_1d"]
    comparison["tracking_error_20d"] = comparison["return_spread"].rolling(window).std() * np.sqrt(252)
    comparison["rolling_correlation_20d"] = comparison["benchmark_return_1d"].rolling(window).corr(comparison["market_proxy_return_1d"])
    comparison["benchmark_source"] = source
    return comparison, source


def summarize_benchmark_alignment(comparison_df: pd.DataFrame) -> dict[str, float | str | None]:
    if comparison_df.empty:
        return {
            "rows": 0,
            "benchmark_source": "unavailable",
            "coverage_ratio": 0.0,
            "mean_return_spread": np.nan,
            "tracking_error_20d": np.nan,
            "rolling_correlation_20d": np.nan,
        }

    coverage = float(comparison_df["benchmark_return_1d"].notna().mean()) if "benchmark_return_1d" in comparison_df.columns else 0.0
    return {
        "rows": int(len(comparison_df)),
        "date_min": str(comparison_df["date"].min().date()) if "date" in comparison_df.columns else None,
        "date_max": str(comparison_df["date"].max().date()) if "date" in comparison_df.columns else None,
        "benchmark_source": str(comparison_df["benchmark_source"].dropna().iloc[0]) if "benchmark_source" in comparison_df.columns and comparison_df["benchmark_source"].notna().any() else "unavailable",
        "coverage_ratio": coverage,
        "mean_return_spread": float(comparison_df["return_spread"].dropna().mean()) if "return_spread" in comparison_df.columns and comparison_df["return_spread"].notna().any() else np.nan,
        "tracking_error_20d": float(comparison_df["tracking_error_20d"].dropna().iloc[-1]) if "tracking_error_20d" in comparison_df.columns and comparison_df["tracking_error_20d"].notna().any() else np.nan,
        "rolling_correlation_20d": float(comparison_df["rolling_correlation_20d"].dropna().iloc[-1]) if "rolling_correlation_20d" in comparison_df.columns and comparison_df["rolling_correlation_20d"].notna().any() else np.nan,
    }
