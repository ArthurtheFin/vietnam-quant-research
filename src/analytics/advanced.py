from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.correlation import build_return_matrix, compute_correlation_matrix, top_correlation_pairs
from src.utils.math_utils import safe_log_ratio


def _ensure_returns(
    df: pd.DataFrame,
    return_col: str = "return_1d",
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
) -> pd.DataFrame:
    out = df.sort_values([symbol_col, date_col]).copy()
    if return_col not in out.columns:
        out[return_col] = out.groupby(symbol_col)[price_col].pct_change()
    return out


def compute_rolling_beta(
    asset_df: pd.DataFrame,
    benchmark_df: pd.DataFrame | None = None,
    benchmark_symbol: str = "VNINDEX",
    window: int = 60,
    return_col: str = "return_1d",
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
) -> pd.DataFrame:
    assets = _ensure_returns(asset_df, return_col=return_col, price_col=price_col, symbol_col=symbol_col, date_col=date_col)
    assets[date_col] = pd.to_datetime(assets[date_col])

    if benchmark_df is None:
        if benchmark_symbol not in set(assets[symbol_col].astype(str).str.upper()):
            raise KeyError(f"Benchmark symbol '{benchmark_symbol}' not found in asset_df")
        benchmark = assets[assets[symbol_col].astype(str).str.upper() == benchmark_symbol.upper()][[date_col, return_col]].copy()
        universe = assets[assets[symbol_col].astype(str).str.upper() != benchmark_symbol.upper()].copy()
    else:
        benchmark = benchmark_df.copy()
        benchmark[date_col] = pd.to_datetime(benchmark[date_col])
        if return_col not in benchmark.columns:
            benchmark = benchmark.sort_values(date_col).copy()
            benchmark[return_col] = benchmark[price_col].pct_change()
        benchmark = benchmark[[date_col, return_col]].rename(columns={return_col: "benchmark_return"})
        universe = assets.copy()

    if benchmark_df is None:
        benchmark = benchmark.rename(columns={return_col: "benchmark_return"})

    merged = universe.merge(benchmark, on=date_col, how="left")
    merged = merged.sort_values([symbol_col, date_col]).copy()

    beta_col = f"rolling_beta_{window}d"
    beta_parts = []
    for _, group in merged.groupby(symbol_col):
        beta = group[return_col].rolling(window).cov(group["benchmark_return"]) / group["benchmark_return"].rolling(window).var()
        beta_parts.append(beta)
    beta_series = pd.concat(beta_parts).sort_index() if beta_parts else pd.Series(dtype=float)
    merged[beta_col] = beta_series
    merged["benchmark_symbol"] = benchmark_symbol
    return merged


def add_cross_sectional_momentum_rank(
    df: pd.DataFrame,
    lookback: int = 20,
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
) -> pd.DataFrame:
    out = df.sort_values([symbol_col, date_col]).copy()
    momentum_col = f"momentum_{lookback}d"
    rank_col = f"momentum_rank_{lookback}d"
    pct_rank_col = f"momentum_pct_rank_{lookback}d"
    decile_col = f"momentum_decile_{lookback}d"

    out[momentum_col] = out.groupby(symbol_col)[price_col].pct_change(lookback)
    out[pct_rank_col] = out.groupby(date_col)[momentum_col].rank(pct=True, ascending=True)
    out[rank_col] = out.groupby(date_col)[momentum_col].rank(method="min", ascending=False)
    out[decile_col] = (out[pct_rank_col] * 10).apply(np.ceil).clip(lower=1, upper=10)
    return out


def pair_divergence_zscore(
    df: pd.DataFrame,
    symbol_a: str,
    symbol_b: str,
    window: int = 60,
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
    method: str = "log_ratio",
) -> pd.DataFrame:
    price_matrix = (
        df.pivot_table(index=date_col, columns=symbol_col, values=price_col, aggfunc="last")
        .sort_index()
    )
    required = [symbol_a, symbol_b]
    if not set(required).issubset(price_matrix.columns):
        missing = [symbol for symbol in required if symbol not in price_matrix.columns]
        raise KeyError(f"Missing symbol(s) in price matrix: {missing}")

    pair = price_matrix[required].dropna().copy()
    if method == "log_ratio":
        spread = safe_log_ratio(pair[symbol_a], pair[symbol_b])
    elif method == "ratio":
        spread = pair[symbol_a] / pair[symbol_b]
    elif method == "spread":
        spread = pair[symbol_a] - pair[symbol_b]
    else:
        raise ValueError("method must be one of: log_ratio, ratio, spread")

    rolling_mean = spread.rolling(window).mean()
    rolling_std = spread.rolling(window).std()
    zscore = (spread - rolling_mean) / rolling_std

    return pd.DataFrame(
        {
            "date": pair.index,
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "price_a": pair[symbol_a].values,
            "price_b": pair[symbol_b].values,
            "spread": spread.values,
            "rolling_mean": rolling_mean.values,
            "rolling_std": rolling_std.values,
            "divergence_zscore": zscore.values,
        }
    )


def screen_pair_divergences(
    df: pd.DataFrame,
    corr_matrix: pd.DataFrame | None = None,
    top_n_pairs: int = 10,
    min_abs_correlation: float = 0.6,
    zscore_window: int = 60,
    min_periods: int = 2,
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
) -> pd.DataFrame:
    if corr_matrix is None:
        returns = build_return_matrix(df, price_col=price_col, symbol_col=symbol_col, date_col=date_col)
        corr_matrix = compute_correlation_matrix(returns, min_periods=min_periods)

    pairs = top_correlation_pairs(corr_matrix, top_n=top_n_pairs, min_abs_correlation=min_abs_correlation)
    rows = []
    for _, pair in pairs.iterrows():
        divergence = pair_divergence_zscore(
            df,
            symbol_a=pair["symbol_a"],
            symbol_b=pair["symbol_b"],
            window=zscore_window,
            price_col=price_col,
            symbol_col=symbol_col,
            date_col=date_col,
        )
        latest = divergence.dropna(subset=["divergence_zscore"]).tail(1)
        if latest.empty:
            continue
        row = latest.iloc[0].to_dict()
        row["correlation"] = pair["correlation"]
        row["abs_correlation"] = pair["abs_correlation"]
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values("divergence_zscore", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)


def correlation_matrix_by_regime(
    df: pd.DataFrame,
    regime_value: str,
    regime_col: str = "volatility_regime",
    return_col: str = "return_1d",
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
    min_periods: int = 20,
) -> pd.DataFrame:
    subset = df[df[regime_col] == regime_value].copy()
    if subset.empty:
        return pd.DataFrame()
    return_matrix = build_return_matrix(
        subset,
        return_col=return_col,
        price_col=price_col,
        symbol_col=symbol_col,
        date_col=date_col,
    )
    return compute_correlation_matrix(return_matrix, min_periods=min_periods)


def correlations_by_regime(
    df: pd.DataFrame,
    regimes: list[str] | None = None,
    regime_col: str = "volatility_regime",
    return_col: str = "return_1d",
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
    min_periods: int = 20,
) -> dict[str, pd.DataFrame]:
    if regimes is None:
        regimes = [str(x) for x in df[regime_col].dropna().unique()]
    return {
        regime: correlation_matrix_by_regime(
            df,
            regime_value=regime,
            regime_col=regime_col,
            return_col=return_col,
            price_col=price_col,
            symbol_col=symbol_col,
            date_col=date_col,
            min_periods=min_periods,
        )
        for regime in regimes
    }
