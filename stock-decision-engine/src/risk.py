from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(close: pd.Series) -> pd.Series:
    peak = close.cummax()
    return close / peak - 1.0


def downside_deviation(returns: pd.Series, trading_days: int = 252) -> float:
    downside = returns[returns < 0]
    return float(downside.std(ddof=1) * np.sqrt(trading_days)) if len(downside) else 0.0


def var_cvar(returns: pd.Series, level: float = 0.95) -> tuple[float, float]:
    r = returns.dropna()
    if r.empty:
        return np.nan, np.nan
    cutoff = float(np.quantile(r, 1.0 - level))
    tail = r[r <= cutoff]
    return cutoff, float(tail.mean()) if len(tail) else cutoff


def ratios(
    stock_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_annual: float = 0.0,
    trading_days: int = 252,
) -> dict[str, float]:
    aligned = pd.concat([stock_returns, benchmark_returns], axis=1, keys=["stock", "bench"]).dropna()
    if len(aligned) < 20:
        return {k: np.nan for k in ["beta", "jensen_alpha", "sharpe", "sortino", "treynor", "information_ratio", "tracking_error", "calmar"]}
    rf_daily = risk_free_annual / trading_days
    excess = aligned["stock"] - rf_daily
    bench_excess = aligned["bench"] - rf_daily
    beta = float(aligned["stock"].cov(aligned["bench"]) / aligned["bench"].var()) if aligned["bench"].var() else np.nan
    alpha_daily = float(excess.mean() - beta * bench_excess.mean()) if np.isfinite(beta) else np.nan
    tracking = aligned["stock"] - aligned["bench"]
    vol = aligned["stock"].std(ddof=1) * np.sqrt(trading_days)
    dd = downside_deviation(aligned["stock"], trading_days)
    curve = (1.0 + aligned["stock"]).cumprod()
    mdd = abs(float((curve / curve.cummax() - 1.0).min()))
    ann_ret = float((1.0 + aligned["stock"]).prod() ** (trading_days / len(aligned)) - 1.0)
    return {
        "beta": beta,
        "jensen_alpha": alpha_daily * trading_days,
        "sharpe": float((excess.mean() * trading_days) / vol) if vol else np.nan,
        "sortino": float((excess.mean() * trading_days) / dd) if dd else np.nan,
        "treynor": float((ann_ret - risk_free_annual) / beta) if beta and np.isfinite(beta) else np.nan,
        "information_ratio": float(tracking.mean() / tracking.std(ddof=1) * np.sqrt(trading_days)) if tracking.std(ddof=1) else np.nan,
        "tracking_error": float(tracking.std(ddof=1) * np.sqrt(trading_days)),
        "calmar": float(ann_ret / mdd) if mdd else np.nan,
    }


def rolling_capm(stock_returns: pd.Series, benchmark_returns: pd.Series, window: int = 60, trading_days: int = 252) -> pd.DataFrame:
    aligned = pd.concat([stock_returns, benchmark_returns], axis=1, keys=["stock", "bench"]).dropna()
    cov = aligned["stock"].rolling(window, min_periods=max(20, window // 2)).cov(aligned["bench"])
    var = aligned["bench"].rolling(window, min_periods=max(20, window // 2)).var()
    beta = cov / var.replace(0, np.nan)
    alpha = (aligned["stock"].rolling(window, min_periods=max(20, window // 2)).mean() - beta * aligned["bench"].rolling(window, min_periods=max(20, window // 2)).mean()) * trading_days
    corr = aligned["stock"].rolling(window, min_periods=max(20, window // 2)).corr(aligned["bench"])
    return pd.DataFrame({"date": aligned.index, "rolling_alpha": alpha.values, "rolling_beta": beta.values, "rolling_corr": corr.values})
