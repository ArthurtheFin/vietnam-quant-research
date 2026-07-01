from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.construction import shrink_covariance, _cov_to_corr, portfolio_risk_contributions

def calculate_covariance_matrix(
    return_matrix: pd.DataFrame,
    shrinkage: float = 0.15,
) -> pd.DataFrame:
    """Calculates the covariance matrix, optionally applying shrinkage."""
    raw_cov = return_matrix.cov()
    return shrink_covariance(raw_cov, shrinkage=shrinkage)

def calculate_correlation_matrix(
    covariance: pd.DataFrame,
) -> pd.DataFrame:
    """Calculates the correlation matrix from a covariance matrix."""
    return _cov_to_corr(covariance)

def calculate_portfolio_variance(
    weights: pd.Series,
    covariance: pd.DataFrame,
) -> float:
    """Calculates portfolio variance: w^T * Sigma * w."""
    common_idx = weights.index.intersection(covariance.index)
    if len(common_idx) == 0:
        return 0.0
    w = weights.loc[common_idx]
    total_w = float(w.sum())
    if total_w > 0:
        w = w / total_w
    cov = covariance.loc[common_idx, common_idx].to_numpy()
    w_arr = w.to_numpy()
    return float(w_arr.T @ cov @ w_arr)

def calculate_portfolio_volatility(
    weights: pd.Series,
    covariance: pd.DataFrame,
    annualized: bool = True,
    periods_per_year: int = 252,
) -> float:
    """Calculates portfolio volatility (annualized standard deviation by default)."""
    variance = calculate_portfolio_variance(weights, covariance)
    if variance <= 0:
        return 0.0
    vol = np.sqrt(variance)
    if annualized:
        return float(vol * np.sqrt(periods_per_year))
    return float(vol)

def calculate_risk_contribution(
    weights: pd.Series,
    covariance: pd.DataFrame,
) -> pd.DataFrame:
    """Calculates marginal, total, and percentage risk contribution of each asset."""
    common_idx = weights.index.intersection(covariance.index)
    if len(common_idx) == 0:
        return pd.DataFrame(columns=["symbol", "weight", "marginal_contribution", "total_contribution", "risk_contribution_pct"])
    
    w = weights.loc[common_idx]
    total_w = float(w.sum())
    if total_w > 0:
        w = w / total_w
        
    cov = covariance.loc[common_idx, common_idx].to_numpy()
    w_arr = w.to_numpy()
    
    # Portfolio variance and volatility
    port_var = float(w_arr.T @ cov @ w_arr)
    port_vol = np.sqrt(port_var) if port_var > 0 else 1e-8
    
    # Marginal contribution: (Sigma * w) / vol
    marginal = (cov @ w_arr) / port_vol
    
    # Total contribution: w * marginal
    total_contrib = w_arr * marginal
    
    # Percentage contribution
    pct_contrib = total_contrib / port_vol if port_vol > 0 else np.zeros_like(total_contrib)
    
    return pd.DataFrame({
        "symbol": w.index,
        "weight": w.values,
        "marginal_contribution": marginal,
        "total_contribution": total_contrib,
        "risk_contribution_pct": pct_contrib * 100.0,
    }).reset_index(drop=True)
