from __future__ import annotations

import pandas as pd


def attach_forward_returns(df: pd.DataFrame, horizons: list[int] | None = None) -> pd.DataFrame:
    if horizons is None:
        horizons = [5, 10, 20]
    out = df.sort_values(["symbol", "date"]).copy()
    for h in horizons:
        out[f"forward_return_{h}d"] = out.groupby("symbol")["close"].shift(-h) / out["close"] - 1
    return out


def attach_forward_returns_from_next_open(
    df: pd.DataFrame,
    horizons: list[int] | None = None,
    open_col: str = "open",
    close_col: str = "close",
) -> pd.DataFrame:
    """Forward returns with entry at the NEXT session's open (audit I4).

    A breakout confirmed by day-T's close cannot be bought at that close;
    close-based forward returns silently credit the overnight gap to the strategy.
    """
    if horizons is None:
        horizons = [5, 10, 20]
    out = df.sort_values(["symbol", "date"]).copy()
    next_open = out.groupby("symbol")[open_col].shift(-1)
    for h in horizons:
        future_close = out.groupby("symbol")[close_col].shift(-h)
        out[f"forward_return_open_{h}d"] = future_close / next_open - 1
    return out
