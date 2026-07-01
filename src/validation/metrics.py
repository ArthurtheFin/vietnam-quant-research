from __future__ import annotations

import numpy as np
import pandas as pd

from src.risk.management import (
    annualized_return,
    annualized_volatility,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    max_drawdown,
    turnover_from_weight_history,
)

def calculate_cagr(nav_series: pd.Series, periods_per_year: int = 252) -> float:
    """Calculates CAGR from NAV series."""
    returns = nav_series.pct_change().dropna()
    return annualized_return(returns, periods_per_year=periods_per_year)

def calculate_sharpe(returns: pd.Series, risk_free_rate: float = 0.03, periods_per_year: int = 252) -> float:
    """Calculates Sharpe ratio."""
    return sharpe_ratio(returns, risk_free_rate=risk_free_rate, periods_per_year=periods_per_year)

def calculate_sortino(returns: pd.Series, target_rate: float = 0.0, periods_per_year: int = 252) -> float:
    """Calculates Sortino ratio."""
    return sortino_ratio(returns, target_rate=target_rate, periods_per_year=periods_per_year)

def calculate_calmar(returns: pd.Series, periods_per_year: int = 252) -> float:
    """Calculates Calmar ratio."""
    return calmar_ratio(returns, periods_per_year=periods_per_year)

def calculate_max_drawdown(nav_series: pd.Series) -> float:
    """Calculates Maximum Drawdown (as a negative percentage)."""
    return max_drawdown(nav_series)

def calculate_turnover(weight_history: pd.DataFrame) -> float:
    """Calculates average portfolio turnover per rebalance period."""
    return turnover_from_weight_history(weight_history)

def calculate_time_under_water(nav_series: pd.Series) -> float:
    """Calculates the percentage of trading periods the portfolio is in a drawdown state."""
    if nav_series.empty:
        return 0.0
    peak = nav_series.cummax()
    underwater = nav_series < peak
    return float(underwater.mean())
