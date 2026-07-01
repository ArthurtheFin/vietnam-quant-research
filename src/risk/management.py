from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.risk_model import conditional_value_at_risk, value_at_risk


def _to_weight_series(weights, index=None) -> pd.Series:
    if isinstance(weights, pd.Series):
        out = weights.astype(float).copy()
    else:
        out = pd.Series(weights, index=index, dtype=float)
    total = float(out.sum())
    if total <= 0:
        raise ValueError("Weights must sum to a positive value")
    return out / total


def portfolio_return_series(return_matrix: pd.DataFrame, weights: pd.Series) -> pd.Series:
    w = _to_weight_series(weights, index=return_matrix.columns)
    aligned = return_matrix.reindex(columns=w.index).fillna(0.0)
    portfolio_returns = aligned.mul(w, axis=1).sum(axis=1)
    portfolio_returns.name = "portfolio_return"
    return portfolio_returns


def portfolio_nav_series(portfolio_returns: pd.Series, start_nav: float = 1.0) -> pd.Series:
    nav = start_nav * (1 + portfolio_returns.fillna(0.0)).cumprod()
    nav.name = "portfolio_nav"
    return nav


def rolling_drawdown(nav: pd.Series) -> pd.Series:
    running_peak = nav.cummax()
    drawdown = nav / running_peak - 1
    drawdown.name = "drawdown"
    return drawdown


def annualized_return(portfolio_returns: pd.Series, periods_per_year: int = 252) -> float:
    r = portfolio_returns.dropna()
    if r.empty:
        return float("nan")
    total_return = float((1 + r).prod())
    years = len(r) / periods_per_year
    if years <= 0:
        return float("nan")
    return total_return ** (1 / years) - 1


def annualized_volatility(portfolio_returns: pd.Series, periods_per_year: int = 252) -> float:
    r = portfolio_returns.dropna()
    if r.empty:
        return float("nan")
    return float(r.std(ddof=0) * np.sqrt(periods_per_year))


def sharpe_ratio(portfolio_returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    r = portfolio_returns.dropna()
    if r.empty:
        return float("nan")
    excess = r - risk_free_rate / periods_per_year
    vol = excess.std(ddof=0)
    if vol == 0:
        return float("nan")
    return float(excess.mean() / vol * np.sqrt(periods_per_year))


def rolling_sharpe_series(
    portfolio_returns: pd.Series,
    window: int = 63,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> pd.Series:
    r = portfolio_returns.astype(float)
    excess = r - risk_free_rate / periods_per_year
    mean = excess.rolling(window).mean()
    vol = excess.rolling(window).std(ddof=0)
    sharpe = mean / vol.replace(0, np.nan) * np.sqrt(periods_per_year)
    sharpe.name = f"rolling_sharpe_{window}d"
    return sharpe


def expanding_sharpe_series(
    portfolio_returns: pd.Series,
    min_periods: int = 21,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> pd.Series:
    r = portfolio_returns.astype(float)
    excess = r - risk_free_rate / periods_per_year
    mean = excess.expanding(min_periods=min_periods).mean()
    vol = excess.expanding(min_periods=min_periods).std(ddof=0)
    sharpe = mean / vol.replace(0, np.nan) * np.sqrt(periods_per_year)
    sharpe.name = "expanding_sharpe"
    return sharpe


def sharpe_stability_report(
    portfolio_returns: pd.Series,
    min_periods: int = 21,
    rolling_window: int = 63,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> dict[str, float]:
    expanding = expanding_sharpe_series(
        portfolio_returns,
        min_periods=min_periods,
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )
    rolling = rolling_sharpe_series(
        portfolio_returns,
        window=rolling_window,
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year,
    )
    valid_expanding = expanding.dropna()
    valid_rolling = rolling.dropna()
    terminal = float(valid_expanding.iloc[-1]) if not valid_expanding.empty else float("nan")
    rolling_std = float(valid_rolling.std(ddof=0)) if len(valid_rolling) > 1 else float("nan")
    stability = float(1 / (1 + rolling_std)) if np.isfinite(rolling_std) else float("nan")
    return {
        "expanding_sharpe_latest": terminal,
        "rolling_sharpe_latest": float(valid_rolling.iloc[-1]) if not valid_rolling.empty else float("nan"),
        "rolling_sharpe_std": rolling_std,
        "sharpe_stability_score": stability,
        "track_record_days": int(portfolio_returns.dropna().shape[0]),
    }


def sortino_ratio(portfolio_returns: pd.Series, target_rate: float = 0.0, periods_per_year: int = 252) -> float:
    r = portfolio_returns.dropna()
    if r.empty:
        return float("nan")
    target_per_period = target_rate / periods_per_year
    downside = np.minimum(r - target_per_period, 0)
    downside_vol = np.sqrt(np.mean(downside**2))
    if downside_vol == 0:
        return float("nan")
    return float((r.mean() - target_per_period) / downside_vol * np.sqrt(periods_per_year))


def max_drawdown(nav: pd.Series) -> float:
    dd = rolling_drawdown(nav)
    if dd.empty:
        return float("nan")
    return float(dd.min())


def calmar_ratio(portfolio_returns: pd.Series, periods_per_year: int = 252) -> float:
    nav = portfolio_nav_series(portfolio_returns)
    mdd = abs(max_drawdown(nav))
    if mdd == 0 or np.isnan(mdd):
        return float("nan")
    return float(annualized_return(portfolio_returns, periods_per_year=periods_per_year) / mdd)


def turnover_from_weight_history(weight_history: pd.DataFrame) -> float:
    if weight_history.empty or len(weight_history) < 2:
        return 0.0
    aligned = weight_history.fillna(0.0)
    turnover = aligned.diff().abs().sum(axis=1).dropna() / 2
    return float(turnover.mean())


def concentration_metrics(weights: pd.Series) -> dict[str, float]:
    w = _to_weight_series(weights)
    herfindahl = float((w**2).sum())
    return {
        "max_weight": float(w.max()),
        "effective_n": float(1 / herfindahl) if herfindahl > 0 else float("nan"),
        "herfindahl_index": herfindahl,
    }


def portfolio_beta(portfolio_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    if aligned.empty or aligned.iloc[:, 1].var(ddof=0) == 0:
        return float("nan")
    cov = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
    var = aligned.iloc[:, 1].var(ddof=1)
    return float(cov / var)


def apply_symbol_caps(weights: pd.Series, max_weight: float = 0.25) -> pd.Series:
    capped = weights.clip(upper=max_weight)
    return _to_weight_series(capped)


def apply_volatility_target(
    weights: pd.Series,
    covariance: pd.DataFrame,
    target_volatility: float = 0.12,
    max_gross_leverage: float = 1.5,
) -> tuple[pd.Series, float]:
    w = _to_weight_series(weights, index=covariance.index)
    cov = covariance.loc[w.index, w.index].astype(float)
    current_vol = float(np.sqrt(w.to_numpy().T @ cov.to_numpy() @ w.to_numpy()) * np.sqrt(252))
    if current_vol <= 0 or np.isnan(current_vol):
        return w, 1.0
    scale = min(target_volatility / current_vol, max_gross_leverage)
    scaled = w * scale
    return scaled.rename("weight"), float(scale)


def exposure_from_drawdown(
    current_drawdown: float,
    schedule: list[tuple[float, float]] | None = None,
) -> float:
    schedule = schedule or [
        (-0.20, 0.25),
        (-0.15, 0.50),
        (-0.10, 0.75),
        (-0.05, 0.90),
    ]
    for threshold, exposure in sorted(schedule):
        if current_drawdown <= threshold:
            return float(exposure)
    return 1.0


def apply_drawdown_overlay(
    weights: pd.Series,
    current_drawdown: float,
    schedule: list[tuple[float, float]] | None = None,
) -> tuple[pd.Series, float]:
    exposure = exposure_from_drawdown(current_drawdown, schedule=schedule)
    return (weights * exposure).rename("weight"), exposure


def build_portfolio_risk_report(
    return_matrix: pd.DataFrame,
    weights: pd.Series,
    benchmark_returns: pd.Series | None = None,
    periods_per_year: int = 252,
) -> dict[str, float]:
    portfolio_returns = portfolio_return_series(return_matrix, weights)
    nav = portfolio_nav_series(portfolio_returns)
    report = {
        "annual_return": annualized_return(portfolio_returns, periods_per_year=periods_per_year),
        "annual_volatility": annualized_volatility(portfolio_returns, periods_per_year=periods_per_year),
        "sharpe_ratio": sharpe_ratio(portfolio_returns, periods_per_year=periods_per_year),
        "sortino_ratio": sortino_ratio(portfolio_returns, periods_per_year=periods_per_year),
        "max_drawdown": max_drawdown(nav),
        "calmar_ratio": calmar_ratio(portfolio_returns, periods_per_year=periods_per_year),
        "var_95": value_at_risk(portfolio_returns, level=0.95),
        "cvar_95": conditional_value_at_risk(portfolio_returns, level=0.95),
    }
    report.update(
        sharpe_stability_report(
            portfolio_returns,
            min_periods=min(21, max(2, len(portfolio_returns.dropna()))),
            rolling_window=min(63, max(5, len(portfolio_returns.dropna()))),
            periods_per_year=periods_per_year,
        )
    )
    report.update(concentration_metrics(weights))
    if benchmark_returns is not None:
        report["beta"] = portfolio_beta(portfolio_returns, benchmark_returns)
    return report
