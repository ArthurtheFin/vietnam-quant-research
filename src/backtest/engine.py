from __future__ import annotations

import pandas as pd


def attach_forward_returns(df: pd.DataFrame, horizons: list[int] | None = None) -> pd.DataFrame:
    if horizons is None:
        horizons = [5, 10, 20]
    out = df.sort_values(["symbol", "date"]).copy()
    for h in horizons:
        out[f"forward_return_{h}d"] = out.groupby("symbol")["close"].shift(-h) / out["close"] - 1
    return out
