from __future__ import annotations

import pandas as pd


def value_at_risk(returns: pd.Series, level: float = 0.95) -> float:
    return float(returns.dropna().quantile(1 - level))


def conditional_value_at_risk(returns: pd.Series, level: float = 0.95) -> float:
    r = returns.dropna()
    var = r.quantile(1 - level)
    return float(r[r <= var].mean())


def position_size_by_risk(
    nav: float,
    entry: float,
    stop: float,
    risk_per_trade: float = 0.01,
    max_position_pct: float | None = None,
) -> dict:
    if nav <= 0:
        raise ValueError("nav must be positive")
    if entry <= 0:
        raise ValueError("entry must be positive")
    if max_position_pct is not None and max_position_pct <= 0:
        raise ValueError("max_position_pct must be positive when provided")

    risk_amount = nav * risk_per_trade
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        raise ValueError("entry and stop must be different")

    quantity = int(risk_amount // risk_per_share)
    max_position_value = None
    capped_by_max_position = False

    if max_position_pct is not None:
        max_position_value = nav * max_position_pct
        max_quantity = int(max_position_value // entry)
        if max_quantity < quantity:
            quantity = max_quantity
            capped_by_max_position = True

    position_value = quantity * entry
    return {
        "risk_amount": risk_amount,
        "risk_per_share": risk_per_share,
        "quantity": quantity,
        "position_value": position_value,
        "position_pct_nav": position_value / nav,
        "max_position_value": max_position_value,
        "capped_by_max_position": capped_by_max_position,
    }
