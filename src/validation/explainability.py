from __future__ import annotations

import pandas as pd

def explain_selected_symbol(
    symbol: str,
    row: pd.Series,
) -> str:
    """Generates a detailed text explanation card of why a stock was selected on the watchlist."""
    name = str(symbol).upper()
    
    meta_score = row.get("meta_score", 50.0)
    trend_score = row.get("trend_score", 50.0)
    momentum_score = row.get("momentum_score", 50.0)
    rs_score = row.get("relative_strength_score", 50.0)
    vol_regime = row.get("volatility_regime", "Unknown")
    reason = row.get("reason", "N/A")
    warning = row.get("warning", "N/A")
    
    explanation = (
        f"Symbol: {name} (Meta Score: {meta_score:.2f})\n"
        f"  - Xu hướng (Trend Score): {trend_score:.2f}/100.0\n"
        f"  - Động lượng (Momentum Score): {momentum_score:.2f}/100.0\n"
        f"  - Sức mạnh giá so với VNINDEX (RS Score): {rs_score:.2f}/100.0\n"
        f"  - Trạng thái biến động: {vol_regime}\n"
        f"  - Lý do hệ thống chọn: {reason}\n"
        f"  - Cảnh báo đi kèm: {warning}"
    )
    return explanation

def generate_watchlist_explanation(
    watchlist_df: pd.DataFrame,
) -> list[str]:
    """Generates detailed text explanations for all items in the watchlist."""
    explanations = []
    for _, row in watchlist_df.iterrows():
        symbol = row.get("symbol")
        if pd.isna(symbol):
            continue
        explanations.append(explain_selected_symbol(str(symbol), row))
    return explanations
