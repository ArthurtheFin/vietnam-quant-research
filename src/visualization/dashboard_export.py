"""Master dashboard export for all visual charts."""
from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from src.visualization.performance_charts import plot_normalized_cumulative_return, plot_risk_return_scatter
from src.visualization.risk_charts import plot_rolling_volatility, plot_drawdown_curve
from src.visualization.correlation_charts import plot_correlation_heatmap, plot_clustered_correlation_heatmap, plot_correlation_to_benchmark
from src.simulation.bootstrap import historical_bootstrap_returns, simulate_equity_paths_from_returns
from src.visualization.simulation_charts import plot_simulated_equity_paths, plot_final_return_distribution


def generate_visual_risk_dashboard(
    df: pd.DataFrame,
    alpha_df: pd.DataFrame | None = None,
    benchmark_symbol: str = "VNINDEX",
    output_dir: str = "reports/figures",
) -> None:
    """Generate and save all core visualization charts to the output directory."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    all_symbols = [s for s in df["symbol"].unique() if str(s).upper() != benchmark_symbol.upper()]
    
    if alpha_df is not None and not alpha_df.empty:
        latest_date = alpha_df["date"].max()
        top_symbols = (
            alpha_df[alpha_df["date"] == latest_date]
            .sort_values("alpha_score", ascending=False)
            .head(5)["symbol"]
            .tolist()
        )
    else:
        top_symbols = all_symbols[:5]
        
    if not top_symbols:
        print("[Warning] No symbols found for dashboard generation.")
        return
        
    print(f"Generating time-series charts for top symbols: {top_symbols}")
    
    # 2. Cumulative Return Chart
    try:
        plot_normalized_cumulative_return(
            df=df,
            symbols=top_symbols,
            benchmark_symbol=benchmark_symbol,
            save_path=str(out_path / "normalized_cumulative_return.png")
        )
        plt.close("all")
    except Exception as e:
        print(f"[Error] Failed to plot cumulative returns: {e}")
        
    # 3. Rolling Volatility
    try:
        plot_rolling_volatility(
            df=df,
            symbols=top_symbols,
            window=20,
            save_path=str(out_path / "rolling_volatility_20d.png")
        )
        plt.close("all")
    except Exception as e:
        print(f"[Error] Failed to plot rolling volatility: {e}")

    # 4. Drawdown curves
    try:
        plot_drawdown_curve(
            df=df,
            symbols=top_symbols,
            save_path=str(out_path / "drawdown_curves.png")
        )
        plt.close("all")
    except Exception as e:
        print(f"[Error] Failed to plot drawdown curves: {e}")

    # 5. Correlation heatmap of these top symbols
    top_returns = (
        df[df["symbol"].isin(top_symbols)]
        .pivot_table(index="date", columns="symbol", values="return_1d", aggfunc="last")
        .dropna(how="all")
    )
    if not top_returns.empty:
        corr_matrix = top_returns.corr(method="pearson")
        try:
            plot_correlation_heatmap(
                corr_matrix=corr_matrix,
                title=f"Correlation Heatmap of Top Symbols",
                save_path=str(out_path / "correlation_heatmap.png")
            )
            plt.close("all")
            
            plot_clustered_correlation_heatmap(
                corr_matrix=corr_matrix,
                title=f"Clustered Correlation Heatmap",
                save_path=str(out_path / "clustered_correlation_heatmap.png")
            )
            plt.close("all")
        except Exception as e:
            print(f"[Error] Failed to plot correlation heatmaps: {e}")

    # 6. Rolling Correlation to Benchmark
    try:
        from src.analytics.correlation import rolling_pair_correlation
        corr_list = []
        for sym in top_symbols:
            try:
                rc = rolling_pair_correlation(df, sym, benchmark_symbol, window=60)
                rc["symbol"] = sym
                corr_list.append(rc)
            except Exception:
                pass
        if corr_list:
            corr_df = pd.concat(corr_list)
            plot_correlation_to_benchmark(
                corr_to_benchmark_df=corr_df,
                benchmark_symbol=benchmark_symbol,
                save_path=str(out_path / "rolling_correlation_to_benchmark.png")
            )
            plt.close("all")
    except Exception as e:
        print(f"[Error] Failed to plot rolling correlation to benchmark: {e}")

    # 7. Alpha Charts (if alpha_df is available)
    if alpha_df is not None and not alpha_df.empty:
        latest_date = alpha_df["date"].max()
        latest_alpha = alpha_df[alpha_df["date"] == latest_date].copy()
        
        stats_rows = []
        for sym in latest_alpha["symbol"].unique():
            sym_df = df[df["symbol"].str.upper() == sym.upper()].sort_values("date")
            if len(sym_df) < 20:
                continue
            r = sym_df["return_1d"].dropna()
            stats_rows.append({
                "symbol": sym,
                "annualized_return": float(r.mean() * 252),
                "annualized_volatility": float(r.std() * np.sqrt(252)),
            })
        if stats_rows:
            stats_df = pd.DataFrame(stats_rows)
            try:
                plot_risk_return_scatter(
                    summary_df=stats_df.head(20),
                    save_path=str(out_path / "risk_return_scatter.png")
                )
                plt.close("all")
            except Exception as e:
                print(f"[Error] Failed to plot risk-return scatter: {e}")

    # 8. Portfolio simulation path charts
    portfolio_returns = top_returns.mean(axis=1)
    if not portfolio_returns.empty:
        try:
            sim_returns = historical_bootstrap_returns(portfolio_returns, horizon_days=20, n_simulations=1000)
            sim_paths = simulate_equity_paths_from_returns(sim_returns, initial_value=100.0)
            
            plot_simulated_equity_paths(
                simulated_paths=sim_paths,
                max_paths_to_plot=100,
                save_path=str(out_path / "simulation_equity_paths.png")
            )
            plt.close("all")
            
            plot_final_return_distribution(
                simulated_paths=sim_paths,
                save_path=str(out_path / "simulation_final_return_distribution.png")
            )
            plt.close("all")
        except Exception as e:
            print(f"[Error] Failed to run/plot portfolio simulations: {e}")

    print("Dashboard charts generated successfully!")
