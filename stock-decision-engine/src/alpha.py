from __future__ import annotations

from typing import Any

import pandas as pd

from risk import ratios, rolling_capm


def alpha_snapshot(
    stock_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_annual: float = 0.0,
    trading_days: int = 252,
) -> dict[str, Any]:
    return ratios(stock_returns, benchmark_returns, risk_free_annual, trading_days)


def rolling_alpha_beta(stock_returns: pd.Series, benchmark_returns: pd.Series, window: int = 60, trading_days: int = 252) -> pd.DataFrame:
    return rolling_capm(stock_returns, benchmark_returns, window, trading_days)
