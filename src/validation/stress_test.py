from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.risk import calculate_portfolio_volatility, calculate_portfolio_variance

def run_market_drawdown_stress(
    weights: pd.Series,
    returns: pd.DataFrame,
    market_drop: float = -0.05,
) -> dict[str, float]:
    """
    Simulates portfolio return under a systematic market drawdown.
    Calculates expected return assuming every asset in the portfolio experiences
    the specified drop scaled by its historical beta.
    """
    common_idx = weights.index.intersection(returns.columns)
    if len(common_idx) == 0:
        return {"expected_portfolio_loss": 0.0}
        
    w = weights.loc[common_idx]
    w = w / w.sum()
    
    # Calculate historical beta for each asset relative to equal-weight market index
    mkt = returns.mean(axis=1)
    mkt_var = mkt.var(ddof=1)
    
    expected_asset_losses = []
    for sym in common_idx:
        asset_ret = returns[sym]
        cov = asset_ret.cov(mkt)
        beta = cov / mkt_var if mkt_var > 0 else 1.0
        expected_loss = beta * market_drop
        expected_asset_losses.append(expected_loss)
        
    expected_losses_s = pd.Series(expected_asset_losses, index=common_idx)
    port_loss = float(w @ expected_losses_s)
    
    return {
        "market_shock": market_drop,
        "expected_portfolio_loss": port_loss,
    }

def run_correlation_shock(
    weights: pd.Series,
    covariance: pd.DataFrame,
    multiplier: float = 1.5,
) -> float:
    """
    Simulates portfolio volatility under a correlation shock.
    It decomposes the covariance matrix into standard deviations and correlation matrix,
    scales the pairwise correlations by the multiplier (capped at 1.0),
    and reconstructs the covariance matrix to find the shocked volatility.
    """
    common_idx = weights.index.intersection(covariance.index)
    if len(common_idx) == 0:
        return 0.0
        
    w = weights.loc[common_idx]
    w = w / w.sum()
    
    cov = covariance.loc[common_idx, common_idx].to_numpy()
    
    # Extract standard deviations
    std = np.sqrt(np.diag(cov))
    
    # Compute correlation matrix
    denom = np.outer(std, std)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = cov / denom
    corr = np.where(np.isfinite(corr), corr, 0.0)
    
    # Apply shock to off-diagonal elements
    shocked_corr = corr * multiplier
    np.fill_diagonal(shocked_corr, 1.0)
    shocked_corr = np.clip(shocked_corr, -1.0, 1.0)
    
    # Reconstruct covariance matrix
    shocked_cov = shocked_corr * denom
    
    # Shocked portfolio volatility
    w_arr = w.to_numpy()
    shocked_var = float(w_arr.T @ shocked_cov @ w_arr)
    
    return float(np.sqrt(shocked_var) * np.sqrt(252)) if shocked_var > 0 else 0.0

def run_volatility_shock(
    weights: pd.Series,
    covariance: pd.DataFrame,
    multiplier: float = 1.5,
) -> float:
    """
    Simulates portfolio volatility under a volatility spike.
    Scales the diagonal standard deviations by the multiplier, keeping correlations intact.
    """
    common_idx = weights.index.intersection(covariance.index)
    if len(common_idx) == 0:
        return 0.0
        
    w = weights.loc[common_idx]
    w = w / w.sum()
    
    cov = covariance.loc[common_idx, common_idx].to_numpy()
    
    # Extract std and corr
    std = np.sqrt(np.diag(cov))
    denom = np.outer(std, std)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = cov / denom
    corr = np.where(np.isfinite(corr), corr, 0.0)
    
    # Shock volatility standard deviations
    shocked_std = std * multiplier
    shocked_denom = np.outer(shocked_std, shocked_std)
    
    # Reconstruct covariance
    shocked_cov = corr * shocked_denom
    
    # Shocked volatility
    w_arr = w.to_numpy()
    shocked_var = float(w_arr.T @ shocked_cov @ w_arr)
    
    return float(np.sqrt(shocked_var) * np.sqrt(252)) if shocked_var > 0 else 0.0
