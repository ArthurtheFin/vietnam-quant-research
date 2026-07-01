from __future__ import annotations

import pandas as pd
import numpy as np

from src.backtest.simulator import backtest_entries_with_fixed_stop, summarize_trades
from src.portfolio.optimization import optimize_max_return_under_risk
from src.portfolio.risk import calculate_portfolio_volatility

def run_parameter_sensitivity(
    entries_df: pd.DataFrame,
    price_df: pd.DataFrame,
    holding_periods: list[int] | None = None,
    stop_losses: list[float] | None = None,
    cost: float = 0.004,
) -> pd.DataFrame:
    """Sweeps over different holding periods and stop losses to test breakout strategy parameter sensitivity."""
    holding_periods = holding_periods or [5, 10, 20, 30]
    stop_losses = stop_losses or [-0.03, -0.05, -0.07, -0.10, -0.12]
    
    records = []
    for hp in holding_periods:
        for sl in stop_losses:
            trades = backtest_entries_with_fixed_stop(
                entries_df=entries_df,
                price_df=price_df,
                holding_period=hp,
                stop_loss=sl,
                cost=cost,
            )
            summary = summarize_trades(trades, return_col="net_return")
            records.append({
                "holding_period": hp,
                "stop_loss": sl,
                "trades": summary["trades"],
                "win_rate": summary["win_rate"],
                "profit_factor": summary["profit_factor"],
                "avg_return": summary["avg_return"],
            })
            
    return pd.DataFrame(records)

def run_cost_sensitivity(
    entries_df: pd.DataFrame,
    price_df: pd.DataFrame,
    holding_period: int = 20,
    stop_loss: float = -0.10,
    costs: list[float] | None = None,
) -> pd.DataFrame:
    """Sweeps over different transaction costs (e.g. 0.1% to 1.0%) to find break-even cost."""
    costs = costs or [0.0, 0.002, 0.004, 0.006, 0.008, 0.010]
    
    records = []
    for c in costs:
        trades = backtest_entries_with_fixed_stop(
            entries_df=entries_df,
            price_df=price_df,
            holding_period=holding_period,
            stop_loss=stop_loss,
            cost=c,
        )
        summary = summarize_trades(trades, return_col="net_return")
        records.append({
            "cost_pct": c,
            "trades": summary["trades"],
            "win_rate": summary["win_rate"],
            "profit_factor": summary["profit_factor"],
            "avg_return": summary["avg_return"],
        })
        
    return pd.DataFrame(records)

def run_risk_limit_sensitivity(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    risk_limits: list[float] | None = None,
) -> pd.DataFrame:
    """Evaluates how different maximum volatility limits impact the optimized portfolio's expected returns and risk."""
    risk_limits = risk_limits or [0.05, 0.08, 0.10, 0.12, 0.15]
    
    records = []
    for limit in risk_limits:
        weights = optimize_max_return_under_risk(
            expected_returns=expected_returns,
            covariance=covariance,
            max_volatility=limit,
            max_weight=0.25,
        )
        port_ret = float(weights.T @ expected_returns.to_numpy())
        port_vol = calculate_portfolio_volatility(weights, covariance, annualized=True)
        
        records.append({
            "risk_limit": limit,
            "expected_return": port_ret,
            "realized_volatility": port_vol,
            "sharpe_ratio": (port_ret - 0.03) / port_vol if port_vol > 0 else 0.0,
        })
        
    return pd.DataFrame(records)
