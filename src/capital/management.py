from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.risk_model import position_size_by_risk


def conviction_multiplier(score: float, min_multiplier: float = 0.50, max_multiplier: float = 1.50, max_score: float = 100.0) -> float:
    score = float(np.clip(score, 0, max_score))
    return float(min_multiplier + (max_multiplier - min_multiplier) * score / max_score)


def resolve_conviction_score(
    row: pd.Series | dict,
    conviction_col: str = "trade_edge_score",
    setup_quality_col: str = "setup_quality_score",
    edge_tier_col: str = "edge_tier",
    win_rate_col: str = "win_rate",
    profit_factor_col: str = "profit_factor",
) -> float:
    row = row if isinstance(row, pd.Series) else pd.Series(row)

    conviction_value = row.get(conviction_col)
    if pd.notna(conviction_value) and float(conviction_value) > 0:
        return float(np.clip(float(conviction_value), 0, 100))

    edge_tier_map = {
        "Strong Edge": 85.0,
        "Valid Edge": 70.0,
        "Emerging Edge": 62.0,
        "Conditional Edge": 55.0,
        "Avoid": 25.0,
    }

    components: list[float] = []
    weights: list[float] = []

    setup_quality = row.get(setup_quality_col)
    if pd.notna(setup_quality):
        components.append(float(np.clip(float(setup_quality), 0, 100)))
        weights.append(0.45)

    edge_tier = row.get(edge_tier_col)
    if pd.notna(edge_tier):
        components.append(edge_tier_map.get(str(edge_tier), 40.0))
        weights.append(0.30)

    win_rate = row.get(win_rate_col)
    if pd.notna(win_rate):
        win_rate_score = np.interp(float(win_rate), [0.45, 0.70], [20.0, 90.0])
        components.append(float(np.clip(win_rate_score, 0, 100)))
        weights.append(0.15)

    profit_factor = row.get(profit_factor_col)
    if pd.notna(profit_factor):
        profit_factor_score = np.interp(float(profit_factor), [0.80, 3.00], [20.0, 95.0])
        components.append(float(np.clip(profit_factor_score, 0, 100)))
        weights.append(0.10)

    if not components:
        return 50.0

    return float(np.average(components, weights=weights))


def regime_multiplier(regime: str, mapping: dict[str, float] | None = None) -> float:
    mapping = mapping or {
        "Risk-on": 1.00,
        "Neutral": 0.75,
        "Risk-off": 0.25,
        "Low Vol": 1.00,
        "Normal Vol": 0.85,
        "High Vol": 0.70,
        "Stress Vol": 0.50,
        "Panic Vol": 0.25,
        "Unknown": 0.60,
    }
    return float(mapping.get(str(regime), mapping.get("Unknown", 0.60)))


def fractional_kelly_fraction(
    p_win: float,
    avg_gain: float,
    avg_loss: float,
    kelly_fraction: float = 0.50,
    max_risk_fraction: float = 0.03,
) -> float:
    if avg_loss <= 0 or avg_gain <= 0:
        return 0.0
    b = avg_gain / avg_loss
    raw_kelly = (p_win * (b + 1) - 1) / b
    scaled = max(0.0, raw_kelly) * kelly_fraction
    return float(min(scaled, max_risk_fraction))


def kelly_scale(
    kelly_risk: float | None,
    base_risk_per_trade: float,
    min_scale: float = 0.50,
    max_scale: float = 1.50,
) -> float:
    if kelly_risk is None or not np.isfinite(kelly_risk) or kelly_risk <= 0 or base_risk_per_trade <= 0:
        return 1.0
    raw_scale = float(kelly_risk) / float(base_risk_per_trade)
    return float(np.clip(raw_scale, min_scale, max_scale))


def atr_based_position_plan(
    nav: float,
    entry: float,
    atr_pct: float,
    atr_multiple: float = 2.0,
    base_risk_per_trade: float = 0.01,
    max_position_pct: float = 0.25,
    conviction_score: float | None = None,
    regime: str | None = None,
    kelly_fraction: float | None = None,
    min_total_risk_pct: float = 0.0025,
    max_total_risk_pct: float = 0.02,
    min_kelly_scale: float = 0.50,
    max_kelly_scale: float = 1.50,
) -> dict[str, float]:
    if atr_pct <= 0:
        raise ValueError("atr_pct must be positive")

    conviction_mult = conviction_multiplier(conviction_score) if conviction_score is not None else 1.0
    regime_mult = regime_multiplier(regime or "Unknown")
    base_risk_budget = base_risk_per_trade * conviction_mult * regime_mult
    kelly_overlay = kelly_scale(
        kelly_risk=kelly_fraction,
        base_risk_per_trade=base_risk_per_trade,
        min_scale=min_kelly_scale,
        max_scale=max_kelly_scale,
    )
    risk_pct = float(np.clip(base_risk_budget * kelly_overlay, min_total_risk_pct, max_total_risk_pct))

    stop_price = entry * (1 - atr_pct * atr_multiple)
    sizing = position_size_by_risk(
        nav=nav,
        entry=entry,
        stop=stop_price,
        risk_per_trade=risk_pct,
        max_position_pct=max_position_pct,
    )
    sizing.update(
        {
            "stop_price": stop_price,
            "atr_pct": atr_pct,
            "atr_multiple": atr_multiple,
            "risk_pct_effective": risk_pct,
            "conviction_multiplier": conviction_mult,
            "regime_multiplier": regime_mult,
            "base_risk_budget": base_risk_budget,
            "kelly_fraction": 0.0 if kelly_fraction is None else float(kelly_fraction),
            "kelly_scale": kelly_overlay,
        }
    )
    return sizing


def allocate_capital_budget(
    plan: pd.DataFrame,
    nav: float,
    max_gross_exposure: float = 1.0,
) -> pd.DataFrame:
    if plan.empty:
        return plan.copy()
    if max_gross_exposure <= 0:
        raise ValueError("max_gross_exposure must be positive")

    budget_remaining = float(nav) * float(max_gross_exposure)
    adjusted_rows = []

    for _, row in plan.iterrows():
        entry_price = float(row["entry_price"])
        desired_quantity = int(row["quantity"])
        affordable_quantity = int(budget_remaining // entry_price) if entry_price > 0 else 0
        final_quantity = max(0, min(desired_quantity, affordable_quantity))
        position_value = final_quantity * entry_price
        realized_risk = final_quantity * float(row["risk_per_share"])
        budget_remaining -= position_value

        updated = row.copy()
        updated["quantity"] = final_quantity
        updated["position_value"] = position_value
        updated["position_pct_nav"] = position_value / nav if nav > 0 else 0.0
        updated["risk_amount_realized"] = realized_risk
        updated["gross_budget_remaining"] = max(budget_remaining, 0.0)
        adjusted_rows.append(updated)

    adjusted_plan = pd.DataFrame(adjusted_rows)
    adjusted_plan = adjusted_plan[adjusted_plan["quantity"] > 0].reset_index(drop=True)
    return adjusted_plan


def align_capital_plan_to_target_weights(
    plan: pd.DataFrame,
    target_weights: pd.Series,
    nav: float,
    max_gross_exposure: float = 1.0,
    symbol_col: str = "symbol",
    entry_col: str = "entry_price",
    value_col: str = "position_value",
) -> pd.DataFrame:
    if plan.empty:
        return plan.copy()
    if target_weights is None or len(target_weights) == 0:
        raise ValueError("target_weights must contain at least one symbol")
    if max_gross_exposure <= 0:
        raise ValueError("max_gross_exposure must be positive")

    weights = pd.Series(target_weights, dtype=float).fillna(0.0)
    weights = weights[weights > 0]
    if weights.empty:
        raise ValueError("target_weights must contain positive weights")
    weights = weights / float(weights.sum())

    gross_budget = float(nav) * float(max_gross_exposure)
    aligned = plan.copy()
    aligned = aligned[aligned[symbol_col].isin(weights.index)].copy()
    if aligned.empty:
        return aligned

    aligned["target_weight"] = aligned[symbol_col].map(weights).fillna(0.0)
    aligned["target_position_value"] = aligned["target_weight"] * gross_budget
    aligned["risk_cap_position_value"] = pd.to_numeric(aligned[value_col], errors="coerce").fillna(0.0)
    aligned["final_position_value_pre_round"] = np.minimum(
        aligned["target_position_value"],
        aligned["risk_cap_position_value"],
    )
    aligned["quantity"] = np.floor(
        aligned["final_position_value_pre_round"] / pd.to_numeric(aligned[entry_col], errors="coerce").replace(0, np.nan)
    ).fillna(0).astype(int)
    aligned["position_value"] = aligned["quantity"] * pd.to_numeric(aligned[entry_col], errors="coerce").fillna(0.0)
    aligned["position_pct_nav"] = aligned["position_value"] / nav if nav > 0 else 0.0
    aligned["risk_amount_realized"] = aligned["quantity"] * pd.to_numeric(aligned["risk_per_share"], errors="coerce").fillna(0.0)
    aligned = aligned[aligned["quantity"] > 0].copy()
    aligned = aligned.sort_values(["target_weight", "conviction_score_resolved", "position_value"], ascending=False).reset_index(drop=True)

    final_gross = float(aligned["position_value"].sum())
    aligned["gross_weight"] = aligned["position_value"] / final_gross if final_gross > 0 else 0.0
    aligned["weight_gap"] = aligned["gross_weight"] - aligned["target_weight"]
    aligned["capital_rank"] = np.arange(1, len(aligned) + 1)
    return aligned


def build_capital_plan(
    candidates: pd.DataFrame,
    nav: float,
    entry_col: str = "close",
    atr_pct_col: str = "atr_pct_14",
    conviction_col: str = "trade_edge_score",
    regime_col: str = "volatility_regime",
    p_win_col: str | None = None,
    avg_gain_col: str | None = None,
    avg_loss_col: str | None = None,
    base_risk_per_trade: float = 0.01,
    atr_multiple: float = 2.0,
    max_position_pct: float = 0.25,
    kelly_fraction: float = 0.50,
    min_total_risk_pct: float = 0.0025,
    max_total_risk_pct: float = 0.02,
    min_kelly_scale: float = 0.50,
    max_kelly_scale: float = 1.50,
    max_gross_exposure: float = 1.0,
) -> pd.DataFrame:
    rows = []
    for _, row in candidates.iterrows():
        entry = row.get(entry_col)
        atr_pct = row.get(atr_pct_col)
        if pd.isna(entry) or pd.isna(atr_pct) or entry <= 0 or atr_pct <= 0:
            continue

        kelly_risk = None
        kelly_note = None
        if p_win_col and avg_gain_col and avg_loss_col:
            p_win = row.get(p_win_col)
            avg_gain = row.get(avg_gain_col)
            avg_loss = row.get(avg_loss_col)
            if pd.notna(p_win) and pd.notna(avg_gain) and pd.notna(avg_loss):
                # avg_loss must be a genuine loss statistic (negative return);
                # abs() of an arbitrary positive stat silently corrupts Kelly.
                if float(avg_loss) >= 0:
                    kelly_note = (
                        f"Kelly disabled: {avg_loss_col} is non-negative "
                        f"({float(avg_loss):.4f}) — not a loss statistic"
                    )
                elif float(avg_gain) <= 0:
                    kelly_note = f"Kelly disabled: {avg_gain_col} is non-positive"
                else:
                    raw_kelly_risk = fractional_kelly_fraction(
                        p_win=float(p_win),
                        avg_gain=float(avg_gain),
                        avg_loss=abs(float(avg_loss)),
                        kelly_fraction=kelly_fraction,
                    )
                    if raw_kelly_risk > 0:
                        kelly_risk = raw_kelly_risk

        resolved_conviction = resolve_conviction_score(row, conviction_col=conviction_col)

        sizing = atr_based_position_plan(
            nav=nav,
            entry=float(entry),
            atr_pct=float(atr_pct),
            atr_multiple=atr_multiple,
            base_risk_per_trade=base_risk_per_trade,
            max_position_pct=max_position_pct,
            conviction_score=resolved_conviction,
            regime=row.get(regime_col),
            kelly_fraction=kelly_risk,
            min_total_risk_pct=min_total_risk_pct,
            max_total_risk_pct=max_total_risk_pct,
            min_kelly_scale=min_kelly_scale,
            max_kelly_scale=max_kelly_scale,
        )
        rows.append(
            {
                "symbol": row.get("symbol"),
                "entry_price": float(entry),
                "trade_edge_score": row.get(conviction_col),
                "conviction_score_resolved": resolved_conviction,
                "edge_tier": row.get("edge_tier"),
                "volatility_regime": row.get(regime_col),
                "kelly_note": kelly_note,
                **sizing,
            }
        )
    if not rows:
        return pd.DataFrame()

    plan = pd.DataFrame(rows).sort_values(
        ["conviction_score_resolved", "kelly_scale", "position_value", "risk_amount"],
        ascending=False,
    ).reset_index(drop=True)
    plan["risk_budget_amount"] = plan["risk_amount"]
    plan["risk_amount_realized"] = plan["quantity"] * plan["risk_per_share"]
    plan = allocate_capital_budget(plan, nav=nav, max_gross_exposure=max_gross_exposure)
    gross_capital = float(plan["position_value"].sum())
    plan["gross_weight"] = plan["position_value"] / gross_capital if gross_capital > 0 else 0.0
    plan["capital_rank"] = np.arange(1, len(plan) + 1)
    return plan
