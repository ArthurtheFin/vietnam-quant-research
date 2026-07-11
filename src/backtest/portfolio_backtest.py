"""Portfolio-level historical backtesting engine with periodic rebalancing and transaction costs."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.analytics.reversal_quality_score import score_reversal_quality
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
    portfolio_size: int = 10,
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
    take_profit_pct: float | None = None,
    trend_break_col: str = "above_ma20",
    benchmark_features: pd.DataFrame | None = None,
    max_per_sector: int | None = 2,
    sector_map: dict[str, str] | None = None,
    giveback_arm_gain: float | None = None,
    giveback_trigger_gain: float = 0.0,
) -> dict[str, Any]:
    """
    Simulates a historical rebalancing portfolio backtest.
    Selects the top N stocks based on historical meta ranking score,
    applies liquidity and trend filters, rebalances weights, and tracks NAV.

    On any decision date not covered by `meta_ranking`, falls back to
    src.analytics.reversal_quality_score.score_reversal_quality (validated
    mean-reversion 3-factor score -- see STRATEGY_RESEARCH_REPORT.md sections
    3-6). This replaces a prior momentum/trend/liquidity fallback that a
    shuffle test proved had no alpha.

    market_regime (optional): DataFrame with ["date", regime_col]. When
    provided, exposure is scaled down by regime_cash_fraction on days where
    the PRIOR session's regime is in risk_off_regimes (lagged 1 day -- the
    regime classifier uses same-day MA/breadth features, so using it same-day
    would be look-ahead bias, same class of bug as D1).

    stop_loss_pct (optional, e.g. -0.15): per-position stop-loss measured
    from the value at last entry/rebalance. Cannot trigger before
    load_min_holding_sessions() sessions have been held (T+2.5 settlement,
    same constraint as C2's simulator-level stops).

    take_profit_pct (optional, e.g. 0.10): once a position's unrealized gain
    (from last entry/rebalance) reaches this threshold, the position is
    "armed" but NOT sold mechanically -- it is only closed once the uptrend
    structure breaks (features[trend_break_col] turns False that day), i.e.
    winners run inside an intact uptrend and are taken off only on a
    confirmed structural break. Same min_holding_sessions gate as stop-loss.

    giveback_arm_gain (optional, e.g. 0.15): PORTFOLIO-level give-back stop,
    independent of and complementary to the per-position stop-loss/regime
    filters -- protects the whole account against a "was up big, gave it all
    back" round trip regardless of what any market-level indicator says.
    Tracks the portfolio's own peak NAV since inception (or since the last
    trigger): once that peak has gained >= giveback_arm_gain over the
    baseline NAV, the breaker "arms". While armed, if NAV falls back to
    <= giveback_trigger_gain over the baseline (0.0 = breakeven, the
    baseline capital -- can be negative to allow giving back into a small
    loss before triggering), everything is liquidated to cash immediately to
    lock in whatever remains. Baseline resets to the post-trigger NAV so the
    breaker can re-arm for a fresh cycle; normal rebalancing resumes at the
    next scheduled rebalance date. None disables the feature entirely
    (default; matches prior behavior exactly).

    benchmark_features (optional): DataFrame with `date` and `return_1d`
    columns (e.g. data/processed/benchmark_vnindex.parquet) used to build
    the returned `benchmark_curve`/`benchmark_symbol`. Only needed if
    `features` doesn't already contain a "VNINDEX" symbol row (it usually
    doesn't -- VNINDEX lives in a separate file, not
    data/processed/stock_features.parquet). If neither a VNINDEX row nor
    `benchmark_features` is available, this raises rather than silently
    substituting some other stock's data and labeling it as the benchmark
    (that used to happen here -- see FOLD_AUTOPSY_REPORT.md).

    max_per_sector / sector_map: caps how many of the `portfolio_size`
    selections can share a sector. Selection still walks the score-sorted
    candidate list top-down, just skipping any symbol whose sector has
    already hit the cap, until portfolio_size names are filled (or
    candidates run out). `sector_map` is a plain {symbol: sector} dict;
    unmapped symbols count as "UNKNOWN". The cap is only active when
    `sector_map` is actually supplied (max_per_sector alone is a no-op
    without it) -- callers who don't pass sector_map get plain top-N
    selection regardless of max_per_sector's value.

    portfolio_size=10 / max_per_sector=2 are the defaults as of
    CONCENTRATION_ANALYSIS_REPORT.md (was portfolio_size=5, no sector cap).
    Basis: a pre-registered theoretical prediction ("more names -> shallower
    worst fold, mean/median converge") was tested and partially confirmed --
    worst-fold CAGR shallowed monotonically with size (-59.7% -> -55.2% ->
    -45.3% for 5/10/20 names) and the 10-name+cap-2 variant beat plain
    size=10 on every metric tested. This is a diversification decision, not
    a "this config won the sensitivity table" decision -- **it reduces
    variance, it does not fix signal quality.** The same report's null test
    (2,000 random portfolios/fold) found the deployed alpha_score actually
    underperforms random stock-picking on average across the 5 folds tested
    (mean percentile 41.2, i.e. below the 50th), and one fold's failure
    (2026, percentile 0.4) was attributed to the score itself, not
    concentration noise -- more names would not have fixed that fold.
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
    take_profit_exits: list[dict] = []
    giveback_stop_exits: list[dict] = []
    giveback_baseline_nav = initial_nav
    giveback_peak_nav = initial_nav
    giveback_armed = False
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

            # A1b. Portfolio-level give-back stop: protect a big unrealized
            # gain from round-tripping all the way back to breakeven,
            # independent of any market/regime indicator.
            if giveback_arm_gain is not None:
                if nav > giveback_peak_nav:
                    giveback_peak_nav = nav
                peak_gain = giveback_peak_nav / giveback_baseline_nav - 1.0 if giveback_baseline_nav > 0 else 0.0
                if not giveback_armed and peak_gain >= giveback_arm_gain:
                    giveback_armed = True
                if giveback_armed:
                    current_gain = nav / giveback_baseline_nav - 1.0 if giveback_baseline_nav > 0 else 0.0
                    if current_gain <= giveback_trigger_gain:
                        liquidation_value = sum(pos["value"] for pos in current_holdings.values())
                        if liquidation_value > 0:
                            nav -= liquidation_value * transaction_cost_pct
                            for sym in list(current_holdings.keys()):
                                trades_log.append({
                                    "date": current_date.strftime("%Y-%m-%d"),
                                    "symbol": sym,
                                    "type": "SELL",
                                    "size_amount": current_holdings[sym]["value"],
                                    "old_value": current_holdings[sym]["value"],
                                    "new_value": 0.0,
                                    "reason": "giveback_stop",
                                })
                            current_holdings = {}
                        giveback_stop_exits.append({
                            "date": current_date.strftime("%Y-%m-%d"),
                            "peak_gain": peak_gain,
                            "trigger_gain": current_gain,
                            "nav": nav,
                        })
                        # Reset baseline/peak so the breaker can re-arm for a fresh cycle.
                        giveback_baseline_nav = nav
                        giveback_peak_nav = nav
                        giveback_armed = False

            # A2. Stop-loss / structural take-profit: per-position, measured
            # from last entry/rebalance value; cannot trigger before T+2.5
            # settlement (min_holding_sessions).
            if stop_loss_pct is not None or take_profit_pct is not None:
                for sym in list(current_holdings.keys()):
                    pos = current_holdings[sym]
                    held_sessions = day_idx - pos["entry_day_idx"] + 1
                    if held_sessions < min_holding_sessions:
                        continue
                    entry_value = pos["entry_value"]
                    if entry_value <= 0:
                        continue
                    move = pos["value"] / entry_value - 1.0

                    exit_reason = None
                    if stop_loss_pct is not None and move <= stop_loss_pct:
                        exit_reason = "stop_loss"
                    elif take_profit_pct is not None and move >= take_profit_pct:
                        # Armed once the gain threshold is hit, but only
                        # closed once the uptrend structure actually breaks --
                        # let winners run inside an intact uptrend.
                        trend_intact = True
                        try:
                            trend_val = df_indexed.loc[(sym, current_date), trend_break_col]
                            if pd.notna(trend_val):
                                trend_intact = bool(trend_val)
                        except KeyError:
                            pass
                        if not trend_intact:
                            exit_reason = "take_profit_trend_break"

                    if exit_reason is None:
                        continue

                    exit_value = pos["value"]
                    nav -= exit_value * transaction_cost_pct
                    del current_holdings[sym]
                    exit_record = {
                        "date": current_date.strftime("%Y-%m-%d"),
                        "symbol": sym,
                        "move_since_entry": move,
                        "exit_value": exit_value,
                    }
                    if exit_reason == "stop_loss":
                        stop_loss_exits.append(exit_record)
                    else:
                        take_profit_exits.append(exit_record)
                    trades_log.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "symbol": sym,
                        "type": "SELL",
                        "size_amount": exit_value,
                        "old_value": exit_value,
                        "new_value": 0.0,
                        "reason": exit_reason,
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
                # Validated mean-reversion score (STRATEGY_RESEARCH_REPORT.md
                # section 6) replaces the old momentum/trend/liquidity blend,
                # which a shuffle test proved had no alpha.
                scored = score_reversal_quality(features_today.reset_index())
                scores_today = scored.set_index("symbol")[["reversal_quality_score"]].rename(
                    columns={"reversal_quality_score": "meta_score"}
                )
                
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

                if max_per_sector is not None and sector_map is not None:
                    selected_symbols = []
                    sector_counts: dict[str, int] = {}
                    for sym in merged.index:
                        sec = sector_map.get(sym, "UNKNOWN")
                        if sector_counts.get(sec, 0) >= max_per_sector:
                            continue
                        selected_symbols.append(sym)
                        sector_counts[sec] = sector_counts.get(sec, 0) + 1
                        if len(selected_symbols) >= portfolio_size:
                            break
                else:
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
    
    # Benchmark comparison. Requires either a real "VNINDEX" row in
    # `features` or an explicit `benchmark_features` frame -- no silent
    # substitution of an arbitrary other stock's data (that used to happen
    # here; see FOLD_AUTOPSY_REPORT.md).
    vnindex_rows = df[df["symbol"].astype(str).str.upper() == "VNINDEX"].sort_values("date")
    if not vnindex_rows.empty:
        bench_df = vnindex_rows
        benchmark_source = "VNINDEX"
    elif benchmark_features is not None and not benchmark_features.empty:
        if "date" not in benchmark_features.columns or "return_1d" not in benchmark_features.columns:
            raise ValueError(
                "run_portfolio_backtest: benchmark_features must have 'date' and "
                "'return_1d' columns."
            )
        bench_df = benchmark_features.copy()
        bench_df["date"] = pd.to_datetime(bench_df["date"])
        bench_df = bench_df.sort_values("date")
        benchmark_source = str(bench_df["symbol"].iloc[0]) if "symbol" in bench_df.columns else "external_benchmark"
    else:
        raise ValueError(
            "run_portfolio_backtest: no benchmark available -- 'VNINDEX' is not a "
            "symbol in `features` (it usually isn't; VNINDEX lives in "
            "data/processed/benchmark_vnindex.parquet, a separate file) and no "
            "`benchmark_features` was supplied. A prior version of this function "
            "silently substituted an arbitrary other stock's data here and "
            "labeled it as the benchmark -- that has been removed. Pass "
            "benchmark_features=<DataFrame with 'date'/'return_1d' columns> "
            "explicitly."
        )

    bench_df = bench_df[bench_df["date"].isin(dates_list)].set_index("date")
    bench_nav = (1.0 + bench_df["return_1d"].fillna(0.0)).cumprod() * initial_nav
    bench_nav = bench_nav.reindex(dates_list).ffill().fillna(initial_nav)

    return {
        "equity_curve": equity_series,
        "portfolio_returns": pct_returns,
        "benchmark_curve": bench_nav,
        "benchmark_symbol": benchmark_source,
        "trades_log": pd.DataFrame(trades_log),
        "skipped_limit_up": pd.DataFrame(skipped_limit_up),
        "regime_adjustments": pd.DataFrame(regime_adjustments),
        "stop_loss_exits": pd.DataFrame(stop_loss_exits),
        "take_profit_exits": pd.DataFrame(take_profit_exits),
        "giveback_stop_exits": pd.DataFrame(giveback_stop_exits),
        "metrics": {
            "initial_nav": initial_nav,
            "final_nav": nav,
            "cagr": cagr,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
            "total_trades": len(trades_log),
            "stop_loss_exit_count": len(stop_loss_exits),
            "take_profit_exit_count": len(take_profit_exits),
            "giveback_stop_exit_count": len(giveback_stop_exits),
            "regime_adjustment_count": len(regime_adjustments),
        }
    }


def symbols_universe(df: pd.DataFrame) -> list[str]:
    """Helper to get list of all unique symbols in the dataset."""
    return df["symbol"].dropna().unique().tolist()
