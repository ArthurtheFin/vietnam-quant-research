"""Simulation and risk distribution charts."""
from __future__ import annotations

import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def ensure_dir(path: str | None) -> None:
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def plot_simulated_equity_paths(
    simulated_paths: np.ndarray,
    max_paths_to_plot: int = 100,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot the simulated equity paths."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    n_paths = min(len(simulated_paths), max_paths_to_plot)
    days = np.arange(simulated_paths.shape[1])
    
    for i in range(n_paths):
        ax.plot(days, simulated_paths[i], color="blue", alpha=0.1, linewidth=0.8)
        
    mean_path = simulated_paths.mean(axis=0)
    median_path = np.median(simulated_paths, axis=0)
    
    ax.plot(days, mean_path, color="red", linewidth=2.5, label="Mean Path")
    ax.plot(days, median_path, color="green", linewidth=2.0, linestyle="--", label="Median Path")
    
    q05 = np.quantile(simulated_paths, 0.05, axis=0)
    q95 = np.quantile(simulated_paths, 0.95, axis=0)
    ax.plot(days, q05, color="black", linestyle=":", label="5% Percentile")
    ax.plot(days, q95, color="black", linestyle=":", label="95% Percentile")
    
    ax.set_title("Simulated Equity Paths (Bootstrap)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Trading Days", fontsize=12)
    ax.set_ylabel("Portfolio Value", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_final_return_distribution(
    simulated_paths: np.ndarray,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot the distribution of the final terminal returns."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    initial_value = simulated_paths[0, 0]
    final_returns = (simulated_paths[:, -1] / initial_value - 1.0) * 100.0
    
    ax.hist(final_returns, bins=50, color="lightblue", edgecolor="black", alpha=0.8)
    
    ax.axvline(final_returns.mean(), color="red", linestyle="-", linewidth=2, label=f"Mean ({final_returns.mean():.1f}%)")
    ax.axvline(np.median(final_returns), color="green", linestyle="--", linewidth=2, label=f"Median ({np.median(final_returns):.1f}%)")
    
    ax.set_title("Distribution of Simulated Terminal Returns (%)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Terminal Return (%)", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_var_cvar_distribution(
    simulated_returns: np.ndarray,
    var_value: float,
    cvar_value: float,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot return distribution with VaR and CVaR boundaries."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ret_pct = simulated_returns * 100.0
    var_pct = var_value * 100.0
    cvar_pct = cvar_value * 100.0
    
    ax.hist(ret_pct, bins=50, color="lightcoral", edgecolor="black", alpha=0.7)
    
    ax.axvline(-var_pct, color="darkred", linestyle="-", linewidth=2.5, label=f"VaR 95% (-{var_pct:.1f}%)")
    ax.axvline(-cvar_pct, color="red", linestyle="--", linewidth=2.0, label=f"CVaR 95% (-{cvar_pct:.1f}%)")
    
    ax.set_title("Value at Risk (VaR) & Expected Shortfall (CVaR)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Simulated Return (%)", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax


def plot_probability_cone(
    simulated_paths: np.ndarray,
    save_path: str | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Plot rolling percentiles over time as a probability cone."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    days = np.arange(simulated_paths.shape[1])
    
    q05 = np.quantile(simulated_paths, 0.05, axis=0)
    q25 = np.quantile(simulated_paths, 0.25, axis=0)
    q50 = np.quantile(simulated_paths, 0.50, axis=0)
    q75 = np.quantile(simulated_paths, 0.75, axis=0)
    q95 = np.quantile(simulated_paths, 0.95, axis=0)
    
    ax.fill_between(days, q05, q95, color="lightblue", alpha=0.3, label="5% - 95% Band")
    ax.fill_between(days, q25, q75, color="blue", alpha=0.2, label="25% - 75% Band")
    ax.plot(days, q50, color="darkblue", linewidth=2.0, label="Median (50%)")
    
    ax.set_title("Rolling Probability Cone", fontsize=14, fontweight="bold")
    ax.set_xlabel("Trading Days", fontsize=12)
    ax.set_ylabel("Portfolio Value", fontsize=12)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left")
    
    plt.tight_layout()
    if save_path:
        ensure_dir(save_path)
        fig.savefig(save_path, dpi=150)
    return fig, ax
