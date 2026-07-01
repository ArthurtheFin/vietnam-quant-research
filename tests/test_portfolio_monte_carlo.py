import numpy as np
import pandas as pd
import pytest

from src.portfolio.monte_carlo import (
    generate_random_weights,
    evaluate_portfolio,
    generate_random_portfolios,
    select_best_portfolio,
)

def test_generate_random_weights():
    n_symbols = 5
    n_portfolios = 100
    max_weight = 0.40
    min_weight = 0.05
    
    weights = generate_random_weights(
        n_symbols=n_symbols,
        n_portfolios=n_portfolios,
        max_weight=max_weight,
        min_weight=min_weight,
    )
    
    assert weights.shape == (n_portfolios, n_symbols)
    # Check weights sum to 1.0
    assert np.allclose(weights.sum(axis=1), 1.0)
    # Check weight bounds
    assert (weights >= min_weight).all()
    assert (weights <= max_weight).all()

def test_evaluate_portfolio():
    symbols = ["A", "B", "C"]
    weights = pd.Series([0.4, 0.4, 0.2], index=symbols)
    expected_returns = pd.Series([0.15, 0.12, 0.08], index=symbols)
    covariance = pd.DataFrame([
        [0.0004, 0.0001, 0.0],
        [0.0001, 0.0003, 0.0],
        [0.0, 0.0, 0.0002]
    ], index=symbols, columns=symbols)
    
    metrics = evaluate_portfolio(
        weights=weights,
        expected_returns=expected_returns,
        covariance=covariance,
        max_vol=0.15,
        risk_free_rate=0.03,
    )
    
    assert metrics["expected_return"] > 0.0
    assert metrics["portfolio_volatility"] > 0.0
    assert metrics["sharpe_ratio"] > 0.0
    assert metrics["constraint_status"] in ["PASS", "FAIL"]

def test_select_best_portfolio():
    symbols = ["A", "B", "C"]
    expected_returns = pd.Series([0.20, 0.15, 0.10], index=symbols)
    covariance = pd.DataFrame([
        [0.0005, 0.0, 0.0],
        [0.0, 0.0004, 0.0],
        [0.0, 0.0, 0.0003]
    ], index=symbols, columns=symbols)
    
    portfolios_df = generate_random_portfolios(
        symbols=symbols,
        expected_returns=expected_returns,
        covariance=covariance,
        n_portfolios=50,
        max_weight=0.50,
        min_weight=0.0,
        max_vol=0.20,
    )
    
    # Test Max Sharpe
    w_sharpe, m_sharpe = select_best_portfolio(
        portfolios_df=portfolios_df,
        symbols=symbols,
        mode="max_sharpe",
    )
    assert len(w_sharpe) == len(symbols)
    assert np.isclose(w_sharpe.sum(), 1.0)
    assert m_sharpe["sharpe_ratio"] > 0.0
