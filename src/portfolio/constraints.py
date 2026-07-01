from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.risk import calculate_portfolio_volatility

def check_weight_constraints(
    weights: pd.Series,
    min_w: float = 0.0,
    max_w: float = 0.25,
) -> dict[str, bool | str]:
    """Checks if weights sum to 1.0 and individual weights fall within bounds."""
    w = weights.fillna(0.0)
    sum_valid = np.isclose(w.sum(), 1.0, atol=1e-4)
    min_valid = (w >= min_w).all()
    max_valid = (w <= max_w).all()
    
    passed = bool(sum_valid and min_valid and max_valid)
    details = f"Sum: {w.sum():.2%}. Min: {w.min():.2%}. Max: {w.max():.2%}"
    
    return {
        "passed": passed,
        "details": details,
    }

def check_risk_constraint(
    weights: pd.Series,
    covariance: pd.DataFrame,
    max_vol: float = 0.10,
) -> dict[str, bool | str]:
    """Checks if portfolio annualized volatility is below the maximum limit."""
    try:
        vol = calculate_portfolio_volatility(weights, covariance, annualized=True)
        passed = vol <= max_vol
        details = f"Portfolio Vol: {vol:.2%}. Max Vol Limit: {max_vol:.2%}"
    except Exception as e:
        passed = False
        details = f"Error: {e}"
        
    return {
        "passed": passed,
        "details": details,
    }

def check_sector_constraints(
    weights: pd.Series,
    sector_series: pd.Series,
    max_sector_weight: float = 0.35,
) -> dict[str, bool | str]:
    """Checks if industry/sector exposures are below the maximum limit."""
    w = weights.fillna(0.0)
    # Align sector mapping
    common = w.index.intersection(sector_series.index)
    if len(common) == 0:
        return {"passed": True, "details": "No sector mapping available."}
        
    aligned_w = w.loc[common]
    aligned_sectors = sector_series.loc[common]
    
    sector_exposures = aligned_w.groupby(aligned_sectors).sum()
    max_sector = sector_exposures.max()
    max_sector_name = sector_exposures.idxmax()
    
    passed = max_sector <= max_sector_weight
    details = f"Max Sector: {max_sector_name} ({max_sector:.2%}). Limit: {max_sector_weight:.2%}"
    
    return {
        "passed": passed,
        "details": details,
    }

def check_liquidity_constraints(
    weights: pd.Series,
    nav: float,
    adtv_series: pd.Series,
    max_pct_adtv: float = 0.10,
) -> dict[str, bool | str]:
    """Checks if position values exceed the maximum allowable percentage of average daily trading volume."""
    w = weights.fillna(0.0)
    common = w.index.intersection(adtv_series.index)
    if len(common) == 0:
        return {"passed": True, "details": "No trading value (ADTV) data available."}
        
    aligned_w = w.loc[common]
    aligned_adtv = adtv_series.loc[common]
    
    position_values = aligned_w * nav
    pct_adtv = position_values / aligned_adtv.replace(0, np.nan)
    max_pct = pct_adtv.max()
    max_symbol = pct_adtv.idxmax()
    
    passed = max_pct <= max_pct_adtv or np.isnan(max_pct)
    details = f"Max Liquidity Draw: {max_symbol} ({max_pct:.2%}). Limit: {max_pct_adtv:.2%}"
    
    return {
        "passed": passed,
        "details": details,
    }

def check_turnover_constraint(
    current_weights: pd.Series,
    previous_weights: pd.Series,
    max_turnover: float = 0.30,
) -> dict[str, bool | str]:
    """Checks if rebalancing turnover is below the maximum constraint limit."""
    all_indices = current_weights.index.union(previous_weights.index)
    w_curr = current_weights.reindex(all_indices).fillna(0.0)
    w_prev = previous_weights.reindex(all_indices).fillna(0.0)
    
    # Turnover = sum(|w_t - w_{t-1}|) / 2
    turnover = float(w_curr.sub(w_prev).abs().sum() / 2)
    passed = turnover <= max_turnover
    details = f"Turnover: {turnover:.2%}. Max Turnover Limit: {max_turnover:.2%}"
    
    return {
        "passed": passed,
        "details": details,
    }
