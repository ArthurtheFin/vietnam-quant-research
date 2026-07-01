from __future__ import annotations

import pandas as pd


def add_moving_averages(df: pd.DataFrame, windows: list[int] = [20, 50, 200], price_col: str = "close") -> pd.DataFrame:
    out = df.sort_values(["symbol", "date"]).copy()
    for w in windows:
        ma = out.groupby("symbol")[price_col].transform(lambda s: s.rolling(w, min_periods=max(2, w // 3)).mean())
        out[f"ma{w}"] = ma
        out[f"distance_ma{w}"] = out[price_col] / ma - 1
        out[f"above_ma{w}"] = out[price_col] > ma
    return out


def add_relative_strength(df: pd.DataFrame, benchmark_symbol: str = "VNINDEX", horizon: int = 20, price_col: str = "close") -> pd.DataFrame:
    out = df.sort_values(["symbol", "date"]).copy()
    out[f"return_{horizon}d"] = out.groupby("symbol")[price_col].pct_change(horizon)
    bench = out[out["symbol"].str.upper() == benchmark_symbol.upper()][["date", f"return_{horizon}d"]]
    bench = bench.rename(columns={f"return_{horizon}d": f"benchmark_return_{horizon}d"})
    out = out.merge(bench, on="date", how="left")
    out[f"relative_strength_{horizon}d"] = out[f"return_{horizon}d"] - out[f"benchmark_return_{horizon}d"]
    return out
