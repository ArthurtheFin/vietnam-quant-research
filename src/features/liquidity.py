from __future__ import annotations

import pandas as pd


def add_liquidity_features(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    out = df.sort_values(["symbol", "date"]).copy()
    for col in ["volume", "value"]:
        if col in out.columns:
            mean = out.groupby("symbol")[col].transform(lambda s: s.rolling(window, min_periods=5).mean())
            std = out.groupby("symbol")[col].transform(lambda s: s.rolling(window, min_periods=5).std())
            out[f"{col}_ma{window}"] = mean
            out[f"{col}_zscore_{window}d"] = (out[col] - mean) / std
    return out
