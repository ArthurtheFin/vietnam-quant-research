from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.correlation import build_return_matrix

def calculate_returns_matrix(
    signals_df: pd.DataFrame,
    return_col: str = "return_1d",
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
) -> pd.DataFrame:
    """Builds a returns matrix from pivoted signals data."""
    return build_return_matrix(
        df=signals_df,
        return_col=return_col,
        price_col=price_col,
        symbol_col=symbol_col,
        date_col=date_col,
    )

def estimate_expected_returns(
    return_matrix: pd.DataFrame,
    annualized: bool = True,
    periods_per_year: int = 252,
) -> pd.Series:
    """Estimates expected returns vector (mean daily return, optionally annualized)."""
    mean_ret = return_matrix.mean()
    if annualized:
        return mean_ret * periods_per_year
    return mean_ret

def calculate_portfolio_return(
    weights: pd.Series,
    expected_returns: pd.Series,
) -> float:
    """Calculates static expected portfolio return: w^T * mu."""
    common_idx = weights.index.intersection(expected_returns.index)
    if len(common_idx) == 0:
        return 0.0
    w = weights.loc[common_idx]
    # Normalize weights to sum to 1.0 to ensure correct calculation
    total_w = float(w.sum())
    if total_w > 0:
        w = w / total_w
    er = expected_returns.loc[common_idx]
    return float(w.to_numpy() @ er.to_numpy())
