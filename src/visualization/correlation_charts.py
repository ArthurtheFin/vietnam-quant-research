"""Correlation visualization charts."""
from __future__ import annotations

import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import seaborn as sns


def ensure_dir(path: str | None) -> None:
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def plot_correlation_heatmap(
    corr_matrix: pd.DataFrame,
    title: str = "Correlation Heatmap",
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot correlation matrix heatmap using Seaborn."""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    sns.heatmap(
        corr_matrix,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        vmin=-1.0,
        vmax=1.0,
        square=True,
        linewidths=0.5,
        ax=ax,
        cbar_kws={"shrink": 0.8}
    )
    
    ax.set_title(title, fontsize=14, fontweight="bold")
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_clustered_correlation_heatmap(
    corr_matrix: pd.DataFrame,
    title: str = "Clustered Correlation Heatmap (Hierarchical Clustering)",
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Reorder correlation matrix by cluster leaf indices and plot heatmap."""
    from src.analytics.clustering import order_correlation_matrix_by_cluster
    
    ordered_matrix = order_correlation_matrix_by_cluster(corr_matrix)
    return plot_correlation_heatmap(ordered_matrix, title=title, save_path=save_path)


def plot_rolling_correlation(
    rolling_corr_df: pd.DataFrame,
    symbol_a: str,
    symbol_b: str,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot rolling correlation between two symbols over time."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(rolling_corr_df["date"], rolling_corr_df["rolling_correlation"], color="purple", linewidth=1.5)
    
    ax.axhline(0.0, color="grey", linestyle="--", alpha=0.6)
    
    ax.set_title(f"Rolling Correlation between {symbol_a.upper()} and {symbol_b.upper()}", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Correlation Coefficient", fontsize=12)
    ax.set_ylim(-1.05, 1.05)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_correlation_to_benchmark(
    corr_to_benchmark_df: pd.DataFrame,
    benchmark_symbol: str = "VNINDEX",
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot rolling correlation of symbols to benchmark index over time."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for symbol, group in corr_to_benchmark_df.groupby("symbol"):
        group = group.sort_values("date")
        ax.plot(group["date"], group["rolling_correlation"], label=symbol.upper(), linewidth=1.5)
        
    ax.axhline(0.0, color="grey", linestyle="--", alpha=0.6)
    
    ax.set_title(f"Rolling Correlation to Benchmark ({benchmark_symbol.upper()})", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Correlation Coefficient", fontsize=12)
    ax.set_ylim(-1.05, 1.05)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower left")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax
