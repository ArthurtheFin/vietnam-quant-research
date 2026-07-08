"""Portfolio-level historical backtesting engine with periodic rebalancing and transaction costs."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.portfolio.construction import (
    equal_weight_allocation,
    hierarchical_risk_parity_allocation,
    inverse_volatility_allocation,
    shrink_covariance,
)
from src.backtest.simulator import _band_for_row, load_min_holding_sessions, load_price_bands
from src.portfolio.returns import estimate_expected_returns
from src.portfolio.risk import calculate_portfolio_volatility
from src.validation.metrics import calculate_cagr, calculate_max_drawdown, calculate_sharpe


def run_portfolio_backtest(
    features: pd.DataFrame,
    meta_ranking: pd.DataFrame,
    rebalance_period: int = 20,
    portfolio_size: int = 5,
    allocation_method: str = "equal_weight",
    transaction_cost_pct: float = 0.0015,
    initial_nav: float = 1_000_000_000.0,
    min_value_ma20: float = 10_000_000_000.0,
    require_above_ma200: bool = True,
    market_regime: pd.DataFrame | None = None,
    regime_col: str = "market_regime",
    risk_off_regimes: tuple[str, ...] = ("Risk-off",),
    regime_cash_fraction: float = 1.0,
    stop_loss_pct: float | None = None,
) -> dict[str, Any]:
    """
    Simulates a historical rebalancing portfolio backtest.
    Selects the top N stocks based on historical meta ranking score,
    applies liquidity and trend filters, rebalances weights, and tracks NAV.

    market_regime (optional): DataFrame with ["date", regime_col]. When
    provided, exposure is scaled down by regime_cash_fraction on days where
    the PRIOR session's regime is in risk_off_regimes (lagged 1 day -- the
    regime classifier uses same-day MA/breadth features, so using it same-day
    would be look-ahead bias, same class of bug as D1).

    stop_loss_pct (optional, e.g. -0.15): per-position stop-loss measured
    from the value at last entry/rebalance. Cannot trigger before
    load_min_holding_sessions() sessions have been held (T+2.5 settlement,
    same constraint as C2's simulator-level stops).
    """
    # 1. Prepare data
    df = features.sort_values(["symbol", "date"]).copy()
    df["date"] = pd.to_datetime(df["date"])

    # Get sorted unique timeline
    all_dates = sorted(df["date"].unique())
    if not all_dates:
        raise ValueError("Empty features date timeline")

    # Index features by symbol and date for fast lookup
    df_indexed = df.set_index(["symbol", "date"])

    # Load ranking scores
    ranking = meta_ranking.copy()
    ranking["date"] = pd.to_datetime(ranking["date"])
    ranking_indexed = ranking.set_index(["date", "symbol"])

    regime_by_date: pd.Series | None = None
    if market_regime is not None and not market_regime.empty and regime_col in market_regime.columns:
        reg = market_regime.copy()
        reg["date"] = pd.to_datetime(reg["date"])
        regime_by_date = reg.drop_duplicates(subset=["date"], keep="last").set_index("date")[regime_col]

    min_holding_sessions = load_min_holding_sessions()

    # 2. Rebalancing dates
    rebalance_dates = all_dates[::rebalance_period]
    if all_dates[-1] not in rebalance_dates:
        rebalance_dates.append(all_dates[-1])

    # State variables
    nav = initial_nav
    # symbol -> {"value": current position value, "entry_value": value at last
    # entry/rebalance, "entry_day_idx": day index of last entry/rebalance}
    current_holdings: dict[str, dict[str, float]] = {}
    equity_curve = []
    dates_list = []
    trades_log = []
    skipped_limit_up: list[dict] = []
    regime_adjustments: list[dict] = []
    stop_loss_exits: list[dict] = []
    price_bands, default_band = load_price_bands()

    # We loop day-by-day
    for day_idx, current_date in enumerate(all_dates):
        # A0. Regime-based exposure scaling (lagged 1 day -- decided on
        # yesterday's regime, applied before today's return).
        if regime_by_date is not None and current_holdings:
            lagged_date = all_dates[day_idx - 1] if day_idx > 0 else None
            lagged_regime = regime_by_date.get(lagged_date) if lagged_date is not None else None
            target_exposure = 1.0
            if lagged_regime in risk_off_regimes:
                target_exposure = 1.0 - regime_cash_fraction

            held_value = sum(pos["value"] for pos in current_holdings.values())
            current_exposure = held_value / nav if nav > 0 else 0.0
            if held_value > 0 and abs(current_exposure - target_exposure) > 1e-6:
                scale = target_exposure / current_exposure if current_exposure > 0 else 0.0
                turnover = abs(held_value - target_exposure * nav)
                nav -= turnover * transaction_cost_pct
                for sym, pos in current_holdings.items():
                    pos["value"] = pos["value"] * scale  # entry_value/entry_day_idx untouched
                regime_adjustments.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "lagged_regime": lagged_regime,
                    "target_exposure": target_exposure,
                    "turnover": turnover,
                })

        # A. Update holdings value based on daily returns
        if current_holdings:
            total_holdings_val = 0.0
            updated_holdings = {}
            for sym, pos in current_holdings.items():
                try:
                    # Get daily return
                    daily_ret = df_indexed.loc[(sym, current_date), "return_1d"]
                    if pd.isna(daily_ret):
                        daily_ret = 0.0
                except KeyError:
                    daily_ret = 0.0

                new_val = pos["value"] * (1.0 + daily_ret)
                updated_holdings[sym] = {**pos, "value": new_val}
                total_holdings_val += new_val

            # Cash remaining is NAV - previous total holdings value
            cash = nav - sum(pos["value"] for pos in current_holdings.values())
            nav = cash + total_holdings_val
            current_holdings = updated_holdings

            # A2. Stop-loss: per-position, measured from last entry/rebalance
            # value; cannot trigger before T+2.5 settlement (min_holding_sessions).
            if stop_loss_pct is not None:
                for sym in list(current_holdings.keys()):
                    pos = current_holdings[sym]
                    held_sessions = day_idx - pos["entry_day_idx"] + 1
                    if held_sessions < min_holding_sessions:
                        continue
                    entry_value = pos["entry_value"]
                    if entry_value <= 0:
                        continue
                    move = pos["value"] / entry_value - 1.0
                    if move <= stop_loss_pct:
                        exit_value = pos["value"]
                        nav -= exit_value * transaction_cost_pct
                        del current_holdings[sym]
                        stop_loss_exits.append({
                            "date": current_date.strftime("%Y-%m-%d"),
                            "symbol": sym,
                            "move_since_entry": move,
                            "exit_value": exit_value,
                        })
                        trades_log.append({
                            "date": current_date.strftime("%Y-%m-%d"),
                            "symbol": sym,
                            "type": "SELL",
                            "size_amount": exit_value,
                            "old_value": exit_value,
                            "new_value": 0.0,
                            "reason": "stop_loss",
                        })

        # B. Check if it is a rebalancing date
        # D1: decide with information available at the PRIOR session (T-1);
        # execution stays at the close of T. Same-bar selection was look-ahead.
        if current_date in rebalance_dates and 0 < day_idx < len(all_dates) - 1:
            decision_date = all_dates[day_idx - 1]
            # 1. Filter and select candidates as of the decision date
            try:
                scores_today = ranking_indexed.loc[decision_date].copy()
            except KeyError:
                scores_today = pd.DataFrame()

            try:
                features_today = df[df["date"] == decision_date].set_index("symbol")
            except Exception:
                features_today = pd.DataFrame()
                
            if scores_today.empty and not features_today.empty:
                # Dynamic scoring fallback: Momentum + Trend + Liquidity
                f_today = features_today.copy()
                
                ret20_col = f_today["return_20d"] if "return_20d" in f_today.columns else pd.Series(0.0, index=f_today.index)
                ret20 = pd.to_numeric(ret20_col, errors="coerce").fillna(0.0)
                
                ret60_col = f_today["return_60d"] if "return_60d" in f_today.columns else pd.Series(0.0, index=f_today.index)
                ret60 = pd.to_numeric(ret60_col, errors="coerce").fillna(0.0)
                
                mom_rank = (ret20.rank(pct=True) + ret60.rank(pct=True)) / 2.0
                
                val_col = "value_ma20" if "value_ma20" in f_today.columns else ("avg_value_20d" if "avg_value_20d" in f_today.columns else None)
                if val_col is not None:
                    val20 = f_today[val_col]
                else:
                    val20 = pd.Series(0.0, index=f_today.index)
                val20 = pd.to_numeric(val20, errors="coerce").fillna(0.0)
                liq_rank = val20.rank(pct=True)
                
                # Check trend
                if "above_ma50" in f_today.columns:
                    above50 = f_today["above_ma50"].astype(float)
                elif "ma50" in f_today.columns:
                    above50 = (f_today["close"] > f_today["ma50"]).astype(float)
                else:
                    above50 = pd.Series(1.0, index=f_today.index)
                    
                if "above_ma200" in f_today.columns:
                    above200 = f_today["above_ma200"].astype(float)
                elif "ma200" in f_today.columns:
                    above200 = (f_today["close"] > f_today["ma200"]).astype(float)
                else:
                    above200 = pd.Series(1.0, index=f_today.index)
                    
                trend_score = (above50 + above200) / 2.0
                
                f_today["meta_score"] = (mom_rank * 0.4 + trend_score * 0.4 + liq_rank * 0.2) * 100.0
                scores_today = f_today[["meta_score"]]
                
            if not scores_today.empty and not features_today.empty:
                merged = scores_today.merge(features_today, left_index=True, right_index=True, how="inner")
            else:
                merged = pd.DataFrame()
                
            # Filter candidates based on trend and liquidity
            if not merged.empty:
                # Strict trend check
                if require_above_ma200 and "above_ma200" in merged.columns:
                    merged = merged[merged["above_ma200"].astype(bool)]
                # Strict liquidity check
                if "value_ma20" in merged.columns:
                    merged = merged[merged["value_ma20"].fillna(0) >= min_value_ma20]
                elif "avg_value_20d" in merged.columns:
                    merged = merged[merged["avg_value_20d"].fillna(0) >= min_value_ma20]
                    
                # Rank candidates by final score or meta score
                score_col = "final_score" if "final_score" in merged.columns else "meta_score"
                if score_col in merged.columns:
                    merged = merged.sort_values(score_col, ascending=False)

                selected_symbols = merged.head(portfolio_size).index.tolist()
            else:
                selected_symbols = []

            # D2: cannot buy a symbol that is limit-up on the execution day.
            if selected_symbols:
                exec_day = df[df["date"] == current_date].set_index("symbol")
                tradable = []
                for sym in selected_symbols:
                    if sym in exec_day.index:
                        row = exec_day.loc[sym]
                        r1 = row.get("return_1d")
                        band = _band_for_row(row, price_bands, default_band)
                        if pd.notna(r1) and float(r1) >= band * 0.98:
                            skipped_limit_up.append({"date": current_date.strftime("%Y-%m-%d"), "symbol": sym})
                            continue
                    tradable.append(sym)
                selected_symbols = tradable
                
            # 2. Calculate new weights for selected symbols
            new_weights = pd.Series(0.0, index=symbols_universe(df))
            if selected_symbols:
                if allocation_method == "equal_weight":
                    new_weights[selected_symbols] = 1.0 / len(selected_symbols)
                elif allocation_method == "inverse_vol" and "atr_pct_14" in merged.columns:
                    vols = merged.loc[selected_symbols, "atr_pct_14"].fillna(0.05)
                    inv_vols = 1.0 / vols.replace(0, np.nan)
                    new_weights[selected_symbols] = inv_vols / inv_vols.sum()
                else:
                    # Fallback to equal weight
                    new_weights[selected_symbols] = 1.0 / len(selected_symbols)

            # Regime-scaled target exposure at this rebalance (same lag rule as A0).
            rebalance_exposure = 1.0
            if regime_by_date is not None:
                lagged_regime_rb = regime_by_date.get(decision_date)
                if lagged_regime_rb in risk_off_regimes:
                    rebalance_exposure = 1.0 - regime_cash_fraction

            # 3. Rebalance portfolio and apply transaction costs
            # First, estimate target positions using current nav
            estimated_target = {}
            for sym in selected_symbols:
                w = new_weights[sym]
                estimated_target[sym] = nav * w * rebalance_exposure

            # Compute trade sizes and costs
            all_traded_symbols = set(current_holdings.keys()) | set(selected_symbols)
            total_turnover = 0.0

            for sym in all_traded_symbols:
                old_val = current_holdings.get(sym, {}).get("value", 0.0)
                new_val = estimated_target.get(sym, 0.0)
                trade_size = abs(new_val - old_val)
                total_turnover += trade_size

                if trade_size > 1.0:
                    trades_log.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "symbol": sym,
                        "type": "BUY" if new_val > old_val else "SELL",
                        "size_amount": trade_size,
                        "old_value": old_val,
                        "new_value": new_val,
                    })

            # Apply transaction costs to NAV
            tc_cost = total_turnover * transaction_cost_pct
            nav -= tc_cost

            # Set target holdings scaled to the new NAV; reset entry reference
            # for every selected symbol (a rebalance resize is treated as a
            # fresh entry for stop-loss purposes).
            target_holdings: dict[str, dict[str, float]] = {}
            for sym in selected_symbols:
                w = new_weights[sym]
                value = nav * w * rebalance_exposure
                target_holdings[sym] = {"value": value, "entry_value": value, "entry_day_idx": day_idx}

            current_holdings = target_holdings
            
        # C. Record daily equity value
        equity_curve.append(nav)
        dates_list.append(current_date)
        
    # 3. Package results
    equity_series = pd.Series(equity_curve, index=dates_list, name="portfolio_nav")
    pct_returns = equity_series.pct_change().fillna(0.0)
    
    # Calculate performance metrics
    cagr = calculate_cagr(equity_series)
    max_dd = calculate_max_drawdown(equity_series)
    sharpe = calculate_sharpe(pct_returns, risk_free_rate=0.03)
    
    # Benchmark comparison
    benchmark_source = "VNINDEX"
    try:
        # Try to calculate benchmark returns
        bench_df = df[df["symbol"] == "VNINDEX"].sort_values("date")
        if bench_df.empty:
            # Fallback to first stock in features
            bench_df = df[df["symbol"] == df["symbol"].iloc[0]].sort_values("date")
            benchmark_source = bench_df["symbol"].iloc[0]
            
        bench_df = bench_df[bench_df["date"].isin(dates_list)].set_index("date")
        bench_nav = (1.0 + bench_df["return_1d"].fillna(0.0)).cumprod() * initial_nav
        bench_nav = bench_nav.reindex(dates_list).ffill().fillna(initial_nav)
    except Exception:
        bench_nav = pd.Series(initial_nav, index=dates_list)
        
    return {
        "equity_curve": equity_series,
        "portfolio_returns": pct_returns,
        "benchmark_curve": bench_nav,
        "benchmark_symbol": benchmark_source,
        "trades_log": pd.DataFrame(trades_log),
        "skipped_limit_up": pd.DataFrame(skipped_limit_up),
        "regime_adjustments": pd.DataFrame(regime_adjustments),
        "stop_loss_exits": pd.DataFrame(stop_loss_exits),
        "metrics": {
            "initial_nav": initial_nav,
            "final_nav": nav,
            "cagr": cagr,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
            "total_trades": len(trades_log),
            "stop_loss_exit_count": len(stop_loss_exits),
            "regime_adjustment_count": len(regime_adjustments),
        }
    }


def symbols_universe(df: pd.DataFrame) -> list[str]:
    """Helper to get list of all unique symbols in the dataset."""
    return df["symbol"].dropna().unique().tolist()
