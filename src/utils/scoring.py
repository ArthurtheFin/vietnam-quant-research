"""Shared scoring and utility functions used across screening, analytics, and reporting modules."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts. Override values take precedence."""
    merged: dict[str, Any] = {}
    for key in set(base) | set(override):
        base_value = base.get(key)
        override_value = override.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            merged[key] = deep_merge(base_value, override_value)
        elif key in override:
            merged[key] = override_value
        else:
            merged[key] = base_value
    return merged


def safe_divide(num: pd.Series, den: pd.Series) -> pd.Series:
    """Divide two Series, replacing zero denominators with NaN."""
    den = pd.to_numeric(den, errors="coerce").replace(0, np.nan)
    return pd.to_numeric(num, errors="coerce") / den


def clip_score(series: pd.Series, low: float, high: float, invert: bool = False) -> pd.Series:
    """Scale values from [low, high] to [0, 100]. Optionally invert."""
    if high <= low:
        raise ValueError("high must be greater than low")
    scaled = (series.astype(float) - low) / (high - low)
    scaled = scaled.clip(0, 1)
    if invert:
        scaled = 1 - scaled
    return scaled * 100


def bell_score(series: pd.Series, center: float, width: float) -> pd.Series:
    """Score based on distance from center. Max score at center, 0 at center ± width."""
    if width <= 0:
        raise ValueError("width must be positive")
    scaled = 1 - (series.astype(float) - center).abs() / width
    return scaled.clip(0, 1) * 100


def cross_sectional_score(df: pd.DataFrame, col: str, date_col: str = "date", higher_is_better: bool = True) -> pd.Series:
    """Rank values cross-sectionally (within each date) and scale to 0-100."""
    rank = df.groupby(date_col)[col].rank(pct=True, ascending=True)
    if higher_is_better:
        return (rank * 100).fillna(50.0)
    return ((1 - rank) * 100).fillna(50.0)


def regime_score(series: pd.Series, mapping: dict[str, float], default: float = 50.0) -> pd.Series:
    """Map categorical regime labels to numeric scores."""
    return series.astype(str).map(mapping).fillna(default).astype(float)


def to_bool(value) -> bool:
    """Convert various truthy representations to Python bool."""
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
