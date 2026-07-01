"""Drawdown calculation and analytics."""
from __future__ import annotations

import pandas as pd
import numpy as np


def calculate_drawdown(equity_curve: pd.Series) -> pd.Series:
    """Calculate drawdown series from equity curve."""
    if equity_curve.empty:
        return pd.Series(dtype=float)
    running_max = equity_curve.cummax()
    running_max_safe = running_max.replace(0, np.nan)
    drawdowns = (equity_curve - running_max_safe) / running_max_safe
    return drawdowns.fillna(0.0)


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Calculate maximum peak-to-trough drawdown from equity curve."""
    drawdowns = calculate_drawdown(equity_curve)
    if drawdowns.empty:
        return 0.0
    return float(drawdowns.min())


def calculate_recovery_time(equity_curve: pd.Series) -> int:
    """Calculate maximum recovery time (number of steps/days to regain peak)."""
    if equity_curve.empty:
        return 0
    running_max = equity_curve.cummax()
    is_in_drawdown = equity_curve < running_max
    
    max_recovery = 0
    current_recovery = 0
    for val in is_in_drawdown:
        if val:
            current_recovery += 1
            if current_recovery > max_recovery:
                max_recovery = current_recovery
        else:
            current_recovery = 0
            
    return max_recovery


def calculate_symbol_drawdowns(
    df: pd.DataFrame,
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
) -> pd.DataFrame:
    """Calculate drawdown curve for each symbol in a daily DataFrame."""
    out = df.sort_values([symbol_col, date_col]).copy()
    drawdown_list = []
    for _, group in out.groupby(symbol_col):
        prices = group[price_col]
        cum_prices = (1.0 + prices.pct_change().fillna(0.0)).cumprod() * 100.0
        dd = calculate_drawdown(cum_prices)
        drawdown_list.append(dd)
    
    out["drawdown"] = pd.concat(drawdown_list).sort_index() if drawdown_list else pd.Series(dtype=float)
    return out
