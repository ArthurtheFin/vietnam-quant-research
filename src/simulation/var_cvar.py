"""Value at Risk (VaR) and Conditional Value at Risk (CVaR) calculations."""
from __future__ import annotations

import pandas as pd
import numpy as np
from scipy.stats import norm


def calculate_historical_var(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """Calculate historical Value at Risk (VaR) at a given confidence level."""
    r = returns.dropna().to_numpy(dtype=float)
    if len(r) == 0:
        return 0.0
    alpha = 1.0 - confidence_level
    var_val = -np.quantile(r, alpha)
    return max(0.0, float(var_val))


def calculate_historical_cvar(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """Calculate historical Conditional Value at Risk (CVaR) / Expected Shortfall."""
    r = returns.dropna().to_numpy(dtype=float)
    if len(r) == 0:
        return 0.0
    
    var_val = calculate_historical_var(returns, confidence_level=confidence_level)
    exceeding = r[r <= -var_val]
    if len(exceeding) == 0:
        return float(var_val)
    return max(0.0, float(-exceeding.mean()))


def calculate_parametric_var(returns: pd.Series, confidence_level: float = 0.95) -> float:
    """Calculate parametric (variance-covariance) VaR assuming normal distribution."""
    r = returns.dropna().to_numpy(dtype=float)
    if len(r) < 2:
        return 0.0
    mean = r.mean()
    std = r.std(ddof=1)
    
    alpha = 1.0 - confidence_level
    z_score = norm.ppf(alpha)
    
    var_val = -(mean + z_score * std)
    return max(0.0, float(var_val))


def calculate_simulated_var(simulated_returns: np.ndarray, confidence_level: float = 0.95) -> float:
    """Calculate simulated VaR from terminal simulated returns (horizon-level)."""
    if simulated_returns.size == 0:
        return 0.0
    alpha = 1.0 - confidence_level
    var_val = -np.quantile(simulated_returns, alpha)
    return max(0.0, float(var_val))


def calculate_simulated_cvar(simulated_returns: np.ndarray, confidence_level: float = 0.95) -> float:
    """Calculate simulated CVaR from terminal simulated returns (horizon-level)."""
    if simulated_returns.size == 0:
        return 0.0
    var_val = calculate_simulated_var(simulated_returns, confidence_level=confidence_level)
    exceeding = simulated_returns[simulated_returns <= -var_val]
    if len(exceeding) == 0:
        return float(var_val)
    return max(0.0, float(-exceeding.mean()))
