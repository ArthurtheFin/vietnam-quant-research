from __future__ import annotations

import numpy as np
import pandas as pd


def _first_hit_index(mask: np.ndarray) -> int | None:
    if not mask.any():
        return None
    return int(np.argmax(mask))


def simulate_trade_exits(paths: np.ndarray, entry: float, stop: float, target: float) -> pd.DataFrame:
    rows = []
    for idx, path in enumerate(paths):
        target_mask = path >= target
        stop_mask = path <= stop
        t_idx = _first_hit_index(target_mask)
        s_idx = _first_hit_index(stop_mask)

        # Conservative: stop takes priority when both hit on same step (strict <)
        if t_idx is not None and (s_idx is None or t_idx < s_idx):
            exit_type = "target"
            exit_day = t_idx + 1
            exit_price = float(target)
        elif s_idx is not None:
            exit_type = "stop"
            exit_day = s_idx + 1
            exit_price = float(stop)
        else:
            exit_type = "time"
            exit_day = len(path)
            exit_price = float(path[-1])

        rows.append(
            {
                "simulation": idx,
                "exit_type": exit_type,
                "exit_day": int(exit_day),
                "exit_price": exit_price,
                "exit_return": float(exit_price / entry - 1),
                "max_price": float(np.max(path)),
                "min_price": float(np.min(path)),
            }
        )
    return pd.DataFrame(rows)


def bootstrap_price_paths(
    returns: pd.Series,
    start_price: float,
    horizon_days: int = 20,
    simulations: int = 10000,
    random_state: int | None = 42,
) -> np.ndarray:
    """Bootstrap historical daily returns into future price paths."""
    rng = np.random.default_rng(random_state)
    r = returns.dropna().to_numpy(dtype=float)
    if len(r) == 0:
        raise ValueError("returns must contain at least one non-null value")
    sampled = rng.choice(r, size=(simulations, horizon_days), replace=True)
    price_relatives = np.cumprod(1 + sampled, axis=1)
    return start_price * price_relatives


def monte_carlo_trade_stats(paths: np.ndarray, entry: float, stop: float, target: float) -> dict:
    hit_target = (paths >= target).any(axis=1)
    hit_stop = (paths <= stop).any(axis=1)
    exits = simulate_trade_exits(paths, entry=entry, stop=stop, target=target)
    exit_returns = exits["exit_return"].to_numpy(dtype=float)
    tail_cutoff = np.quantile(exit_returns, 0.05)
    return {
        "p_hit_target": float(np.mean(hit_target)),
        "p_hit_stop": float(np.mean(hit_stop)),
        "p_target_before_stop": float((exits["exit_type"] == "target").mean()),
        "p_stop_before_target": float((exits["exit_type"] == "stop").mean()),
        "expected_return": float(np.mean(exit_returns)),
        "median_return": float(np.median(exit_returns)),
        "var_95": float(tail_cutoff),
        "cvar_95": float(exit_returns[exit_returns <= tail_cutoff].mean()),
        "best_5pct": float(np.quantile(exit_returns, 0.95)),
        "avg_exit_day": float(exits["exit_day"].mean()),
    }


def monte_carlo_path_summary(
    paths: np.ndarray,
    start_price: float,
    quantiles: tuple[float, ...] = (0.05, 0.25, 0.5, 0.75, 0.95),
) -> pd.DataFrame:
    if paths.ndim != 2 or paths.shape[0] == 0 or paths.shape[1] == 0:
        raise ValueError("paths must be a non-empty 2D array")

    summary = {
        "day": np.arange(0, paths.shape[1] + 1),
        "mean_price": np.concatenate([[start_price], paths.mean(axis=0)]),
    }

    for q in quantiles:
        label = f"q{int(round(q * 100)):02d}"
        summary[label] = np.concatenate([[start_price], np.quantile(paths, q, axis=0)])

    return pd.DataFrame(summary)


def monte_carlo_terminal_summary(
    paths: np.ndarray,
    start_value: float,
    quantiles: tuple[float, ...] = (0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99),
) -> pd.DataFrame:
    if paths.ndim != 2 or paths.shape[0] == 0 or paths.shape[1] == 0:
        raise ValueError("paths must be a non-empty 2D array")

    terminal = pd.Series(paths[:, -1], dtype=float, name="terminal_value")
    rows = [
        {"metric": "simulations", "value": float(len(terminal))},
        {"metric": "start_value", "value": float(start_value)},
        {"metric": "mean_terminal_value", "value": float(terminal.mean())},
        {"metric": "median_terminal_value", "value": float(terminal.median())},
        {"metric": "expected_return", "value": float(terminal.mean() / start_value - 1.0)},
        {"metric": "median_return", "value": float(terminal.median() / start_value - 1.0)},
        {"metric": "std_terminal_return", "value": float((terminal / start_value - 1.0).std())},
    ]
    for q in quantiles:
        q_label = f"terminal_q{int(round(q * 100)):02d}"
        r_label = f"return_q{int(round(q * 100)):02d}"
        q_value = float(terminal.quantile(q))
        rows.append({"metric": q_label, "value": q_value})
        rows.append({"metric": r_label, "value": float(q_value / start_value - 1.0)})
    return pd.DataFrame(rows)


def monte_carlo_probability_table(
    paths: np.ndarray,
    start_value: float,
    stop: float | None = None,
    target: float | None = None,
    return_thresholds: tuple[float, ...] = (-0.10, -0.05, 0.0, 0.05, 0.10, 0.15),
) -> pd.DataFrame:
    if paths.ndim != 2 or paths.shape[0] == 0 or paths.shape[1] == 0:
        raise ValueError("paths must be a non-empty 2D array")

    terminal = pd.Series(paths[:, -1], dtype=float, name="terminal_value")
    terminal_return = terminal / float(start_value) - 1.0

    rows: list[dict[str, float | str]] = []
    for threshold in return_thresholds:
        direction = ">=" if threshold >= 0 else "<="
        probability = float((terminal_return >= threshold).mean()) if threshold >= 0 else float((terminal_return <= threshold).mean())
        rows.append(
            {
                "scenario": f"Terminal return {direction} {threshold:.0%}",
                "probability": probability,
                "odds_pct": probability * 100.0,
            }
        )

    rows.extend(
        [
            {
                "scenario": "Terminal above entry",
                "probability": float((terminal > float(start_value)).mean()),
                "odds_pct": float((terminal > float(start_value)).mean()) * 100.0,
            },
            {
                "scenario": "Terminal below entry",
                "probability": float((terminal < float(start_value)).mean()),
                "odds_pct": float((terminal < float(start_value)).mean()) * 100.0,
            },
        ]
    )

    if target is not None:
        hit_target = (paths >= float(target)).any(axis=1)
        terminal_above_target = terminal >= float(target)
        rows.extend(
            [
                {
                    "scenario": "Hit target any time",
                    "probability": float(hit_target.mean()),
                    "odds_pct": float(hit_target.mean()) * 100.0,
                },
                {
                    "scenario": "Finish above target",
                    "probability": float(terminal_above_target.mean()),
                    "odds_pct": float(terminal_above_target.mean()) * 100.0,
                },
            ]
        )

    if stop is not None:
        hit_stop = (paths <= float(stop)).any(axis=1)
        terminal_below_stop = terminal <= float(stop)
        rows.extend(
            [
                {
                    "scenario": "Hit stop any time",
                    "probability": float(hit_stop.mean()),
                    "odds_pct": float(hit_stop.mean()) * 100.0,
                },
                {
                    "scenario": "Finish below stop",
                    "probability": float(terminal_below_stop.mean()),
                    "odds_pct": float(terminal_below_stop.mean()) * 100.0,
                },
            ]
        )

    return pd.DataFrame(rows).sort_values("probability", ascending=False).reset_index(drop=True)
