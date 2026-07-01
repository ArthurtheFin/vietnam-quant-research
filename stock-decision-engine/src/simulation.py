from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class SimulationResult:
    paths: pd.DataFrame
    summary: dict[str, float]


def bootstrap_monte_carlo(stock: pd.DataFrame, metrics: dict[str, Any], cfg: dict[str, Any], seed: int = 42) -> SimulationResult:
    rng = np.random.default_rng(seed)
    horizon = int(cfg.get("mc_horizon_days", 20))
    n_paths = int(cfg.get("mc_paths", 3000))
    returns = stock["ret"].dropna().replace([np.inf, -np.inf], np.nan).dropna()
    current_vol_pct = metrics.get("volatility_percentile", np.nan)
    if "volatility_percentile" in stock.columns and np.isfinite(current_vol_pct):
        vol = stock.loc[returns.index, "volatility_percentile"]
        if current_vol_pct >= 70:
            sample = returns[vol >= 60]
        elif current_vol_pct <= 30:
            sample = returns[vol <= 40]
        else:
            sample = returns[(vol > 30) & (vol < 70)]
        if len(sample) >= 60:
            returns = sample
    if len(returns) < 30:
        raise ValueError("Not enough historical daily returns for Monte Carlo simulation.")
    draws = rng.choice(returns.to_numpy(), size=(horizon, n_paths), replace=True)
    start = float(metrics["close"])
    prices = start * np.cumprod(1.0 + draws, axis=0)
    paths = pd.DataFrame(prices, index=np.arange(1, horizon + 1))
    terminal = paths.iloc[-1] / start - 1.0
    stop = float(metrics["stop_loss"])
    target1 = float(metrics["target_1"])
    target2 = float(metrics["target_2"])
    hit_t1 = (paths >= target1).any(axis=0)
    hit_t2 = (paths >= target2).any(axis=0)
    hit_stop = (paths <= stop).any(axis=0)
    first_t1 = (paths >= target1).idxmax(axis=0).where(hit_t1, np.inf)
    first_stop = (paths <= stop).idxmax(axis=0).where(hit_stop, np.inf)
    summary = {
        "prob_final_gt_target_1": float((paths.iloc[-1] > target1).mean()),
        "prob_final_gt_target_2": float((paths.iloc[-1] > target2).mean()),
        "prob_hit_target_1_before_stop": float((first_t1 < first_stop).mean()),
        "prob_hit_stop_before_target_1": float((first_stop < first_t1).mean()),
        "expected_return": float(terminal.mean()),
        "median_return": float(terminal.median()),
        "p05_return": float(terminal.quantile(0.05)),
        "p95_return": float(terminal.quantile(0.95)),
        "cvar_return": float(terminal[terminal <= terminal.quantile(0.05)].mean()),
    }
    return SimulationResult(paths=paths, summary=summary)
