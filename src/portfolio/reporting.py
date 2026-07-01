from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.returns import calculate_portfolio_return
from src.portfolio.risk import calculate_portfolio_volatility, calculate_risk_contribution
from src.portfolio.constraints import (
    check_weight_constraints,
    check_risk_constraint,
    check_sector_constraints,
    check_liquidity_constraints,
)

def generate_portfolio_summary(
    weights: pd.Series,
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    risk_free_rate: float = 0.03,
) -> dict[str, float]:
    """Generates standard quantitative summary metrics for the portfolio."""
    port_ret = calculate_portfolio_return(weights, expected_returns)
    port_vol = calculate_portfolio_volatility(weights, covariance, annualized=True)
    sharpe = (port_ret - risk_free_rate) / port_vol if port_vol > 0 else 0.0
    
    return {
        "expected_return": port_ret,
        "annualized_volatility": port_vol,
        "sharpe_ratio": sharpe,
    }

def generate_constraint_check_table(
    weights: pd.Series,
    covariance: pd.DataFrame,
    sector_series: pd.Series | None = None,
    adtv_series: pd.Series | None = None,
    nav: float = 1_000_000_000,
    max_vol: float = 0.10,
    max_sector: float = 0.35,
    max_pct_adtv: float = 0.10,
) -> pd.DataFrame:
    """Compiles a summary table of constraint compliance."""
    sector_s = sector_series if sector_series is not None else pd.Series(dtype="object")
    adtv_s = adtv_series if adtv_series is not None else pd.Series(dtype=float)
    
    checks = []
    
    # 1. Weights
    w_check = check_weight_constraints(weights, min_w=0.0, max_w=0.25)
    checks.append({"Constraint": "Weights Boundary & Sum", "Passed": w_check["passed"], "Details": w_check["details"]})
    
    # 2. Risk
    r_check = check_risk_constraint(weights, covariance, max_vol=max_vol)
    checks.append({"Constraint": f"Annual Volatility <= {max_vol:.0%}", "Passed": r_check["passed"], "Details": r_check["details"]})
    
    # 3. Sector
    if not sector_s.empty:
        s_check = check_sector_constraints(weights, sector_s, max_sector_weight=max_sector)
        checks.append({"Constraint": f"Sector Cap <= {max_sector:.0%}", "Passed": s_check["passed"], "Details": s_check["details"]})
    else:
        checks.append({"Constraint": "Sector Cap Constraint", "Passed": True, "Details": "Skipped (No Sector Data)"})
        
    # 4. Liquidity
    if not adtv_s.empty:
        l_check = check_liquidity_constraints(weights, nav, adtv_s, max_pct_adtv=max_pct_adtv)
        checks.append({"Constraint": f"Liquidity ADTV Limit <= {max_pct_adtv:.0%}", "Passed": l_check["passed"], "Details": l_check["details"]})
    else:
        checks.append({"Constraint": "Liquidity ADTV Constraint", "Passed": True, "Details": "Skipped (No Liquidity Data)"})
        
    return pd.DataFrame(checks)

def generate_risk_contribution_table(
    weights: pd.Series,
    covariance: pd.DataFrame,
) -> pd.DataFrame:
    """Generates the structured risk contributions table."""
    return calculate_risk_contribution(weights, covariance)

def generate_correlation_report(
    return_matrix: pd.DataFrame,
    threshold: float = 0.70,
) -> dict[str, any]:
    """Analyzes the correlation matrix of return series and flags highly correlated pairs."""
    if return_matrix.empty or len(return_matrix.columns) < 2:
        return {
            "average_pairwise_correlation": 0.0,
            "max_correlation": 0.0,
            "max_correlation_pair": None,
            "high_correlation_alerts": [],
        }
        
    corr = return_matrix.corr()
    
    # Pairwise correlations (exclude diagonal)
    mask = np.triu(np.ones(corr.shape), k=1).astype(bool)
    tri_corr = corr.where(mask).stack()
    
    avg_corr = float(tri_corr.mean())
    max_corr = float(tri_corr.max()) if not tri_corr.empty else 0.0
    max_pair = tri_corr.idxmax() if not tri_corr.empty else None
    
    alerts = []
    for pair, val in tri_corr.items():
        if val >= threshold:
            alerts.append(f"{pair[0]} vs {pair[1]}: {val:.2f}")
            
    return {
        "average_pairwise_correlation": avg_corr,
        "max_correlation": max_corr,
        "max_correlation_pair": max_pair,
        "high_correlation_alerts": alerts,
    }
