from __future__ import annotations

import numpy as np
import pandas as pd
import itertools


from src.portfolio.returns import calculate_portfolio_return
from src.portfolio.risk import calculate_portfolio_volatility, calculate_portfolio_variance, calculate_risk_contribution
from src.portfolio.constraints import (
    check_weight_constraints,
    check_risk_constraint,
    check_sector_constraints,
    check_liquidity_constraints,
)

def generate_random_weights(
    n_symbols: int,
    n_portfolios: int = 5000,
    max_weight: float = 0.25,
    min_weight: float = 0.0,
) -> np.ndarray:
    """
    Generates random weights on the simplex (sum to 1.0) with individual bounds
    using rejection sampling. Falls back to equal weights if acceptance is too low.
    """
    weights_list = []
    attempts = 0
    max_attempts = n_portfolios * 200
    
    while len(weights_list) < n_portfolios and attempts < max_attempts:
        attempts += 1
        # Exponential distribution yields uniform distribution on the simplex
        w = np.random.exponential(1.0, n_symbols)
        w /= w.sum()
        if (w >= min_weight).all() and (w <= max_weight).all():
            weights_list.append(w)
            
    # Fallback to fill shortfall
    if len(weights_list) < n_portfolios:
        shortfall = n_portfolios - len(weights_list)
        equal_w = np.ones(n_symbols) / n_symbols
        for _ in range(shortfall):
            weights_list.append(equal_w)
            
    return np.array(weights_list)

def evaluate_portfolio(
    weights: pd.Series,
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    sector_series: pd.Series | None = None,
    adtv_series: pd.Series | None = None,
    nav: float = 1e9,
    max_vol: float = 0.10,
    max_sector: float = 0.35,
    max_pct_adtv: float = 0.10,
    risk_free_rate: float = 0.03,
    lambda_penalty: float = 1.0,
) -> dict[str, any]:
    """
    Evaluates returns, risk, Sharpe ratio, penalty score, and checks constraints
    for a single portfolio weight vector.
    """
    # 1. Math calculations
    port_ret = calculate_portfolio_return(weights, expected_returns)
    port_var = calculate_portfolio_variance(weights, covariance)
    port_vol = calculate_portfolio_volatility(weights, covariance, annualized=True)
    
    sharpe = (port_ret - risk_free_rate) / port_vol if port_vol > 0 else 0.0
    balanced_score = port_ret - lambda_penalty * port_var
    
    # 2. Constraint verification
    # Weight bounds
    w_check = check_weight_constraints(weights)
    # Volatility bounds
    v_check = check_risk_constraint(weights, covariance, max_vol=max_vol)
    
    # Sector limits
    s_check = {"passed": True, "details": "N/A"}
    if sector_series is not None and not sector_series.empty:
        s_check = check_sector_constraints(weights, sector_series, max_sector_weight=max_sector)
        
    # Liquidity limits
    l_check = {"passed": True, "details": "N/A"}
    if adtv_series is not None and not adtv_series.empty:
        l_check = check_liquidity_constraints(weights, nav, adtv_series, max_pct_adtv=max_pct_adtv)
        
    passed = bool(w_check["passed"] and v_check["passed"] and s_check["passed"] and l_check["passed"])
    
    fail_reasons = []
    if not w_check["passed"]:
        fail_reasons.append("Weights boundary violation")
    if not v_check["passed"]:
        fail_reasons.append("Risk limit violation")
    if not s_check["passed"]:
        fail_reasons.append("Sector cap violation")
    if not l_check["passed"]:
        fail_reasons.append("Liquidity ADTV limit violation")
        
    fail_reason = "; ".join(fail_reasons) if fail_reasons else "PASS"
    
    return {
        "expected_return": port_ret,
        "portfolio_variance": port_var,
        "portfolio_volatility": port_vol,
        "sharpe_ratio": sharpe,
        "balanced_score": balanced_score,
        "constraint_status": "PASS" if passed else "FAIL",
        "fail_reason": fail_reason,
    }

def generate_random_portfolios(
    symbols: list[str],
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    n_portfolios: int = 5000,
    max_weight: float = 0.25,
    min_weight: float = 0.0,
    sector_series: pd.Series | None = None,
    adtv_series: pd.Series | None = None,
    nav: float = 1e9,
    max_vol: float = 0.10,
    max_sector: float = 0.35,
    max_pct_adtv: float = 0.10,
    risk_free_rate: float = 0.03,
    lambda_penalty: float = 1.0,
) -> pd.DataFrame:
    """
    Simulates N random portfolios and calculates returns, volatility, Sharpe, and constraint status.
    """
    n_symbols = len(symbols)
    weights_matrix = generate_random_weights(
        n_symbols=n_symbols,
        n_portfolios=n_portfolios,
        max_weight=max_weight,
        min_weight=min_weight,
    )
    
    records = []
    for idx in range(n_portfolios):
        w_vec = pd.Series(weights_matrix[idx], index=symbols)
        metrics = evaluate_portfolio(
            weights=w_vec,
            expected_returns=expected_returns,
            covariance=covariance,
            sector_series=sector_series,
            adtv_series=adtv_series,
            nav=nav,
            max_vol=max_vol,
            max_sector=max_sector,
            max_pct_adtv=max_pct_adtv,
            risk_free_rate=risk_free_rate,
            lambda_penalty=lambda_penalty,
        )
        
        row = {
            "portfolio_id": idx,
            "expected_return": metrics["expected_return"],
            "portfolio_variance": metrics["portfolio_variance"],
            "portfolio_volatility": metrics["portfolio_volatility"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "balanced_score": metrics["balanced_score"],
            "constraint_status": metrics["constraint_status"],
            "fail_reason": metrics["fail_reason"],
        }
        # Add weights as string or dict to reconstruct later
        for s_idx, sym in enumerate(symbols):
            row[f"w_{sym}"] = weights_matrix[idx][s_idx]
            
        records.append(row)
        
    return pd.DataFrame(records)

def select_best_portfolio(
    portfolios_df: pd.DataFrame,
    symbols: list[str],
    mode: str = "max_sharpe",
    target_return: float = 0.15,
    max_volatility: float = 0.10,
) -> tuple[pd.Series, dict[str, any]]:
    """
    Picks the best portfolio from simulated portfolios based on selected modes,
    prioritizing portfolios that PASS constraints.
    """
    # 1. Filter PASS portfolios
    valid = portfolios_df[portfolios_df["constraint_status"] == "PASS"].copy()
    if valid.empty:
        # Fallback to all if none passed (soft constraints)
        valid = portfolios_df.copy()
        
    # 2. Select according to mode
    if mode == "max_return_under_risk":
        # Mode 1: Max expected return under risk limit
        under_risk = valid[valid["portfolio_volatility"] <= max_volatility]
        if under_risk.empty:
            under_risk = valid.copy()
        best_row = under_risk.sort_values("expected_return", ascending=False).iloc[0]
    elif mode == "min_risk":
        # Mode 3: Min risk with acceptable return
        above_ret = valid[valid["expected_return"] >= target_return]
        if above_ret.empty:
            above_ret = valid.copy()
        best_row = above_ret.sort_values("portfolio_volatility", ascending=True).iloc[0]
    elif mode == "balanced_score":
        # Mode 4: Balanced score
        best_row = valid.sort_values("balanced_score", ascending=False).iloc[0]
    else:
        # Mode 2: Max Sharpe ratio (default)
        best_row = valid.sort_values("sharpe_ratio", ascending=False).iloc[0]
        
    # 3. Extract weights Series and metrics
    w_dict = {sym: float(best_row[f"w_{sym}"]) for sym in symbols}
    w_series = pd.Series(w_dict, name="weight")
    
    metrics = {
        "portfolio_id": int(best_row["portfolio_id"]),
        "expected_return": float(best_row["expected_return"]),
        "portfolio_volatility": float(best_row["portfolio_volatility"]),
        "sharpe_ratio": float(best_row["sharpe_ratio"]),
        "balanced_score": float(best_row["balanced_score"]),
        "constraint_status": str(best_row["constraint_status"]),
        "fail_reason": str(best_row["fail_reason"]),
    }
    
    return w_series, metrics


def generate_sub_portfolios(
    symbols: list[str],
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    min_size: int = 3,
    max_size: int = 5,
    sector_series: pd.Series | None = None,
    adtv_series: pd.Series | None = None,
    nav: float = 1e9,
    max_vol: float = 0.10,
    max_sector: float = 0.35,
    max_pct_adtv: float = 0.10,
    risk_free_rate: float = 0.03,
) -> pd.DataFrame:
    """
    Enumerates all possible combinations of size min_size to max_size from the symbols list.
    For each combination, it calculates equal-weighted and optimized weights, evaluates metrics,
    and returns a DataFrame.
    """
    records = []
    portfolio_counter = 0
    
    for size in range(min_size, max_size + 1):
        for combo in itertools.combinations(symbols, size):
            combo_list = list(combo)
            portfolio_counter += 1
            
            # --- 1. Equal-Weight Portfolio for this combination ---
            eq_weights = pd.Series(0.0, index=symbols)
            eq_weights[combo_list] = 1.0 / len(combo_list)
            
            eq_metrics = evaluate_portfolio(
                weights=eq_weights,
                expected_returns=expected_returns,
                covariance=covariance,
                sector_series=sector_series,
                adtv_series=adtv_series,
                nav=nav,
                max_vol=max_vol,
                max_sector=max_sector,
                max_pct_adtv=max_pct_adtv,
                risk_free_rate=risk_free_rate,
            )
            
            # --- 2. Max Sharpe Optimized Portfolio for this combination ---
            sub_er = expected_returns.loc[combo_list]
            sub_cov = covariance.loc[combo_list, combo_list]
            
            from src.portfolio.optimization import optimize_max_sharpe
            try:
                sub_opt_w = optimize_max_sharpe(
                    expected_returns=sub_er,
                    covariance=sub_cov,
                    risk_free_rate=risk_free_rate,
                    max_weight=0.50,
                )
                opt_weights = pd.Series(0.0, index=symbols)
                opt_weights[sub_opt_w.index] = sub_opt_w.values
            except Exception:
                opt_weights = eq_weights.copy()
                
            opt_metrics = evaluate_portfolio(
                weights=opt_weights,
                expected_returns=expected_returns,
                covariance=covariance,
                sector_series=sector_series,
                adtv_series=adtv_series,
                nav=nav,
                max_vol=max_vol,
                max_sector=max_sector,
                max_pct_adtv=max_pct_adtv,
                risk_free_rate=risk_free_rate,
            )
            
            # Append Equal Weight record
            eq_row = {
                "portfolio_name": f"Portfolio {portfolio_counter} (EQ)",
                "size": size,
                "tickers": ", ".join(combo_list),
                "type": "Equal-Weight",
                "expected_return": eq_metrics["expected_return"],
                "portfolio_volatility": eq_metrics["portfolio_volatility"],
                "sharpe_ratio": eq_metrics["sharpe_ratio"],
                "constraint_status": eq_metrics["constraint_status"],
                "fail_reason": eq_metrics["fail_reason"],
            }
            # Store weights
            for sym in symbols:
                eq_row[f"w_{sym}"] = eq_weights[sym]
            records.append(eq_row)
            
            # Append Opt record
            opt_row = {
                "portfolio_name": f"Portfolio {portfolio_counter} (OPT)",
                "size": size,
                "tickers": ", ".join(combo_list),
                "type": "Optimized",
                "expected_return": opt_metrics["expected_return"],
                "portfolio_volatility": opt_metrics["portfolio_volatility"],
                "sharpe_ratio": opt_metrics["sharpe_ratio"],
                "constraint_status": opt_metrics["constraint_status"],
                "fail_reason": opt_metrics["fail_reason"],
            }
            for sym in symbols:
                opt_row[f"w_{sym}"] = opt_weights[sym]
            records.append(opt_row)
            
    return pd.DataFrame(records)

