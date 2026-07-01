"""Performance visualization charts."""
from __future__ import annotations

import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def ensure_dir(path: str | None) -> None:
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def plot_normalized_cumulative_return(
    df: pd.DataFrame,
    symbols: list[str],
    benchmark_symbol: str | None = "VNINDEX",
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot normalized cumulative returns reindexed to 100 at start."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for symbol in symbols:
        symbol_df = df[df["symbol"].str.upper() == symbol.upper()].sort_values("date").copy()
        if symbol_df.empty:
            continue
        cum_ret = (1.0 + symbol_df["return_1d"].fillna(0.0)).cumprod() * 100.0
        ax.plot(symbol_df["date"], cum_ret, label=symbol.upper(), linewidth=1.5)
        
    if benchmark_symbol:
        bench_df = df[df["symbol"].str.upper() == benchmark_symbol.upper()].sort_values("date").copy()
        if not bench_df.empty:
            cum_ret_bench = (1.0 + bench_df["return_1d"].fillna(0.0)).cumprod() * 100.0
            ax.plot(bench_df["date"], cum_ret_bench, label=f"{benchmark_symbol.upper()} (Bench)", color="black", linestyle="--", linewidth=2.0)
            
    ax.set_title("Normalized Cumulative Returns (Reindexed to 100)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Value", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_rolling_return(
    df: pd.DataFrame,
    symbols: list[str],
    window: int = 60,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot rolling returns over a given window."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for symbol in symbols:
        symbol_df = df[df["symbol"].str.upper() == symbol.upper()].sort_values("date").copy()
        if symbol_df.empty:
            continue
        rolling_ret = symbol_df["close"].pct_change(window) * 100.0
        ax.plot(symbol_df["date"], rolling_ret, label=symbol.upper(), linewidth=1.5)
        
    ax.set_title(f"Rolling {window}-Day Return (%)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Return (%)", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_return_distribution(
    df: pd.DataFrame,
    symbols: list[str],
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot return distribution histogram for selected symbols."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for symbol in symbols:
        symbol_df = df[df["symbol"].str.upper() == symbol.upper()].copy()
        if symbol_df.empty:
            continue
        ax.hist(symbol_df["return_1d"].dropna() * 100.0, bins=50, alpha=0.5, label=symbol.upper())
        
    ax.set_title("Distribution of Daily Returns (%)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Daily Return (%)", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_risk_return_scatter(
    summary_df: pd.DataFrame,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot scatter of Annualized Return vs Annualized Volatility."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ret = summary_df["annualized_return"]
    vol = summary_df["annualized_volatility"]
    
    if ret.max() <= 1.0:
        ret = ret * 100.0
    if vol.max() <= 1.0:
        vol = vol * 100.0
        
    ax.scatter(vol, ret, color="blue", alpha=0.7, edgecolors="black", s=100)
    
    for _, row in summary_df.iterrows():
        x = row["annualized_volatility"]
        y = row["annualized_return"]
        if x <= 1.0:
            x = x * 100.0
        if y <= 1.0:
            y = y * 100.0
        ax.annotate(row["symbol"], (x + 0.5, y), fontsize=9, fontweight="bold")
        
    ax.set_title("Annualized Return vs Volatility", fontsize=14, fontweight="bold")
    ax.set_xlabel("Annualized Volatility (%)", fontsize=12)
    ax.set_ylabel("Annualized Return (%)", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax
