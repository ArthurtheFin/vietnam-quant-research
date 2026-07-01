from __future__ import annotations

import numpy as np
import pandas as pd


def add_rolling_distribution_stats(df: pd.DataFrame, return_col: str = "return_1d", window: int = 60) -> pd.DataFrame:
    out = df.sort_values(["symbol", "date"]).copy()
    grp = out.groupby("symbol")[return_col]
    out[f"dist_mean_{window}d"] = grp.transform(lambda s: s.rolling(window, min_periods=20).mean())
    out[f"dist_median_{window}d"] = grp.transform(lambda s: s.rolling(window, min_periods=20).median())
    out[f"dist_skew_{window}d"] = grp.transform(lambda s: s.rolling(window, min_periods=20).skew())
    out[f"dist_kurt_{window}d"] = grp.transform(lambda s: s.rolling(window, min_periods=20).kurt())
    out[f"dist_q05_{window}d"] = grp.transform(lambda s: s.rolling(window, min_periods=20).quantile(0.05))
    out[f"dist_q95_{window}d"] = grp.transform(lambda s: s.rolling(window, min_periods=20).quantile(0.95))
    q05_abs = out[f"dist_q05_{window}d"].abs().replace(0, np.nan)
    out[f"tail_ratio_{window}d"] = out[f"dist_q95_{window}d"].abs() / q05_abs
    return out
