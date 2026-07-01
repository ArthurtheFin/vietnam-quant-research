from __future__ import annotations

import numpy as np
import pandas as pd


def add_returns(df: pd.DataFrame, horizons: list[int] = [1, 5, 10, 20], price_col: str = "close") -> pd.DataFrame:
    out = df.sort_values(["symbol", "date"]).copy()
    
    from src.utils.math_utils import safe_log_ratio
    
    # Check for positive prices to avoid division by zero/negative logs
    valid_prices = out[price_col].where(out[price_col] > 0.0)
    
    # Calculate daily return and clip to [-0.15, 0.15] to neutralize splits/anomalies
    daily_ret = valid_prices.groupby(out["symbol"]).pct_change(1, fill_method=None)
    out["return_1d"] = daily_ret.clip(-0.15, 0.15)
    
    for h in horizons:
        if h == 1:
            continue
        # Compound clipped daily returns to calculate multi-day returns
        out[f"return_{h}d"] = out.groupby("symbol")["return_1d"].transform(
            lambda s: (1.0 + s).rolling(h).apply(np.prod, raw=True) - 1.0
        )
        # Shift forward returns
        out[f"forward_return_{h}d"] = out.groupby("symbol")["return_1d"].transform(
            lambda s: (1.0 + s.shift(-h)).rolling(h).apply(np.prod, raw=True) - 1.0
        )
        
    out["log_return_1d"] = safe_log_ratio(out[price_col], out.groupby("symbol")[price_col].shift(1))
    return out
