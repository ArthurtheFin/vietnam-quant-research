"""Historical bootstrap simulation for returns and price paths."""
from __future__ import annotations

import pandas as pd
import numpy as np


def historical_bootstrap_returns(
    returns: pd.Series,
    horizon_days: int = 20,
    n_simulations: int = 5000,
    random_state: int | None = 42,
) -> np.ndarray:
    """Bootstrap historical returns using simple sampling with replacement.
    
    Returns a 2D numpy array of shape (n_simulations, horizon_days).
    """
    r = returns.dropna().to_numpy(dtype=float)
    if len(r) == 0:
        raise ValueError("Returns series must contain at least one non-null value.")
        
    rng = np.random.default_rng(random_state)
    sampled = rng.choice(r, size=(n_simulations, horizon_days), replace=True)
    return sampled


def block_bootstrap_returns(
    returns: pd.Series,
    horizon_days: int = 20,
    block_size: int = 5,
    n_simulations: int = 5000,
    random_state: int | None = 42,
) -> np.ndarray:
    """Bootstrap historical returns using circular block bootstrapping to preserve short-term correlation.
    
    Returns a 2D numpy array of shape (n_simulations, horizon_days).
    """
    r = returns.dropna().to_numpy(dtype=float)
    n = len(r)
    if n < block_size:
        raise ValueError(f"Returns length ({n}) must be greater than block size ({block_size}).")
        
    rng = np.random.default_rng(random_state)
    sim_returns = np.zeros((n_simulations, horizon_days))
    
    num_blocks = int(np.ceil(horizon_days / block_size))
    for sim in range(n_simulations):
        path_ret = []
        for _ in range(num_blocks):
            start_idx = rng.integers(0, n)
            indices = np.arange(start_idx, start_idx + block_size) % n
            path_ret.extend(r[indices])
        sim_returns[sim, :] = np.array(path_ret)[:horizon_days]
        
    return sim_returns


def simulate_equity_paths_from_returns(
    simulated_returns: np.ndarray,
    initial_value: float = 100.0,
) -> np.ndarray:
    """Convert simulated returns into cumulative equity paths (1 + returns).cumprod()."""
    price_relatives = np.cumprod(1.0 + simulated_returns, axis=1)
    day0 = np.ones((simulated_returns.shape[0], 1)) * initial_value
    paths = np.hstack([day0, day0 * price_relatives])
    return paths


def summarize_simulation(simulated_equity_paths: np.ndarray) -> dict[str, float]:
    """Summarize simulated final outcomes."""
    final_values = simulated_equity_paths[:, -1]
    initial_value = simulated_equity_paths[0, 0]
    final_returns = final_values / initial_value - 1.0
    
    worst_idx = int(np.argmin(final_values))
    best_idx = int(np.argmax(final_values))
    
    return {
        "mean_return": float(final_returns.mean()),
        "median_return": float(np.median(final_returns)),
        "std_return": float(final_returns.std()),
        "p_loss": float((final_returns < 0.0).mean()),
        "p_gain": float((final_returns > 0.0).mean()),
        "worst_return": float(final_returns.min()),
        "best_return": float(final_returns.max()),
        "q05": float(np.quantile(final_returns, 0.05)),
        "q25": float(np.quantile(final_returns, 0.25)),
        "q75": float(np.quantile(final_returns, 0.75)),
        "q95": float(np.quantile(final_returns, 0.95)),
        "worst_path_idx": worst_idx,
        "best_path_idx": best_idx,
    }
