from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


def save_all_charts(
    stock: pd.DataFrame,
    benchmark: pd.DataFrame,
    rs: pd.DataFrame,
    rolling: pd.DataFrame,
    mc_paths: pd.DataFrame,
    metrics: dict[str, Any],
    decision: dict[str, Any],
    output_dir: str | Path,
    ticker: str,
) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    makers = {
        "price_structure": lambda: plot_price_structure(stock, metrics, ticker),
        "relative_strength": lambda: plot_relative_strength(rs, ticker),
        "rolling_alpha_beta": lambda: plot_rolling_alpha_beta(rolling, ticker),
        "momentum": lambda: plot_momentum(stock, ticker),
        "risk": lambda: plot_risk(stock, ticker),
        "monte_carlo_fan": lambda: plot_monte_carlo(mc_paths, metrics, ticker),
        "score_breakdown": lambda: plot_score_breakdown(decision["sub_scores"], ticker),
    }
    paths = {}
    for name, maker in makers.items():
        fig = maker()
        path = out / f"{ticker.upper()}_{name}.png"
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        paths[name] = path
    return paths


def plot_price_structure(stock: pd.DataFrame, metrics: dict[str, Any], ticker: str):
    fig, ax = plt.subplots(figsize=(11, 5))
    x = stock["date"]
    ax.plot(x, stock["close"], label="Close", color="#1f2937", linewidth=1.8)
    for ma, color in [("ma20", "#2563eb"), ("ma50", "#16a34a"), ("ma200", "#dc2626")]:
        if ma in stock:
            ax.plot(x, stock[ma], label=ma.upper(), color=color, linewidth=1.1)
    ax.axhspan(metrics["entry_zone_low"], metrics["entry_zone_high"], color="#93c5fd", alpha=0.25, label="Entry zone")
    ax.axhline(metrics["stop_loss"], color="#dc2626", linestyle="--", label="Stop-loss")
    ax.axhline(metrics["target_1"], color="#16a34a", linestyle="--", label="Target 1")
    ax.axhline(metrics["target_2"], color="#15803d", linestyle=":", label="Target 2")
    ax.set_title(f"{ticker.upper()} Price Structure")
    ax.legend(loc="best", fontsize=8)
    ax.grid(alpha=0.2)
    return fig


def plot_relative_strength(rs: pd.DataFrame, ticker: str):
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(rs["date"], rs["stock_cum_return"], label=f"{ticker.upper()} cumulative", color="#1f2937")
    ax.plot(rs["date"], rs["benchmark_cum_return"], label="Benchmark cumulative", color="#64748b")
    ax2 = ax.twinx()
    ax2.plot(rs["date"], rs["relative_strength_line"], label="RS line", color="#ea580c", alpha=0.8)
    ax.set_title("Relative Strength")
    ax.grid(alpha=0.2)
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc="best", fontsize=8)
    return fig


def plot_rolling_alpha_beta(rolling: pd.DataFrame, ticker: str):
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(rolling["date"], rolling["rolling_alpha"], label="Rolling Jensen alpha", color="#2563eb")
    ax2 = ax.twinx()
    ax2.plot(rolling["date"], rolling["rolling_beta"], label="Rolling beta", color="#dc2626")
    ax2.plot(rolling["date"], rolling["rolling_corr"], label="Rolling corr", color="#16a34a", alpha=0.8)
    ax.axhline(0, color="#94a3b8", linewidth=0.8)
    ax.set_title(f"{ticker.upper()} Rolling Alpha/Beta")
    ax.grid(alpha=0.2)
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc="best", fontsize=8)
    return fig


def plot_momentum(stock: pd.DataFrame, ticker: str):
    fig, axes = plt.subplots(3, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(stock["date"], stock["rsi_14"], color="#2563eb")
    axes[0].axhline(70, color="#dc2626", linestyle="--", linewidth=0.8)
    axes[0].axhline(30, color="#16a34a", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("RSI")
    axes[1].bar(stock["date"], stock["macd_hist"], color="#64748b", width=1.0)
    axes[1].set_ylabel("MACD hist")
    axes[2].plot(stock["date"], stock["adx"], label="ADX", color="#1f2937")
    axes[2].plot(stock["date"], stock["plus_di"], label="+DI", color="#16a34a")
    axes[2].plot(stock["date"], stock["minus_di"], label="-DI", color="#dc2626")
    axes[2].legend(fontsize=8)
    axes[2].set_ylabel("ADX/DI")
    axes[0].set_title(f"{ticker.upper()} Momentum")
    for ax in axes:
        ax.grid(alpha=0.2)
    return fig


def plot_risk(stock: pd.DataFrame, ticker: str):
    fig, axes = plt.subplots(3, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(stock["date"], stock["vol_20d"], label="Vol 20D", color="#2563eb")
    axes[0].plot(stock["date"], stock["vol_60d"], label="Vol 60D", color="#64748b")
    axes[0].legend(fontsize=8)
    axes[1].plot(stock["date"], stock["atr_pct"], color="#ea580c")
    axes[1].set_ylabel("ATR%")
    axes[2].fill_between(stock["date"], stock["drawdown"], 0, color="#dc2626", alpha=0.25)
    axes[2].set_ylabel("Drawdown")
    axes[0].set_title(f"{ticker.upper()} Risk")
    for ax in axes:
        ax.grid(alpha=0.2)
    return fig


def plot_monte_carlo(paths: pd.DataFrame, metrics: dict[str, Any], ticker: str):
    fig, ax = plt.subplots(figsize=(11, 5))
    sample = paths.iloc[:, : min(200, paths.shape[1])]
    ax.plot(sample.index, sample, color="#94a3b8", alpha=0.08, linewidth=0.7)
    ax.plot(paths.index, paths.median(axis=1), color="#1f2937", label="Median", linewidth=2)
    ax.plot(paths.index, paths.quantile(0.05, axis=1), color="#dc2626", label="5th pct", linewidth=1.3)
    ax.plot(paths.index, paths.quantile(0.95, axis=1), color="#16a34a", label="95th pct", linewidth=1.3)
    ax.axhline(metrics["stop_loss"], color="#dc2626", linestyle="--", label="Stop-loss")
    ax.axhline(metrics["target_1"], color="#16a34a", linestyle="--", label="Target 1")
    ax.axhline(metrics["target_2"], color="#15803d", linestyle=":", label="Target 2")
    ax.set_title(f"{ticker.upper()} Monte Carlo Fan")
    ax.set_xlabel("Future trading days")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)
    return fig


def plot_score_breakdown(scores: pd.DataFrame, ticker: str):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    s = scores.sort_values("score")
    ax.barh(s["component"], s["score"], color="#2563eb", alpha=0.85)
    ax.set_xlim(0, 100)
    ax.set_title(f"{ticker.upper()} Score Breakdown")
    ax.grid(axis="x", alpha=0.2)
    return fig
