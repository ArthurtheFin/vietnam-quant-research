from __future__ import annotations

import pandas as pd


def calculate_market_breadth(features: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Aggregate stock-level features into daily breadth indicators."""
    df = features.copy()
    metrics = []
    for date, g in df.groupby(date_col):
        row = {"date": date, "stock_count": len(g)}
        for w in [20, 50, 200]:
            col = f"above_ma{w}"
            if col in g.columns:
                row[f"pct_above_ma{w}"] = g[col].mean()
        if "return_1d" in g.columns:
            row["advance_count"] = int((g["return_1d"] > 0).sum())
            row["decline_count"] = int((g["return_1d"] < 0).sum())
            row["advance_decline_ratio"] = row["advance_count"] / max(row["decline_count"], 1)
        if "volume" in g.columns and "return_1d" in g.columns:
            up_vol = g.loc[g["return_1d"] > 0, "volume"].sum()
            down_vol = g.loc[g["return_1d"] < 0, "volume"].sum()
            row["up_down_volume_ratio"] = up_vol / max(down_vol, 1)
        metrics.append(row)
    return pd.DataFrame(metrics).sort_values("date")
