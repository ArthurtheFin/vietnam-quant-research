from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from src.analytics.entropy import ENTROPY_REGIME_HIGH_THRESHOLD, ENTROPY_REGIME_LOW_THRESHOLD


def return_distribution_chart(df: pd.DataFrame, return_col: str = "return_1d"):
    return px.histogram(df.dropna(subset=[return_col]), x=return_col, nbins=60, title=f"Distribution of {return_col}")


def price_chart(df: pd.DataFrame, symbol: str):
    data = df[df["symbol"].str.upper() == symbol.upper()].copy()
    return px.line(data, x="date", y="close", title=f"{symbol.upper()} Close Price")


def monte_carlo_fan_chart(
    summary: pd.DataFrame,
    entry: float,
    stop: float | None = None,
    target: float | None = None,
    title: str = "Monte Carlo Price Fan Chart",
):
    fig = go.Figure()
    x = summary["day"]

    if {"q05", "q95"}.issubset(summary.columns):
        fig.add_trace(go.Scatter(x=x, y=summary["q95"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(
            go.Scatter(
                x=x,
                y=summary["q05"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(31, 119, 180, 0.12)",
                name="5-95% band",
            )
        )

    if {"q25", "q75"}.issubset(summary.columns):
        fig.add_trace(go.Scatter(x=x, y=summary["q75"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(
            go.Scatter(
                x=x,
                y=summary["q25"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(31, 119, 180, 0.24)",
                name="25-75% band",
            )
        )

    if "q50" in summary.columns:
        fig.add_trace(go.Scatter(x=x, y=summary["q50"], mode="lines", name="Median path", line=dict(color="#0f4c5c", width=3)))
    fig.add_trace(go.Scatter(x=x, y=summary["mean_price"], mode="lines", name="Mean path", line=dict(color="#e36414", dash="dash")))

    fig.add_hline(y=entry, line_dash="dot", line_color="#4f5d75", annotation_text="Entry")
    if stop is not None:
        fig.add_hline(y=stop, line_dash="dash", line_color="#c1121f", annotation_text="Stop")
    if target is not None:
        fig.add_hline(y=target, line_dash="dash", line_color="#2d6a4f", annotation_text="Target")

    fig.update_layout(title=title, xaxis_title="Day", yaxis_title="Price", template="plotly_white")
    return fig


def monte_carlo_exit_histogram(
    exits: pd.DataFrame,
    return_col: str = "exit_return",
    title: str = "Monte Carlo Exit Return Distribution",
):
    plot_df = exits.copy()
    plot_df["exit_return_pct"] = plot_df[return_col] * 100
    return px.histogram(
        plot_df,
        x="exit_return_pct",
        color="exit_type",
        nbins=50,
        title=title,
        labels={"exit_return_pct": "Exit return (%)", "exit_type": "Exit type"},
    )


def monte_carlo_terminal_distribution_chart(
    paths: np.ndarray,
    start_value: float,
    title: str = "Monte Carlo Terminal Distribution",
):
    if paths.ndim != 2 or paths.shape[0] == 0:
        return px.histogram(pd.DataFrame({"terminal_return_pct": []}), x="terminal_return_pct", title=title)
    terminal = pd.Series(paths[:, -1], name="terminal_value", dtype=float)
    plot_df = pd.DataFrame(
        {
            "terminal_value": terminal,
            "terminal_return_pct": (terminal / float(start_value) - 1.0) * 100.0,
        }
    )
    fig = px.histogram(
        plot_df,
        x="terminal_return_pct",
        nbins=60,
        title=title,
        labels={"terminal_return_pct": "Terminal return (%)"},
        color_discrete_sequence=["#457b9d"],
    )
    for q, color, label in [
        (0.05, "#c1121f", "5%"),
        (0.50, "#1d3557", "Median"),
        (0.95, "#2d6a4f", "95%"),
    ]:
        x = float(plot_df["terminal_return_pct"].quantile(q))
        fig.add_vline(x=x, line_dash="dash", line_color=color, annotation_text=label)
    fig.update_layout(template="plotly_white")
    return fig


def monte_carlo_exit_timeline_chart(
    exits: pd.DataFrame,
    title: str = "Monte Carlo Exit Timing",
):
    if exits.empty:
        return px.histogram(pd.DataFrame({"exit_day": [], "exit_type": []}), x="exit_day", color="exit_type", title=title)
    fig = px.histogram(
        exits,
        x="exit_day",
        color="exit_type",
        nbins=min(40, max(10, int(exits["exit_day"].max()))),
        barmode="stack",
        title=title,
        labels={"exit_day": "Exit day", "exit_type": "Exit type"},
        color_discrete_map={"target": "#2d6a4f", "stop": "#c1121f", "time": "#6c757d"},
    )
    fig.update_layout(template="plotly_white")
    return fig


def monte_carlo_scenario_chart(
    scenario_df: pd.DataFrame,
    score_col: str = "expected_return",
    title: str = "Monte Carlo Scenario Comparison",
):
    if scenario_df.empty:
        return px.scatter(pd.DataFrame({"risk_reward": [], score_col: []}), x="risk_reward", y=score_col, title=title)
    data = scenario_df.copy()
    for col in ["expected_return", "median_return", "var_95", "best_5pct"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce") * 100.0
    fig = px.scatter(
        data,
        x="risk_reward",
        y=score_col,
        size="p_target_before_stop" if "p_target_before_stop" in data.columns else None,
        color="var_95" if "var_95" in data.columns else score_col,
        hover_data=[col for col in ["stop_pct", "target_pct", "median_return", "best_5pct", "avg_exit_day"] if col in data.columns],
        title=title,
        labels={
            "risk_reward": "Risk / reward",
            score_col: "Expected return (%)" if score_col == "expected_return" else score_col,
            "var_95": "5% tail return (%)",
        },
        color_continuous_scale="RdYlGn",
    )
    fig.update_layout(template="plotly_white")
    return fig


def monte_carlo_probability_bar_chart(
    probability_df: pd.DataFrame,
    title: str = "Monte Carlo Probability Map",
):
    if probability_df.empty:
        return px.bar(pd.DataFrame({"scenario": [], "odds_pct": []}), x="odds_pct", y="scenario", orientation="h", title=title)
    data = probability_df.sort_values("probability", ascending=True).copy()
    fig = px.bar(
        data,
        x="odds_pct",
        y="scenario",
        orientation="h",
        color="odds_pct",
        color_continuous_scale="Tealgrn",
        title=title,
        labels={"odds_pct": "Probability (%)", "scenario": "Scenario"},
        text="odds_pct",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(template="plotly_white")
    return fig


def monte_carlo_percentile_cone_chart(
    path_summary: pd.DataFrame,
    title: str = "Monte Carlo Percentile Cone",
):
    fig = go.Figure()
    x = path_summary["day"]

    if {"q01", "q99"}.issubset(path_summary.columns):
        fig.add_trace(go.Scatter(x=x, y=path_summary["q99"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(
            go.Scatter(
                x=x,
                y=path_summary["q01"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(17, 138, 178, 0.10)",
                name="1-99% cone",
            )
        )

    if {"q05", "q95"}.issubset(path_summary.columns):
        fig.add_trace(go.Scatter(x=x, y=path_summary["q95"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(
            go.Scatter(
                x=x,
                y=path_summary["q05"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(17, 138, 178, 0.18)",
                name="5-95% cone",
            )
        )

    if {"q25", "q75"}.issubset(path_summary.columns):
        fig.add_trace(go.Scatter(x=x, y=path_summary["q75"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(
            go.Scatter(
                x=x,
                y=path_summary["q25"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(17, 138, 178, 0.28)",
                name="25-75% cone",
            )
        )

    if "q50" in path_summary.columns:
        fig.add_trace(go.Scatter(x=x, y=path_summary["q50"], mode="lines", name="Median path", line=dict(color="#1d3557", width=3)))
    if "mean_price" in path_summary.columns:
        fig.add_trace(go.Scatter(x=x, y=path_summary["mean_price"], mode="lines", name="Mean path", line=dict(color="#e76f51", dash="dash")))

    fig.update_layout(title=title, xaxis_title="Day", yaxis_title="Price", template="plotly_white")
    return fig


def correlation_heatmap(corr_matrix: pd.DataFrame, title: str = "Correlation Heatmap"):
    return px.imshow(
        corr_matrix,
        text_auto=".2f",
        aspect="auto",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        title=title,
    )


def rolling_correlation_chart(rolling_corr: pd.DataFrame, title: str = "Rolling Correlation"):
    label = f"{rolling_corr['symbol_a'].iloc[0]} vs {rolling_corr['symbol_b'].iloc[0]}" if not rolling_corr.empty else "Pair"
    return px.line(
        rolling_corr,
        x="date",
        y="rolling_correlation",
        title=f"{title}: {label}",
        labels={"rolling_correlation": "Rolling correlation"},
    )


def beta_chart(beta_df: pd.DataFrame, symbol: str, beta_col: str = "rolling_beta_60d", title: str = "Rolling Beta"):
    data = beta_df[beta_df["symbol"].astype(str).str.upper() == symbol.upper()].copy()
    return px.line(
        data,
        x="date",
        y=beta_col,
        title=f"{title}: {symbol.upper()}",
        labels={beta_col: "Beta"},
    )


def momentum_ranking_chart(
    ranking_df: pd.DataFrame,
    momentum_col: str = "momentum_20d",
    top_n: int = 10,
    title: str = "Cross-sectional Momentum Ranking",
):
    data = ranking_df.dropna(subset=[momentum_col]).nlargest(top_n, momentum_col).copy()
    return px.bar(
        data,
        x="symbol",
        y=momentum_col,
        color=momentum_col,
        title=title,
        labels={momentum_col: "Momentum"},
    )


def pair_divergence_chart(divergence_df: pd.DataFrame, title: str = "Pair Divergence Z-score"):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=divergence_df["date"],
            y=divergence_df["divergence_zscore"],
            mode="lines",
            name="Divergence z-score",
            line=dict(color="#1d3557", width=2),
        )
    )
    fig.add_hline(y=2, line_dash="dash", line_color="#c1121f")
    fig.add_hline(y=-2, line_dash="dash", line_color="#c1121f")
    fig.add_hline(y=0, line_dash="dot", line_color="#6c757d")
    fig.update_layout(title=title, xaxis_title="Date", yaxis_title="Z-score", template="plotly_white")
    return fig


def weight_bar_chart(weights: pd.Series, title: str = "Portfolio Weights"):
    data = weights.sort_values(ascending=False).rename("weight").reset_index()
    data.columns = ["symbol", "weight"]
    return px.bar(data, x="symbol", y="weight", color="weight", title=title, labels={"weight": "Weight"})


def risk_contribution_chart(risk_contributions: pd.Series, title: str = "Risk Contributions"):
    data = risk_contributions.sort_values(ascending=False).rename("risk_contribution").reset_index()
    data.columns = ["symbol", "risk_contribution"]
    return px.bar(
        data,
        x="symbol",
        y="risk_contribution",
        color="risk_contribution",
        title=title,
        labels={"risk_contribution": "Risk Contribution"},
    )


def equity_curve_chart(nav: pd.Series, title: str = "Equity Curve"):
    data = nav.rename("nav").reset_index()
    data.columns = ["date", "nav"]
    return px.line(data, x="date", y="nav", title=title, labels={"nav": "Portfolio NAV"})


def drawdown_chart(drawdown: pd.Series, title: str = "Drawdown Curve"):
    data = drawdown.rename("drawdown").reset_index()
    data.columns = ["date", "drawdown"]
    return px.area(data, x="date", y="drawdown", title=title, labels={"drawdown": "Drawdown"})


def sharpe_stability_chart(
    expanding_sharpe: pd.Series,
    rolling_sharpe: pd.Series | None = None,
    title: str = "Sharpe Stability",
):
    fig = go.Figure()
    exp_df = expanding_sharpe.rename("expanding_sharpe").reset_index()
    exp_df.columns = ["date", "expanding_sharpe"]
    fig.add_trace(
        go.Scatter(
            x=exp_df["date"],
            y=exp_df["expanding_sharpe"],
            mode="lines",
            name="Expanding Sharpe",
            line=dict(color="#1d3557", width=2.5),
        )
    )
    if rolling_sharpe is not None and not rolling_sharpe.empty:
        roll_df = rolling_sharpe.rename("rolling_sharpe").reset_index()
        roll_df.columns = ["date", "rolling_sharpe"]
        fig.add_trace(
            go.Scatter(
                x=roll_df["date"],
                y=roll_df["rolling_sharpe"],
                mode="lines",
                name="Rolling Sharpe",
                line=dict(color="#e36414", width=1.8, dash="dash"),
            )
        )
    fig.add_hline(y=0, line_dash="dot", line_color="#6c757d")
    fig.update_layout(title=title, xaxis_title="Date", yaxis_title="Sharpe", template="plotly_white")
    return fig


def entropy_regime_chart(
    entropy_df: pd.DataFrame,
    entropy_col: str,
    regime_col: str = "market_entropy_regime",
    title: str = "Market Entropy Regime",
):
    data = entropy_df.copy()
    fig = go.Figure()
    if entropy_col in data.columns:
        fig.add_trace(
            go.Scatter(
                x=data["date"],
                y=data[entropy_col],
                mode="lines",
                name=entropy_col,
                line=dict(color="#2a9d8f", width=2.5),
            )
        )
    if regime_col in data.columns:
        regime_map = {"Structured": 0.2, "Transitional": 0.5, "Chaotic": 0.8}
        overlay = data[regime_col].map(regime_map)
        fig.add_trace(
            go.Scatter(
                x=data["date"],
                y=overlay,
                mode="lines",
                name="Regime overlay",
                line=dict(color="#e76f51", width=1.5, dash="dot"),
                opacity=0.55,
            )
        )
    # Thresholds mirror classify_entropy_regime's defaults (src/analytics/entropy.py)
    # -- recalibrated from the real data distribution, NOT predictive-power
    # tested. See docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md NV3.
    fig.add_hline(
        y=ENTROPY_REGIME_LOW_THRESHOLD,
        line_dash="dash",
        line_color="#457b9d",
        annotation_text="Structured threshold (recalibrated, chua kiem dinh)",
        annotation_position="bottom right",
    )
    fig.add_hline(
        y=ENTROPY_REGIME_HIGH_THRESHOLD,
        line_dash="dash",
        line_color="#c1121f",
        annotation_text="Chaotic threshold (recalibrated, chua kiem dinh)",
        annotation_position="top right",
    )
    fig.update_layout(title=title, xaxis_title="Date", yaxis_title="Normalized entropy", template="plotly_white")
    return fig


def capital_plan_chart(capital_plan: pd.DataFrame, value_col: str = "position_value", title: str = "Capital Plan"):
    if capital_plan.empty or value_col not in capital_plan.columns or "symbol" not in capital_plan.columns:
        empty = pd.DataFrame({"symbol": [], value_col: [], "risk_pct_effective": []})
        return px.bar(empty, x="symbol", y=value_col, color="risk_pct_effective", title=title, labels={value_col: "Position Value"})
    data = capital_plan.sort_values(value_col, ascending=False).copy()
    return px.bar(data, x="symbol", y=value_col, color="risk_pct_effective", title=title, labels={value_col: "Position Value"})


def screen_score_bar_chart(
    screen_df: pd.DataFrame,
    score_col: str = "net_accumulation_score",
    top_n: int = 10,
    title: str = "Stealth Accumulation Leaders",
):
    data = screen_df.sort_values(score_col, ascending=False).head(top_n).copy()
    return px.bar(
        data,
        x="symbol",
        y=score_col,
        color="fakeout_risk_score" if "fakeout_risk_score" in data.columns else score_col,
        hover_data=["accumulation_score", "breakout_quality_score", "accumulation_stage"],
        title=title,
        labels={score_col: "Score"},
    )


def stage_distribution_chart(
    screen_df: pd.DataFrame,
    stage_col: str = "accumulation_stage",
    title: str = "Accumulation Stage Distribution",
):
    data = screen_df[stage_col].value_counts(dropna=False).rename_axis(stage_col).reset_index(name="count")
    return px.bar(data, x=stage_col, y="count", color=stage_col, title=title, labels={"count": "Count"})


def screen_history_chart(
    screen_df: pd.DataFrame,
    symbol: str,
    score_col: str = "net_accumulation_score",
    title: str = "Stealth Accumulation Score History",
):
    data = screen_df[screen_df["symbol"].astype(str).str.upper() == symbol.upper()].copy()
    return px.line(
        data,
        x="date",
        y=score_col,
        color="accumulation_stage" if "accumulation_stage" in data.columns else None,
        title=f"{title}: {symbol.upper()}",
        labels={score_col: "Score"},
    )


def sector_distribution_chart(
    screen_df: pd.DataFrame,
    sector_col: str = "sector",
    title: str = "Sector Distribution",
):
    data = screen_df[sector_col].fillna("Unclassified").value_counts(dropna=False).rename_axis(sector_col).reset_index(name="count")
    return px.bar(data, x=sector_col, y="count", color=sector_col, title=title, labels={"count": "Count"})


def backtest_horizon_chart(
    summary_df: pd.DataFrame,
    value_col: str = "avg_forward_return",
    title: str = "Screen Backtest By Horizon",
):
    return px.bar(
        summary_df,
        x="holding_period_days",
        y=value_col,
        color="portfolio_type",
        barmode="group",
        title=title,
        labels={"holding_period_days": "Holding Period (days)", value_col: "Average Forward Return"},
    )


def backtest_path_chart(
    by_date_df: pd.DataFrame,
    holding_period: int = 10,
    value_col: str = "avg_forward_return",
    title: str = "Forward Return History",
):
    data = by_date_df[by_date_df["holding_period_days"] == holding_period].copy()
    return px.line(
        data,
        x="selection_date",
        y=value_col,
        color="portfolio_type",
        title=f"{title}: {holding_period}D",
        labels={"selection_date": "Selection Date", value_col: "Average Forward Return"},
    )


def benchmark_nav_chart(
    comparison_df: pd.DataFrame,
    title: str = "VNINDEX Vs Market Proxy NAV",
):
    data = comparison_df.copy()
    fig = go.Figure()
    if "benchmark_nav" in data.columns:
        fig.add_trace(go.Scatter(x=data["date"], y=data["benchmark_nav"], mode="lines", name="Benchmark NAV", line=dict(color="#1d3557", width=2)))
    if "market_proxy_nav" in data.columns:
        fig.add_trace(go.Scatter(x=data["date"], y=data["market_proxy_nav"], mode="lines", name="Market Proxy NAV", line=dict(color="#e36414", width=2)))
    fig.update_layout(title=title, xaxis_title="Date", yaxis_title="NAV", template="plotly_white")
    return fig


def benchmark_spread_chart(
    comparison_df: pd.DataFrame,
    title: str = "Benchmark Minus Market Proxy Return Spread",
):
    data = comparison_df.copy()
    fig = go.Figure()
    if "return_spread" in data.columns:
        fig.add_trace(go.Scatter(x=data["date"], y=data["return_spread"], mode="lines", name="Return spread", line=dict(color="#6a040f", width=2)))
    if "rolling_correlation_20d" in data.columns:
        fig.add_trace(go.Scatter(x=data["date"], y=data["rolling_correlation_20d"], mode="lines", name="20D rolling corr", line=dict(color="#3a5a40", dash="dash")))
    fig.add_hline(y=0, line_dash="dot", line_color="#6c757d")
    fig.update_layout(title=title, xaxis_title="Date", yaxis_title="Spread / Correlation", template="plotly_white")
    return fig


def meta_score_bar_chart(
    ranked_df: pd.DataFrame,
    score_col: str = "meta_score",
    top_n: int = 10,
    title: str = "Meta Ranking Leaders",
):
    if ranked_df.empty or score_col not in ranked_df.columns or "symbol" not in ranked_df.columns:
        return px.bar(pd.DataFrame({"symbol": [], score_col: []}), x="symbol", y=score_col, title=title)
    data = ranked_df.sort_values(score_col, ascending=False).head(top_n).copy()
    return px.bar(
        data,
        x="symbol",
        y=score_col,
        color="priority_bucket" if "priority_bucket" in data.columns else score_col,
        hover_data=[
            col
            for col in [
                "setup_style",
                "trade_edge_score",
                "net_accumulation_score",
                "momentum_component_score",
                "risk_penalty_score",
            ]
            if col in data.columns
        ],
        title=title,
        labels={score_col: "Meta score"},
    )


def meta_priority_bucket_chart(
    ranked_df: pd.DataFrame,
    bucket_col: str = "priority_bucket",
    title: str = "Meta Ranking Bucket Distribution",
):
    if ranked_df.empty or bucket_col not in ranked_df.columns:
        return px.bar(pd.DataFrame({bucket_col: [], "count": []}), x=bucket_col, y="count", title=title)
    data = ranked_df[bucket_col].fillna("Unknown").value_counts(dropna=False).rename_axis(bucket_col).reset_index(name="count")
    return px.bar(data, x=bucket_col, y="count", color=bucket_col, title=title, labels={"count": "Count"})


def meta_component_heatmap(
    ranked_df: pd.DataFrame,
    top_n: int = 10,
    title: str = "Meta Ranking Component Heatmap",
):
    component_cols = [
        "breakout_component_score",
        "stealth_component_score",
        "momentum_component_score",
        "execution_component_score",
        "risk_penalty_score",
        "meta_score",
    ]
    available = [col for col in component_cols if col in ranked_df.columns]
    data = ranked_df.sort_values("meta_score", ascending=False).head(top_n).copy()
    if "meta_score" not in ranked_df.columns or not available or data.empty:
        return px.imshow(pd.DataFrame())
    matrix = data.set_index("symbol")[available]
    return px.imshow(
        matrix,
        text_auto=".1f",
        aspect="auto",
        color_continuous_scale="YlGnBu",
        title=title,
    )


def meta_symbol_component_chart(
    ranked_df: pd.DataFrame,
    symbol: str,
    title: str = "Meta Component Breakdown",
):
    if ranked_df.empty or "symbol" not in ranked_df.columns:
        return px.bar(pd.DataFrame({"component": [], "score": []}), x="component", y="score", title=f"{title}: {symbol.upper()}")
    data = ranked_df[ranked_df["symbol"].astype(str).str.upper() == symbol.upper()].copy()
    if data.empty:
        return px.bar(pd.DataFrame({"component": [], "score": []}), x="component", y="score", title=f"{title}: {symbol.upper()}")
    row = data.iloc[0]
    component_map = {
        "Breakout": row.get("breakout_component_score", np.nan),
        "Stealth": row.get("stealth_component_score", np.nan),
        "Momentum": row.get("momentum_component_score", np.nan),
        "Execution": row.get("execution_component_score", np.nan),
        "Risk Penalty": row.get("risk_penalty_score", np.nan),
        "Meta Score": row.get("meta_score", np.nan),
    }
    plot_df = pd.DataFrame({"component": list(component_map.keys()), "score": list(component_map.values())})
    return px.bar(plot_df, x="component", y="score", color="score", title=f"{title}: {symbol.upper()}", labels={"score": "Score"})


def weight_comparison_chart(
    plan_df: pd.DataFrame,
    target_col: str = "target_weight",
    actual_col: str = "gross_weight",
    title: str = "Target Vs Final Weights",
):
    available = [col for col in ["symbol", target_col, actual_col] if col in plan_df.columns]
    data = plan_df[available].copy()
    if len(available) < 3:
        return px.bar(pd.DataFrame({"symbol": [], "weight": [], "weight_type": []}), x="symbol", y="weight", color="weight_type", title=title)
    melted = data.melt(id_vars="symbol", value_vars=[target_col, actual_col], var_name="weight_type", value_name="weight")
    return px.bar(
        melted,
        x="symbol",
        y="weight",
        color="weight_type",
        barmode="group",
        title=title,
        labels={"weight": "Weight", "weight_type": "Weight Type"},
    )


def top_alpha_bar_chart(ranking_df: pd.DataFrame, top_n: int = 20, title: str = "Top Alpha Scores"):
    """Plot a horizontal bar chart of the top N stocks by alpha score."""
    data = ranking_df.sort_values("alpha_score", ascending=False).head(top_n).copy()
    if data.empty:
        return go.Figure()
    fig = px.bar(
        data,
        x="alpha_score",
        y="symbol",
        orientation="h",
        color="alpha_score",
        color_continuous_scale="Viridis",
        labels={"alpha_score": "Alpha Score", "symbol": "Stock Symbol"},
        title=title,
    )
    fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=500)
    return fig


def alpha_factor_heatmap(ranking_df: pd.DataFrame, top_n: int = 20, title: str = "Alpha Factor Component Heatmap"):
    """Plot a heatmap of alpha factor components for the top N stocks."""
    component_cols = [
        "momentum_score",
        "rs_score",
        "trend_score",
        "volume_score",
        "volatility_score",
        "liquidity_score",
        "alpha_score",
    ]
    available = [col for col in component_cols if col in ranking_df.columns]
    data = ranking_df.sort_values("alpha_score", ascending=False).head(top_n).copy()
    if data.empty or not available:
        return go.Figure()
    
    matrix = data.set_index("symbol")[available]
    fig = px.imshow(
        matrix,
        text_auto=".1f",
        aspect="auto",
        color_continuous_scale="RdYlGn",
        title=title,
        labels=dict(x="Factor Component", y="Stock Symbol", color="Score")
    )
    fig.update_layout(height=max(400, top_n * 25))
    return fig


def alpha_vs_volatility_chart(scored_df: pd.DataFrame, date=None, title: str = "Alpha Score vs Volatility"):
    """Plot a scatter chart of alpha score vs realized volatility for a given date."""
    if date is None:
        date = scored_df["date"].max()
    
    data = scored_df[scored_df["date"] == date].copy()
    if data.empty:
        return go.Figure()
        
    vol_col = "realized_vol_20d" if "realized_vol_20d" in data.columns else ("atr_pct_14" if "atr_pct_14" in data.columns else None)
    if vol_col is None:
        return go.Figure()
        
    # annualize volatility if it is realized_vol_20d
    x_label = "Realized Volatility (20d)"
    if vol_col == "realized_vol_20d" and data[vol_col].max() < 2.0:
        data["vol_annualized"] = data[vol_col] * np.sqrt(252) * 100
        vol_col = "vol_annualized"
        x_label = "Annualized Volatility (%)"
    elif vol_col == "atr_pct_14":
        data["vol_atr_pct"] = data[vol_col] * 100
        vol_col = "vol_atr_pct"
        x_label = "ATR % (14d)"

    color_col = "volatility_regime" if "volatility_regime" in data.columns else ("market_regime" if "market_regime" in data.columns else None)
    
    size_col = None
    if "volume" in data.columns:
        data["volume_clean"] = data["volume"].fillna(0)
        median_vol = data["volume_clean"].median()
        baseline = median_vol * 0.05 if median_vol > 0 else 1.0
        data["size_val"] = data["volume_clean"] + baseline
        size_col = "size_val"
    
    fig = px.scatter(
        data,
        x=vol_col,
        y="alpha_score",
        color=color_col,
        hover_name="symbol",
        hover_data=["close", "volume", "alpha_score"],
        labels={vol_col: x_label, "alpha_score": "Alpha Score (0-100)"},
        title=f"{title} ({pd.to_datetime(date).strftime('%Y-%m-%d')})",
        size=size_col,
        size_max=30,
    )
    # Add vertical line for universe median volatility
    median_vol = data[vol_col].median()
    fig.add_vline(x=median_vol, line_dash="dash", line_color="red", annotation_text="Median Volatility")
    # Add horizontal line for score = 75 (watchlist threshold)
    fig.add_hline(y=75, line_dash="dash", line_color="green", annotation_text="Strong Alpha Threshold (75)")
    
    fig.update_layout(height=600)
    return fig


def alpha_vs_beta_chart(scored_df: pd.DataFrame, date=None, title: str = "Alpha Score vs Beta"):
    """Plot a scatter chart of alpha score vs rolling beta for a given date."""
    if date is None:
        date = scored_df["date"].max()
    
    data = scored_df[scored_df["date"] == date].copy()
    if data.empty:
        return go.Figure()
        
    beta_col = next((c for c in data.columns if "beta" in c.lower()), None)
    if beta_col is None:
        return go.Figure()
        
    color_col = "volatility_regime" if "volatility_regime" in data.columns else ("market_regime" if "market_regime" in data.columns else None)
    
    size_col = None
    if "volume" in data.columns:
        data["volume_clean"] = data["volume"].fillna(0)
        median_vol = data["volume_clean"].median()
        baseline = median_vol * 0.05 if median_vol > 0 else 1.0
        data["size_val"] = data["volume_clean"] + baseline
        size_col = "size_val"

    fig = px.scatter(
        data,
        x=beta_col,
        y="alpha_score",
        color=color_col,
        hover_name="symbol",
        hover_data=["close", "volume", "alpha_score"],
        labels={beta_col: f"Beta ({beta_col})", "alpha_score": "Alpha Score (0-100)"},
        title=f"{title} ({pd.to_datetime(date).strftime('%Y-%m-%d')})",
        size=size_col,
        size_max=30,
    )
    # Add vertical line for Beta = 1.0
    fig.add_vline(x=1.0, line_dash="dash", line_color="red", annotation_text="Market Beta (1.0)")
    # Add horizontal line for score = 75 (watchlist threshold)
    fig.add_hline(y=75, line_dash="dash", line_color="green", annotation_text="Strong Alpha Threshold (75)")
    
    fig.update_layout(height=600)
    return fig


