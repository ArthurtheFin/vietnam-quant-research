from __future__ import annotations

import pandas as pd

from src.backtest.simulator import summarize_trades_by_group

def classify_market_regime(
    price_df: pd.DataFrame,
    symbol_col: str = "symbol",
    date_col: str = "date",
    price_col: str = "close",
) -> pd.DataFrame:
    """Classifies market regimes into Uptrend, Downtrend, or Sideways based on simple MA crossovers."""
    out = price_df.sort_values([symbol_col, date_col]).copy()
    
    # Calculate simple indicators
    out["ma50"] = out.groupby(symbol_col)[price_col].transform(lambda s: s.rolling(50).mean())
    out["ma200"] = out.groupby(symbol_col)[price_col].transform(lambda s: s.rolling(200).mean())
    
    def get_regime(row):
        close = row[price_col]
        ma50 = row["ma50"]
        ma200 = row["ma200"]
        
        if pd.isna(ma50) or pd.isna(ma200):
            return "Unknown"
        if close > ma50 and ma50 > ma200:
            return "Uptrend"
        if close < ma50 and ma50 < ma200:
            return "Downtrend"
        return "Sideways"
        
    out["market_regime"] = out.apply(get_regime, axis=1)
    return out

def analyze_performance_by_regime(
    trades_df: pd.DataFrame,
    regime_col: str = "volatility_regime",
    return_col: str = "net_return",
) -> pd.DataFrame:
    """Aggregates backtest trade performance metrics grouped by market volatility or trend regime."""
    return summarize_trades_by_group(
        trades=trades_df,
        group_col=regime_col,
        return_col=return_col,
    )
