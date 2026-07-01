from __future__ import annotations

import pandas as pd


def add_breakout_signal(df: pd.DataFrame, lookback: int = 20, volume_z_col: str = "volume_zscore_20d", min_volume_z: float = 1.0) -> pd.DataFrame:
    out = df.sort_values(["symbol", "date"]).copy()
    prior_high = out.groupby("symbol")["high"].transform(lambda s: s.shift(1).rolling(lookback, min_periods=lookback//2).max())
    volume_ok = out[volume_z_col] >= min_volume_z if volume_z_col in out.columns else True
    
    # Enforce trend confirmation: close price must be above ma50 and ma200 if available
    trend_ok = True
    if "ma50" in out.columns:
        trend_ok = trend_ok & (out["close"] > out["ma50"])
    if "ma200" in out.columns:
        trend_ok = trend_ok & (out["close"] > out["ma200"])
        
    out[f"breakout_{lookback}d"] = (out["close"] > prior_high) & volume_ok & trend_ok
    return out



def add_pullback_ma_signal(df: pd.DataFrame, ma_col: str = "ma20", tolerance: float = 0.015) -> pd.DataFrame:
    out = df.copy()
    near_ma = (out["close"] / out[ma_col] - 1).abs() <= tolerance
    ma_long = out["ma50"] if "ma50" in out.columns else out[ma_col]
    ma_longer = out["ma200"] if "ma200" in out.columns else out[ma_col]
    trend_ok = ma_long >= ma_longer
    bullish_close = out["close"] >= (out["open"] if "open" in out.columns else out["close"])
    out[f"pullback_{ma_col}"] = near_ma & trend_ok & bullish_close
    return out


def add_volume_spike_signal(df: pd.DataFrame, z_col: str = "volume_zscore_20d", threshold: float = 2.0) -> pd.DataFrame:
    out = df.copy()
    out["volume_spike"] = out[z_col] >= threshold if z_col in out.columns else pd.Series(False, index=out.index)
    return out
