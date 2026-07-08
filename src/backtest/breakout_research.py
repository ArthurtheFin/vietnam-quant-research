from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.backtest.simulator import (
    backtest_entries_with_atr_stop,
    backtest_entries_with_fixed_stop,
    filter_non_overlapping_signals,
    summarize_trades,
    summarize_trades_by_group,
    sweep_atr_multiples,
    sweep_fixed_stop_losses,
)
from src.backtest.engine import attach_forward_returns_from_next_open
from src.features.returns import add_returns
from src.features.volatility import add_atr, add_realized_volatility, add_volatility_percentile, classify_volatility_regime


def ensure_breakout_features(
    df: pd.DataFrame,
    breakout_window: int = 20,
    forward_horizons: tuple[int, ...] = (5, 10, 20),
    atr_window: int = 14,
) -> pd.DataFrame:
    out = df.sort_values(["symbol", "date"]).copy()

    required_return_cols = [f"forward_return_{h}d" for h in forward_horizons] + ["return_1d", "log_return_1d"]
    if any(col not in out.columns for col in required_return_cols):
        out = add_returns(out, horizons=list(sorted(set(forward_horizons))))

    # I4: open-based forward returns (entry at next session's open) when open data exists
    open_cols = [f"forward_return_open_{h}d" for h in forward_horizons]
    if "open" in out.columns and any(col not in out.columns for col in open_cols):
        out = attach_forward_returns_from_next_open(out, horizons=list(sorted(set(forward_horizons))))

    rolling_high_col = f"rolling_high_{breakout_window}d"
    breakout_col = f"breakout_{breakout_window}d"
    if rolling_high_col not in out.columns:
        out[rolling_high_col] = (
            out.groupby("symbol")["close"]
            .transform(lambda s: s.shift(1).rolling(breakout_window).max())
        )
    if breakout_col not in out.columns:
        out[breakout_col] = out["close"] > out[rolling_high_col]

    atr_pct_col = f"atr_pct_{atr_window}"
    if atr_pct_col not in out.columns:
        out = add_atr(out, window=atr_window)

    if "realized_vol_20d" not in out.columns:
        out = add_realized_volatility(out, window=20)
    if "volatility_percentile" not in out.columns:
        out = add_volatility_percentile(out, vol_col="realized_vol_20d", window=252)
    if "volatility_regime" not in out.columns:
        out = classify_volatility_regime(out)

    return out


def build_non_overlap_entries(
    features: pd.DataFrame,
    signal_col: str = "breakout_20d",
    holding_period: int = 20,
    cost: float = 0.004,
) -> tuple[pd.DataFrame, dict]:
    entries = filter_non_overlapping_signals(features, signal_col=signal_col, holding_period=holding_period)
    # I4: prefer entry at next session's open; close-of-signal-bar entries are untradeable.
    open_return_col = f"forward_return_open_{holding_period}d"
    if open_return_col in entries.columns and entries[open_return_col].notna().any():
        forward_return_col = open_return_col
        entry_basis = "next_open"
    else:
        forward_return_col = f"forward_return_{holding_period}d"
        entry_basis = "signal_close (open column unavailable — same-bar bias present)"
    entries = entries.dropna(subset=[forward_return_col]).copy()
    entries[f"net_return_{holding_period}d"] = entries[forward_return_col] - cost

    baseline = entries.rename(columns={f"net_return_{holding_period}d": "net_return"})
    baseline_summary = summarize_trades(baseline, return_col="net_return")
    baseline_summary["entry_basis"] = entry_basis
    return entries, baseline_summary


def select_best_stop(summary: pd.DataFrame, min_trades: int = 50) -> pd.Series:
    candidate = summary.copy()
    if "trades" in candidate.columns:
        candidate = candidate[candidate["trades"] >= min_trades].copy()
    if candidate.empty:
        raise ValueError("No stop-loss candidate satisfies the minimum trade threshold")
    return candidate.sort_values(["profit_factor", "avg_return"], ascending=[False, False]).iloc[0]


def _select_best_stop_relaxed(summary: pd.DataFrame, thresholds: tuple[int, ...] = (50, 20, 5)) -> tuple[pd.Series, int]:
    """Select the best stop, relaxing the min-trade threshold on small samples.

    Returns (row, min_trades_used). The relaxation is recorded by the caller so
    thin evidence is visible instead of silently blocking the pipeline."""
    last_error: Exception | None = None
    for threshold in thresholds:
        try:
            return select_best_stop(summary, min_trades=threshold), threshold
        except ValueError as exc:
            last_error = exc
    raise last_error


def build_setup_eligibility(
    by_symbol: pd.DataFrame,
    setup_name: str = "breakout_20d",
    stop_loss: float = -0.10,
    holding_period: int = 20,
    cost_assumption: float = 0.004,
) -> pd.DataFrame:
    eligibility = by_symbol.copy()
    eligibility["setup_name"] = setup_name
    eligibility["stop_loss"] = stop_loss
    eligibility["holding_period"] = holding_period
    eligibility["cost_assumption"] = cost_assumption

    def classify_symbol_edge(row: pd.Series) -> str:
        trades = row.get("trades", 0)
        trades = 0.0 if pd.isna(trades) else float(trades)
        profit_factor = row.get("profit_factor", 0)
        profit_factor = 0.0 if pd.isna(profit_factor) else float(profit_factor)
        avg_return = row.get("avg_return", 0)
        avg_return = 0.0 if pd.isna(avg_return) else float(avg_return)
        median_return = row.get("median_return", 0)
        median_return = 0.0 if pd.isna(median_return) else float(median_return)

        strong_stats = profit_factor >= 2.0 and avg_return > 0 and median_return > 0
        valid_stats = profit_factor >= 1.5 and avg_return > 0
        conditional_stats = profit_factor >= 1.2 and avg_return > 0

        if trades < 5:
            return "Insufficient Data"
        if trades < 10:
            if strong_stats:
                return "Emerging Edge"
            if valid_stats:
                return "Conditional Edge"
            return "Insufficient Data"
        if trades < 15:
            if strong_stats:
                return "Valid Edge"
            if valid_stats:
                return "Emerging Edge"
            if conditional_stats:
                return "Conditional Edge"
            return "Avoid"
        if strong_stats:
            return "Strong Edge"
        if valid_stats:
            return "Valid Edge"
        if conditional_stats:
            return "Conditional Edge"
        return "Avoid"

    eligibility["edge_tier"] = eligibility.apply(classify_symbol_edge, axis=1)
    eligibility["eligible"] = eligibility["edge_tier"].isin(["Strong Edge", "Valid Edge"])
    eligibility["watchlist_eligible"] = eligibility["edge_tier"].isin(["Strong Edge", "Valid Edge", "Emerging Edge", "Conditional Edge"])
    cols = [
        "symbol",
        "setup_name",
        "trades",
        "win_rate",
        "avg_return",
        "median_return",
        "profit_factor",
        "stop_rate",
        "edge_tier",
        "eligible",
        "watchlist_eligible",
        "stop_loss",
        "holding_period",
        "cost_assumption",
    ]
    return eligibility[cols].sort_values(["watchlist_eligible", "eligible", "profit_factor"], ascending=[False, False, False]).reset_index(drop=True)


def build_volatility_rules(
    by_regime: pd.DataFrame,
    setup_name: str = "breakout_20d",
    stop_loss: float = -0.10,
    holding_period: int = 20,
) -> pd.DataFrame:
    vol_rule = by_regime.copy()
    vol_rule["setup_name"] = setup_name
    vol_rule["stop_loss"] = stop_loss
    vol_rule["holding_period"] = holding_period

    def classify_vol_rule(row: pd.Series) -> str:
        regime = row["volatility_regime"]
        if regime == "Unknown":
            return "Ignore"
        if regime == "Panic Vol":
            return "Avoid"
        if row["profit_factor"] >= 1.5 and row["avg_return"] > 0:
            return "Allowed"
        if row["profit_factor"] >= 1.2 and row["avg_return"] > 0:
            return "Conditional"
        return "Avoid"

    vol_rule["volatility_rule"] = vol_rule.apply(classify_vol_rule, axis=1)
    cols = [
        "volatility_regime",
        "setup_name",
        "trades",
        "win_rate",
        "avg_return",
        "median_return",
        "profit_factor",
        "stop_rate",
        "volatility_rule",
        "stop_loss",
        "holding_period",
    ]
    return vol_rule[cols].sort_values("profit_factor", ascending=False).reset_index(drop=True)


def clean_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = out[col].astype(str)
    return out


def run_breakout_research(
    features: pd.DataFrame,
    signal_col: str = "breakout_20d",
    holding_period: int = 20,
    cost: float = 0.004,
    stop_losses: list[float | None] | None = None,
    atr_multiples: list[float] | None = None,
    validation_split: float | None = 0.7,
    min_validation_trades: int = 50,
) -> dict[str, pd.DataFrame | dict | pd.Series]:
    stop_losses = stop_losses or [None, -0.05, -0.07, -0.10, -0.12]
    atr_multiples = atr_multiples or [1.5, 2.0, 2.5]

    prepared = ensure_breakout_features(features)
    entries, baseline_summary = build_non_overlap_entries(
        prepared,
        signal_col=signal_col,
        holding_period=holding_period,
        cost=cost,
    )

    # I3: select the stop on TRAIN entries only; report metrics on VALIDATION.
    # Selecting and reporting on the same sample overstates the edge.
    entries = entries.sort_values("date").reset_index(drop=True)
    entry_dates = pd.to_datetime(entries["date"]) if not entries.empty else pd.Series(dtype="datetime64[ns]")
    split_date = None
    if validation_split is not None and not entries.empty:
        candidate_split = entry_dates.quantile(validation_split)
        train_mask = entry_dates <= candidate_split
        if train_mask.any() and (~train_mask).any():
            split_date = candidate_split
    if split_date is not None:
        train_entries = entries[entry_dates <= split_date].copy()
        validation_entries = entries[entry_dates > split_date].copy()
    else:
        train_entries = entries.copy()
        validation_entries = entries.copy()

    fixed_stop_summary, trades_by_stop = sweep_fixed_stop_losses(
        entries_df=train_entries,
        price_df=prepared,
        stop_losses=stop_losses,
        holding_period=holding_period,
        cost=cost,
    )
    best_row, min_trades_used = _select_best_stop_relaxed(fixed_stop_summary)
    best_stop = None if best_row["stop_loss"] == "no_stop" else float(best_row["stop_loss"])

    # Evaluate the train-selected stop on held-out entries.
    validation_trades = backtest_entries_with_fixed_stop(
        entries_df=validation_entries,
        price_df=prepared,
        holding_period=holding_period,
        stop_loss=best_stop,
        cost=cost,
    )
    validated = split_date is not None and len(validation_trades) >= min_validation_trades
    best_trades = validation_trades.copy()
    by_symbol = summarize_trades_by_group(best_trades, group_col="symbol")
    by_regime = summarize_trades_by_group(best_trades, group_col="volatility_regime")

    atr_stop_summary, atr_trades_map = sweep_atr_multiples(
        entries_df=train_entries,
        price_df=prepared,
        atr_multiples=atr_multiples,
        atr_col="atr_pct_14",
        holding_period=holding_period,
        cost=cost,
    )

    eligibility = build_setup_eligibility(
        by_symbol,
        stop_loss=-0.10 if best_stop is None else best_stop,
        holding_period=holding_period,
        cost_assumption=cost,
    )
    vol_rule = build_volatility_rules(
        by_regime,
        stop_loss=-0.10 if best_stop is None else best_stop,
        holding_period=holding_period,
    )
    if not validated:
        # Fail loudly: thin or absent held-out evidence must not masquerade as edge.
        eligibility["edge_tier"] = "Unvalidated"
        eligibility["eligible"] = False
        eligibility["watchlist_eligible"] = False

    stop_selection = {
        "split_date": None if split_date is None else pd.Timestamp(split_date).date().isoformat(),
        "train_entries": int(len(train_entries)),
        "validation_entries": int(len(validation_entries)),
        "validation_trades": int(len(validation_trades)),
        "min_validation_trades": int(min_validation_trades),
        "validated": bool(validated),
        "selected_stop": best_stop,
        "selection_min_trades_used": int(min_trades_used),
        "selected_on": "train" if split_date is not None else "in_sample (degenerate timeline)",
    }

    return {
        "prepared_features": prepared,
        "non_overlap_entries": entries,
        "baseline_summary": baseline_summary,
        "fixed_stop_summary": fixed_stop_summary,
        "best_stop_row": best_row,
        "best_fixed_trades": best_trades,
        "by_symbol": by_symbol,
        "by_volatility_regime": by_regime,
        "atr_stop_summary": atr_stop_summary,
        "trades_by_stop": trades_by_stop,
        "atr_trades_map": atr_trades_map,
        "eligibility": eligibility,
        "volatility_rule": vol_rule,
        "stop_selection": stop_selection,
    }


def save_breakout_research_outputs(
    results: dict[str, pd.DataFrame | dict | pd.Series],
    out_dir: str = "data/signals",
    prefix: str = "breakout_20d",
) -> None:
    from src.data.loaders import save_parquet

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    mapping = {
        "non_overlap_entries": f"{prefix}_non_overlap.parquet",
        "fixed_stop_summary": f"{prefix}_fixed_stop_summary.parquet",
        "best_fixed_trades": f"{prefix}_best_fixed_stop_trades.parquet",
        "by_symbol": f"{prefix}_best_fixed_stop_by_symbol.parquet",
        "atr_stop_summary": f"{prefix}_atr_stop_summary.parquet",
        "by_volatility_regime": f"{prefix}_best_fixed_stop_by_vol_regime.parquet",
        "eligibility": f"{prefix}_setup_eligibility.parquet",
        "volatility_rule": f"{prefix}_volatility_rule.parquet",
    }

    for key, filename in mapping.items():
        value = results.get(key)
        if isinstance(value, pd.DataFrame):
            save_parquet(clean_for_parquet(value), Path(out_dir) / filename)

