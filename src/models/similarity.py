from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import pairwise_distances


def find_similar_states(
    df: pd.DataFrame,
    current_row: pd.Series,
    feature_cols: list[str],
    top_n: int = 50,
    date_col: str = "date",
) -> pd.DataFrame:
    history = df.dropna(subset=feature_cols).copy()

    if date_col in history.columns and date_col in current_row.index and pd.notna(current_row[date_col]):
        current_date = pd.to_datetime(current_row[date_col])
        history = history[pd.to_datetime(history[date_col]) < current_date]

    if {"symbol", date_col}.issubset(history.columns) and {"symbol", date_col}.issubset(current_row.index):
        history = history[
            ~(
                history["symbol"].astype(str).eq(str(current_row["symbol"]))
                & pd.to_datetime(history[date_col]).eq(pd.to_datetime(current_row[date_col]))
            )
        ]

    if history.empty:
        return history

    current_features = current_row[feature_cols]
    if current_features.isna().any():
        raise ValueError("current_row must have non-null values for all feature_cols")

    X = history[feature_cols].astype(float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    current = pd.DataFrame([current_features.astype(float).to_dict()])
    current_scaled = scaler.transform(current)
    distances = pairwise_distances(X_scaled, current_scaled).ravel()
    history["similarity_distance"] = distances
    return history.sort_values("similarity_distance").head(top_n)


def summarize_forward_returns(similar_states: pd.DataFrame, forward_return_col: str = "forward_return_10d") -> dict:
    s = similar_states[forward_return_col].dropna()
    if s.empty:
        return {}
    return {
        "sample_size": int(len(s)),
        "p_positive": float((s > 0).mean()),
        "mean_forward_return": float(s.mean()),
        "median_forward_return": float(s.median()),
        "worst_10pct": float(s.quantile(0.10)),
        "best_10pct": float(s.quantile(0.90)),
    }
