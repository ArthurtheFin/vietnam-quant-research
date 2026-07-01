from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.portfolio.construction import (
    equal_weight_allocation,
    maximize_sharpe_ratio,
    _sanitize_covariance,
    _normalize_weights,
)

def equal_weight_portfolio(symbols: list[str] | pd.Index | pd.Series) -> pd.Series:
    """Returns equal-weighted allocation for symbols."""
    return equal_weight_allocation(symbols)

def optimize_max_return_under_risk(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    max_volatility: float = 0.10,
    max_weight: float = 0.25,
    periods_per_year: int = 252,
) -> pd.Series:
    """
    Objective 1: Maximize expected portfolio return under a risk (annualized volatility) constraint.
    Maximize: w^T * mu (Minimize: -w^T * mu)
    Subject to:
      sum(w) = 1
      w_i in [0.0, max_weight]
      annualized_volatility(w) <= max_volatility
    """
    cov = _sanitize_covariance(covariance)
    if cov.empty or expected_returns.empty:
        return pd.Series(dtype=float, name="weight")

    common_idx = cov.index.intersection(expected_returns.index)
    cov = cov.loc[common_idx, common_idx]
    er = expected_returns.loc[common_idx]
    n = len(common_idx)
    if n == 0:
        return pd.Series(dtype=float, name="weight")

    # Objective: Minimize negative expected return
    def objective(w):
        return -float(w.T @ er.to_numpy())

    # Constraints:
    # 1. Weights sum to 1.0
    eq_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    # 2. Annualized volatility <= max_volatility
    # Volatility limit inequality: max_volatility - vol >= 0
    def vol_ineq(w):
        port_var = float(w.T @ cov.to_numpy() @ w)
        port_vol = np.sqrt(port_var) * np.sqrt(periods_per_year) if port_var > 0 else 0.0
        return max_volatility - port_vol

    vol_constraint = {"type": "ineq", "fun": vol_ineq}

    bounds = tuple((0.0, max_weight) for _ in range(n))
    init_guess = np.ones(n) / n

    res = minimize(
        objective,
        init_guess,
        method="SLSQP",
        bounds=bounds,
        constraints=[eq_constraint, vol_constraint],
    )

    if not res.success:
        # Fallback: if optimization fails, try to return equal weight
        return equal_weight_allocation(common_idx)

    return _normalize_weights(pd.Series(res.x, index=common_idx, name="weight"))

def optimize_min_risk_for_target_return(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    target_return: float,
    max_weight: float = 0.25,
    periods_per_year: int = 252,
) -> pd.Series:
    """
    Objective 2: Minimize portfolio risk for a target expected return.
    Minimize: w^T * Sigma * w
    Subject to:
      sum(w) = 1
      w_i in [0.0, max_weight]
      w^T * mu >= target_return
    """
    cov = _sanitize_covariance(covariance)
    if cov.empty or expected_returns.empty:
        return pd.Series(dtype=float, name="weight")

    common_idx = cov.index.intersection(expected_returns.index)
    cov = cov.loc[common_idx, common_idx]
    er = expected_returns.loc[common_idx]
    n = len(common_idx)
    if n == 0:
        return pd.Series(dtype=float, name="weight")

    # Objective: Minimize variance
    def objective(w):
        return float(w.T @ cov.to_numpy() @ w)

    # Constraints:
    # 1. Weights sum to 1.0
    eq_constraint = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    # 2. Return >= target_return
    def return_ineq(w):
        port_ret = float(w.T @ er.to_numpy())
        return port_ret - target_return

    return_constraint = {"type": "ineq", "fun": return_ineq}

    bounds = tuple((0.0, max_weight) for _ in range(n))
    init_guess = np.ones(n) / n

    res = minimize(
        objective,
        init_guess,
        method="SLSQP",
        bounds=bounds,
        constraints=[eq_constraint, return_constraint],
    )

    if not res.success:
        return equal_weight_allocation(common_idx)

    return _normalize_weights(pd.Series(res.x, index=common_idx, name="weight"))

def optimize_max_sharpe(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    risk_free_rate: float = 0.03,
    max_weight: float = 0.25,
    periods_per_year: int = 252,
) -> pd.Series:
    """
    Objective 3: Maximize risk-adjusted return (Sharpe Ratio).
    Wraps maximize_sharpe_ratio helper.
    """
    cov_annual = covariance * periods_per_year
    return maximize_sharpe_ratio(
        expected_returns=expected_returns,
        covariance=cov_annual,
        risk_free_rate=risk_free_rate,
        max_weight=max_weight,
    )

