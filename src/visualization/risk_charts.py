"""Risk visualization charts."""
from __future__ import annotations

import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def ensure_dir(path: str | None) -> None:
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def plot_annualized_volatility_bar(
    summary_df: pd.DataFrame,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot bar chart of annualized volatility per symbol."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    data = summary_df.sort_values("annualized_volatility", ascending=False).copy()
    vol = data["annualized_volatility"]
    if vol.max() <= 1.0:
        vol = vol * 100.0
        
    bars = ax.bar(data["symbol"], vol, color="crimson", edgecolor="black", alpha=0.8)
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, f"{yval:.1f}%", ha='center', va='bottom', fontsize=9, fontweight="bold")
        
    ax.set_title("Annualized Volatility Comparison", fontsize=14, fontweight="bold")
    ax.set_xlabel("Stock Symbol", fontsize=12)
    ax.set_ylabel("Annualized Volatility (%)", fontsize=12)
    ax.grid(True, axis="y", linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_rolling_volatility(
    df: pd.DataFrame,
    symbols: list[str],
    window: int = 20,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot rolling volatility over time."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for symbol in symbols:
        symbol_df = df[df["symbol"].str.upper() == symbol.upper()].sort_values("date").copy()
        if symbol_df.empty:
            continue
        vol_col = f"realized_vol_{window}d"
        if vol_col not in symbol_df.columns:
            rolling_vol = symbol_df["return_1d"].rolling(window).std() * np.sqrt(252) * 100.0
        else:
            rolling_vol = symbol_df[vol_col]
            if rolling_vol.max() <= 1.0:
                rolling_vol = rolling_vol * 100.0
                
        ax.plot(symbol_df["date"], rolling_vol, label=symbol.upper(), linewidth=1.5)
        
    ax.set_title(f"Rolling {window}-Day Annualized Volatility (%)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Annualized Volatility (%)", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_atr_pct(
    df: pd.DataFrame,
    symbols: list[str],
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot ATR% over time to represent average range relative to price."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for symbol in symbols:
        symbol_df = df[df["symbol"].str.upper() == symbol.upper()].sort_values("date").copy()
        if symbol_df.empty:
            continue
        atr_col = "atr_pct_14"
        if atr_col in symbol_df.columns:
            atr_vals = symbol_df[atr_col]
            if atr_vals.max() <= 1.0:
                atr_vals = atr_vals * 100.0
            ax.plot(symbol_df["date"], atr_vals, label=symbol.upper(), linewidth=1.5)
            
    ax.set_title("Average True Range Percentage (ATR % 14d)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("ATR (%)", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_drawdown_curve(
    df: pd.DataFrame,
    symbols: list[str],
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot drawdown curves over time."""
    from src.analytics.drawdown import calculate_symbol_drawdowns
    fig, ax = plt.subplots(figsize=(10, 6))
    
    if "drawdown" not in df.columns:
        df = calculate_symbol_drawdowns(df)
        
    for symbol in symbols:
        symbol_df = df[df["symbol"].str.upper() == symbol.upper()].sort_values("date").copy()
        if symbol_df.empty:
            continue
        dd = symbol_df["drawdown"]
        if dd.min() >= -1.0:
            dd = dd * 100.0
        ax.plot(symbol_df["date"], dd, label=symbol.upper(), linewidth=1.5)
        
    ax.set_title("Drawdown Curves (%)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Drawdown (%)", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="lower left")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_return_vs_drawdown(
    summary_df: pd.DataFrame,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot scatter showing Sharpe Quality: Return vs Max Drawdown."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ret = summary_df["annualized_return"]
    mdd = summary_df["max_drawdown"].abs()
    
    if ret.max() <= 1.0:
        ret = ret * 100.0
    if mdd.max() <= 1.0:
        mdd = mdd * 100.0
        
    ax.scatter(mdd, ret, color="orange", alpha=0.7, edgecolors="black", s=100)
    
    for _, row in summary_df.iterrows():
        x = abs(row["max_drawdown"])
        y = row["annualized_return"]
        if x <= 1.0:
            x = x * 100.0
        if y <= 1.0:
            y = y * 100.0
        ax.annotate(row["symbol"], (x + 0.5, y), fontsize=9, fontweight="bold")
        
    ax.set_title("Annualized Return vs Maximum Drawdown", fontsize=14, fontweight="bold")
    ax.set_xlabel("Maximum Drawdown (%)", fontsize=12)
    ax.set_ylabel("Annualized Return (%)", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax
