from src.validation.bias_checks import check_lookahead_bias, check_data_leakage, check_survivorship_bias
from src.validation.robustness import run_parameter_sensitivity, run_cost_sensitivity, run_risk_limit_sensitivity
from src.validation.regime import classify_market_regime, analyze_performance_by_regime
from src.validation.metrics import (
    calculate_cagr,
    calculate_sharpe,
    calculate_sortino,
    calculate_calmar,
    calculate_max_drawdown,
    calculate_turnover,
    calculate_time_under_water,
)
from src.validation.stress_test import run_market_drawdown_stress, run_correlation_shock, run_volatility_shock
from src.validation.explainability import explain_selected_symbol, generate_watchlist_explanation
