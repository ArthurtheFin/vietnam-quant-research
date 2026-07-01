from __future__ import annotations

import numpy as np
import pandas as pd


def build_return_matrix(
    df: pd.DataFrame,
    return_col: str = "return_1d",
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
) -> pd.DataFrame:
    out = df.copy()
    if return_col not in out.columns:
        out = out.sort_values([symbol_col, date_col]).copy()
        out[return_col] = out.groupby(symbol_col)[price_col].pct_change()

    out[date_col] = pd.to_datetime(out[date_col])
    matrix = (
        out.pivot_table(index=date_col, columns=symbol_col, values=return_col, aggfunc="last")
        .sort_index()
        .sort_index(axis=1)
    )
    matrix = matrix.replace([np.inf, -np.inf], np.nan)
    return matrix


def compute_correlation_matrix(
    data: pd.DataFrame,
    method: str = "pearson",
    min_periods: int = 20,
) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame()
    return data.corr(method=method, min_periods=min_periods)


def top_correlation_pairs(
    corr_matrix: pd.DataFrame,
    top_n: int = 20,
    min_abs_correlation: float = 0.5,
) -> pd.DataFrame:
    if corr_matrix.empty:
        return pd.DataFrame(columns=["symbol_a", "symbol_b", "correlation", "abs_correlation"])

    pairs = []
    columns = list(corr_matrix.columns)
    for i, col_a in enumerate(columns):
        for col_b in columns[i + 1 :]:
            corr = corr_matrix.loc[col_a, col_b]
            if pd.isna(corr):
                continue
            if abs(corr) < min_abs_correlation:
                continue
            pairs.append(
                {
                    "symbol_a": col_a,
                    "symbol_b": col_b,
                    "correlation": float(corr),
                    "abs_correlation": float(abs(corr)),
                }
            )

    if not pairs:
        return pd.DataFrame(columns=["symbol_a", "symbol_b", "correlation", "abs_correlation"])

    return pd.DataFrame(pairs).sort_values(
        ["abs_correlation", "correlation"],
        ascending=[False, False],
    ).head(top_n).reset_index(drop=True)


def rolling_pair_correlation(
    df: pd.DataFrame,
    symbol_a: str,
    symbol_b: str,
    window: int = 60,
    return_col: str = "return_1d",
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
) -> pd.DataFrame:
    matrix = build_return_matrix(
        df,
        return_col=return_col,
        price_col=price_col,
        symbol_col=symbol_col,
        date_col=date_col,
    )
    required = [symbol_a, symbol_b]
    if not set(required).issubset(matrix.columns):
        missing = [symbol for symbol in required if symbol not in matrix.columns]
        raise KeyError(f"Missing symbol(s) in return matrix: {missing}")

    pair = matrix[required].dropna(how="all").copy()
    rolling_corr = pair[symbol_a].rolling(window).corr(pair[symbol_b])
    return pd.DataFrame(
        {
            "date": pair.index,
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "rolling_correlation": rolling_corr.values,
        }
    )
