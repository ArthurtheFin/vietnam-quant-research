from __future__ import annotations

import pandas as pd


def _resolve_volatility_percentile(row: pd.Series) -> float | None:
    for col in ("volatility_percentile", "realized_vol_20d_percentile", "ewma_vol_20d_percentile"):
        value = row.get(col, None)
        if pd.notna(value):
            return value
    return None


def classify_market_regime(row: pd.Series) -> str:
    score = 0
    if row.get("index_above_ma50", False):
        score += 1
    if row.get("index_above_ma200", False):
        score += 1
    if row.get("pct_above_ma50", 0) >= 0.55:
        score += 1
    if row.get("advance_decline_ratio", 0) >= 1.2:
        score += 1
    vol_pct = _resolve_volatility_percentile(row)
    if pd.notna(vol_pct) and vol_pct < 0.8:
        score += 1
    if score >= 4:
        return "Risk-on"
    if score >= 2:
        return "Neutral"
    return "Risk-off"


def add_market_regime(market_features: pd.DataFrame) -> pd.DataFrame:
    out = market_features.copy()
    out["market_regime"] = out.apply(classify_market_regime, axis=1)
    return out
