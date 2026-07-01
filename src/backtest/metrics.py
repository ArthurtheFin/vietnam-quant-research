from __future__ import annotations

import numpy as np
import pandas as pd


def summarize_signal_performance(df: pd.DataFrame, signal_col: str, forward_return_cols: list[str]) -> pd.DataFrame:
    rows = []
    signal_df = df[df[signal_col] == True].copy()
    for col in forward_return_cols:
        s = signal_df[col].dropna()
        if s.empty:
            continue
        rows.append({
            "signal": signal_col,
            "horizon": col,
            "trades": len(s),
            "win_rate": (s > 0).mean(),
            "avg_return": s.mean(),
            "median_return": s.median(),
            "best_return": s.max(),
            "worst_return": s.min(),
            "profit_factor": s[s > 0].sum() / abs(s[s < 0].sum()) if abs(s[s < 0].sum()) > 0 else np.inf,
        })
    return pd.DataFrame(rows)


def expected_value(p_win: float, avg_gain: float, avg_loss: float) -> float:
    return p_win * avg_gain - (1 - p_win) * abs(avg_loss)
