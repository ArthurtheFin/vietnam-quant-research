"""Pipeline script for Quantitative Risk, Portfolio, and Simulation Dashboard.

Loads stock features, benchmark returns, and alpha scores. Computes asset-level risk,
return, beta, and correlation tables. Simulates a top-alpha portfolio and exports all
summary statistics tables to reports/tables/ and dashboard figures to reports/figures/.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from src.data.dataset_config import OFFICIAL_FEATURES_PATH
from src.data.loaders import read_parquet
from src.analytics.drawdown import calculate_max_drawdown, calculate_recovery_time, calculate_drawdown
from src.analytics.advanced import compute_rolling_beta
from src.analytics.correlation import build_return_matrix
from src.simulation.bootstrap import block_bootstrap_returns, simulate_equity_paths_from_returns, summarize_simulation
from src.simulation.var_cvar import calculate_simulated_var, calculate_simulated_cvar
from src.visualization.dashboard_export import generate_visual_risk_dashboard
from src.risk.management import sharpe_ratio


def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Calculate annualized Sortino ratio."""
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    mean_excess = (r.mean() - risk_free_rate / 252) * 252
    downside_diff = r.clip(upper=0.0)
    downside_deviation = np.sqrt(np.mean(downside_diff ** 2)) * np.sqrt(252)
    if downside_deviation == 0:
        return np.nan
    return float(mean_excess / downside_deviation)


def main() -> None:
    print("=== Starting main_visual_dashboard Pipeline ===")

    # 1. Check & Load data
    stock_path = Path(OFFICIAL_FEATURES_PATH)
    bench_path = Path("data/processed/benchmark_vnindex.parquet")
    alpha_path = Path("data/signals/alpha_scores.parquet")

    if not stock_path.exists():
        print(f"Error: stock_features not found at {stock_path}. Run generate_features.py first.")
        sys.exit(1)
    if not alpha_path.exists():
        print(f"Error: alpha_scores not found at {alpha_path}. Run run_alpha_scoring.py first.")
        sys.exit(1)
    if not bench_path.exists():
        print(f"Error: benchmark_vnindex not found at {bench_path}. Run update_index_data.py first.")
        sys.exit(1)

    stock_df = read_parquet(str(stock_path))
    bench_df = read_parquet(str(bench_path))
    alpha_df = read_parquet(str(alpha_path))

    latest_date = alpha_df["date"].max()
    print(f"Data successfully loaded. Latest date: {latest_date.strftime('%Y-%m-%d')}")

    # Ensure reports folders exist
    tables_dir = Path("reports/tables")
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = Path("reports/figures")
    figures_dir.mkdir(parents=True, exist_ok=True)

    # 2. Extract Latest Metric Summaries
    print("Calculating rolling beta and correlations...")
    # Compute rolling beta 60d using the core utility
    beta_df = compute_rolling_beta(alpha_df, bench_df, window=60)
    
    # Merge returns to compute Pearson correlation
    bench_ret = bench_df[["date", "return_1d"]].rename(columns={"return_1d": "bench_return"})
    merged_with_bench = alpha_df.merge(bench_ret, on="date", how="left")

    symbols = [s for s in alpha_df["symbol"].unique() if str(s).upper() != "VNINDEX"]

    risk_rows = []
    return_rows = []
    beta_rows = []
    corr_rows = []
    decision_rows = []

    print("Computing symbol-level metrics...")
    for sym in symbols:
        sym_all = merged_with_bench[merged_with_bench["symbol"] == sym].sort_values("date")
        sym_beta = beta_df[beta_df["symbol"] == sym].sort_values("date")
        
        # Calculate over last 252 trading days (or full history if shorter)
        sym_subset = sym_all.tail(252)
        if len(sym_subset) < 20:
            continue

        ret_1d = sym_subset["return_1d"]
        close = sym_subset["close"]
        bench_return = sym_subset["bench_return"]

        # 1D returns compounding
        cum_prices = (1.0 + ret_1d.fillna(0.0)).cumprod() * 100.0
        
        # Drawdown calculations
        max_dd = calculate_max_drawdown(cum_prices)
        rec_days = calculate_recovery_time(cum_prices)

        # Returns/Risk metrics
        ann_ret = float(ret_1d.mean() * 252)
        ann_vol = float(ret_1d.std() * np.sqrt(252))
        sharpe = sharpe_ratio(ret_1d)
        sortino = calculate_sortino_ratio(ret_1d)

        # Latest features
        latest_feat = sym_subset.tail(1).iloc[0]
        rolling_vol_20d = float(latest_feat.get("realized_vol_20d", np.nan))
        rolling_vol_60d = float(latest_feat.get("realized_vol_60d", np.nan))
        atr_pct = float(latest_feat.get("atr_pct_14", np.nan))
        alpha_score = float(latest_feat.get("alpha_score", np.nan))
        market = str(latest_feat.get("market", "UNKNOWN"))
        value_ma20 = float(latest_feat.get("value_ma20", 0.0))
        market_regime = str(latest_feat.get("market_regime", "UNKNOWN"))

        # Beta & Correlation
        latest_beta_row = sym_beta.tail(1)
        beta_val = float(latest_beta_row["rolling_beta_60d"].iloc[0]) if not latest_beta_row.empty else np.nan
        
        corr_60 = float(ret_1d.tail(60).corr(bench_return.tail(60))) if len(ret_1d) >= 60 else np.nan
        corr_120 = float(ret_1d.tail(120).corr(bench_return.tail(120))) if len(ret_1d) >= 120 else np.nan

        # Append to respective tables
        risk_rows.append({
            "symbol": sym,
            "annualized_volatility": ann_vol,
            "max_drawdown": max_dd,
            "recovery_days": rec_days,
            "rolling_vol_20d": rolling_vol_20d,
            "rolling_vol_60d": rolling_vol_60d,
            "atr_pct_14": atr_pct
        })
        
        return_rows.append({
            "symbol": sym,
            "annualized_return": ann_ret,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino
        })

        beta_rows.append({
            "symbol": sym,
            "rolling_beta_60d": beta_val
        })

        corr_rows.append({
            "symbol": sym,
            "correlation_to_benchmark_60d": corr_60,
            "correlation_to_benchmark_120d": corr_120
        })

        # Decision classification
        label = "Avoid"
        reason = ""

        # Liquidity filter
        if value_ma20 < 2e8: # < 200M daily trading volume
            label = "Avoid"
            reason = "Illiquid (Avg daily trading value < 200M VND)"
        elif market.upper() not in ["HOSE", "HNX"]:
            label = "Avoid"
            reason = f"Market is {market} (prefer HOSE/HNX)"
        elif alpha_score < 50:
            label = "Avoid"
            reason = f"Low Alpha Score ({alpha_score:.1f} < 50)"
        elif ann_vol > 0.50:
            label = "Too Volatile"
            reason = f"High Volatility ({ann_vol*100:.1f}% > 50%)"
        elif max_dd < -0.35:
            label = "Avoid"
            reason = f"Extreme Historical Max Drawdown ({max_dd*100:.1f}% < -35%)"
        elif pd.notna(beta_val) and (beta_val < 0.1 or beta_val > 2.0):
            label = "Avoid"
            reason = f"Out of bounds Beta ({beta_val:.2f})"
        elif alpha_score >= 70:
            label = "Strong candidate"
            reason = "High Alpha, solid risk/return profile and liquidity"
        elif alpha_score >= 60:
            label = "Watchlist"
            reason = "Good Alpha, review for position sizing or pullbacks"
        else:
            label = "Avoid"
            reason = "Moderate Alpha, does not meet screening thresholds"

        decision_rows.append({
            "symbol": sym,
            "alpha_score": alpha_score,
            "market": market,
            "value_ma20": value_ma20,
            "annualized_return": ann_ret,
            "annualized_volatility": ann_vol,
            "max_drawdown": max_dd,
            "rolling_beta_60d": beta_val,
            "correlation_to_benchmark_60d": corr_60,
            "market_regime": market_regime,
            "decision_label": label,
            "reason": reason
        })

    # Save to CSV
    pd.DataFrame(risk_rows).to_csv(tables_dir / "risk_summary.csv", index=False)
    pd.DataFrame(return_rows).to_csv(tables_dir / "return_summary.csv", index=False)
    pd.DataFrame(beta_rows).to_csv(tables_dir / "beta_summary.csv", index=False)
    pd.DataFrame(corr_rows).to_csv(tables_dir / "correlation_to_benchmark.csv", index=False)
    
    decision_df = pd.DataFrame(decision_rows)
    decision_df.to_csv(tables_dir / "decision_rules.csv", index=False)

    print("CSV tables saved successfully.")

    # 3. Simulate Top Alpha Portfolio
    print("Selecting top alpha portfolio...")
    # Select HOSE/HNX, liquid (value_ma20 >= 1B VND) stocks with label in Strong Candidate or Watchlist
    valid_candidates = decision_df[
        (decision_df["value_ma20"] >= 1e9) & 
        (decision_df["decision_label"].isin(["Strong candidate", "Watchlist"]))
    ].sort_values("alpha_score", ascending=False)

    top_symbols = valid_candidates.head(5)["symbol"].tolist()
    print(f"Top portfolio symbols selected: {top_symbols}")

    if len(top_symbols) > 0:
        # Build returns matrix for top symbols
        top_returns = (
            alpha_df[alpha_df["symbol"].isin(top_symbols)]
            .pivot_table(index="date", columns="symbol", values="return_1d", aggfunc="last")
            .dropna(how="all")
        )
        
        # Equally-weighted portfolio returns
        portfolio_returns = top_returns.mean(axis=1)
        
        # Calculate stats
        port_cum_prices = (1.0 + portfolio_returns.fillna(0.0)).cumprod() * 100.0
        port_max_dd = calculate_max_drawdown(port_cum_prices)
        port_rec_days = calculate_recovery_time(port_cum_prices)
        port_ann_ret = float(portfolio_returns.mean() * 252)
        port_ann_vol = float(portfolio_returns.std() * np.sqrt(252))
        port_sharpe = sharpe_ratio(portfolio_returns)
        port_sortino = calculate_sortino_ratio(portfolio_returns)

        # Run block bootstrap simulation (horizon = 20 trading days, circular block size = 5)
        print("Running block bootstrap simulation on portfolio...")
        try:
            sim_returns = block_bootstrap_returns(
                portfolio_returns, 
                horizon_days=20, 
                block_size=5, 
                n_simulations=5000
            )
        except ValueError as e:
            print(f"Warning: Circular block bootstrap failed ({e}). Falling back to simple bootstrap.")
            from src.simulation.bootstrap import historical_bootstrap_returns
            sim_returns = historical_bootstrap_returns(
                portfolio_returns, 
                horizon_days=20, 
                n_simulations=5000
            )

        sim_paths = simulate_equity_paths_from_returns(sim_returns, initial_value=100.0)
        sim_summary = summarize_simulation(sim_paths)

        # VaR/CVaR calculations on 20-day horizon returns (from simulated paths terminal value)
        terminal_returns = (sim_paths[:, -1] / 100.0) - 1.0
        sim_var_95 = calculate_simulated_var(terminal_returns, confidence_level=0.95)
        sim_cvar_95 = calculate_simulated_cvar(terminal_returns, confidence_level=0.95)

        # Historical VaR/CVaR
        hist_var_95 = float(portfolio_returns.quantile(0.05) * -1.0)
        hist_cvar_95 = float(-portfolio_returns[portfolio_returns <= -hist_var_95].mean())

        # Save portfolio metrics
        port_metrics = {
            "annualized_return": port_ann_ret,
            "annualized_volatility": port_ann_vol,
            "sharpe_ratio": port_sharpe,
            "sortino_ratio": port_sortino,
            "max_drawdown": port_max_dd,
            "recovery_days": port_rec_days,
            "historical_var_95_daily": hist_var_95,
            "historical_cvar_95_daily": hist_cvar_95
        }
        pd.DataFrame([port_metrics]).to_csv(tables_dir / "portfolio_metrics.csv", index=False)

        # Save simulation summary
        sim_summary_out = {**sim_summary, "simulated_var_95_20d": sim_var_95, "simulated_cvar_95_20d": sim_cvar_95}
        pd.DataFrame([sim_summary_out]).to_csv(tables_dir / "simulation_summary.csv", index=False)

        # Check for high pairwise correlation among top stocks to flag correlation-risk
        corr_matrix = top_returns.corr(method="pearson")
        avg_corrs = {}
        for sym in top_symbols:
            avg_corrs[sym] = float(corr_matrix.loc[sym].drop(sym).mean())
            
        print("Average pairwise correlation of top portfolio holdings:")
        for sym, avg_c in avg_corrs.items():
            print(f"  {sym}: {avg_c:.2f}")
            if avg_c > 0.70:
                print(f"  [Warning] {sym} is highly correlated to other portfolio components! Avg correlation: {avg_c:.2f}")
                # We can update its decision label in the CSV
                decision_df.loc[decision_df["symbol"] == sym, "decision_label"] = "Too Correlated"
                decision_df.loc[decision_df["symbol"] == sym, "reason"] = f"High correlation with top alpha holdings ({avg_c:.2f} > 0.70)"
        
        # Save updated decision table
        decision_df.to_csv(tables_dir / "decision_rules.csv", index=False)

    # 4. Generate & Save all Figures
    print("Generating visual risk dashboard figures...")
    generate_visual_risk_dashboard(
        df=alpha_df,
        alpha_df=alpha_df,
        benchmark_symbol="VNINDEX",
        output_dir=str(figures_dir)
    )

    print("=== main_visual_dashboard Pipeline Completed Successfully ===")


if __name__ == "__main__":
    main()
