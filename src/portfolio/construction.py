from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform
from scipy.optimize import minimize


def _as_weight_series(values, index=None, name: str = "weight") -> pd.Series:
    if isinstance(values, pd.Series):
        series = values.astype(float).copy()
        series.name = name
        return series
    series = pd.Series(values, index=index, dtype=float, name=name)
    return series


def _normalize_weights(weights: pd.Series, min_weight: float = 0.0) -> pd.Series:
    out = weights.fillna(0.0).clip(lower=min_weight)
    total = float(out.sum())
    if total <= 0:
        raise ValueError("Weights must sum to a positive value")
    return out / total


def equal_weight_allocation(symbols: list[str] | pd.Index | pd.Series) -> pd.Series:
    index = pd.Index(symbols, dtype="object")
    return _normalize_weights(pd.Series(1.0, index=index, dtype=float, name="weight"))


def inverse_volatility_allocation(volatility: pd.Series, floor: float = 1e-8) -> pd.Series:
    vol = _as_weight_series(volatility, name="volatility").replace(0, np.nan).abs().clip(lower=floor)
    inv_vol = 1.0 / vol
    return _normalize_weights(inv_vol.rename("weight"))


def shrink_covariance(covariance: pd.DataFrame, shrinkage: float = 0.1) -> pd.DataFrame:
    cov = covariance.astype(float).copy()
    if cov.empty:
        return cov
    diagonal = np.diag(np.diag(cov.to_numpy()))
    shrunk = (1 - shrinkage) * cov.to_numpy() + shrinkage * diagonal
    return pd.DataFrame(shrunk, index=cov.index, columns=cov.columns)


def portfolio_risk_contributions(weights: pd.Series, covariance: pd.DataFrame) -> pd.Series:
    w = _normalize_weights(_as_weight_series(weights, index=covariance.index))
    cov = covariance.loc[w.index, w.index].astype(float)
    marginal = cov.to_numpy() @ w.to_numpy()
    portfolio_var = float(w.to_numpy().T @ marginal)
    if portfolio_var <= 0:
        raise ValueError("Portfolio variance must be positive")
    contributions = w.to_numpy() * marginal / portfolio_var
    return pd.Series(contributions, index=w.index, name="risk_contribution")


def risk_parity_allocation(
    covariance: pd.DataFrame,
    max_iter: int = 500,
    tol: float = 1e-8,
    min_weight: float = 1e-6,
) -> pd.Series:
    cov = covariance.astype(float).copy()
    if cov.empty:
        return pd.Series(dtype=float, name="weight")
    weights = equal_weight_allocation(cov.index).clip(lower=min_weight)
    target = 1.0 / len(weights)

    for _ in range(max_iter):
        rc = portfolio_risk_contributions(weights, cov)
        diff = rc - target
        if float(diff.abs().max()) < tol:
            break
        adjust = np.where(rc.to_numpy() > 0, target / rc.to_numpy(), 1.0)
        weights = _normalize_weights(pd.Series(weights.to_numpy() * adjust, index=weights.index), min_weight=min_weight)

    return weights.rename("weight")


def _cov_to_corr(cov: pd.DataFrame) -> pd.DataFrame:
    std = np.sqrt(np.diag(cov.to_numpy()))
    denom = np.outer(std, std)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = cov.to_numpy() / denom
    corr = np.where(np.isfinite(corr), corr, 0.0)
    corr = np.clip(corr, -1, 1)
    np.fill_diagonal(corr, 1.0)
    return pd.DataFrame(corr, index=cov.index, columns=cov.columns)


def _sanitize_covariance(covariance: pd.DataFrame) -> pd.DataFrame:
    cov = covariance.astype(float).replace([np.inf, -np.inf], np.nan).copy()
    cov = cov.dropna(axis=0, how="all").dropna(axis=1, how="all")
    common_index = cov.index.intersection(cov.columns)
    cov = cov.loc[common_index, common_index]
    if cov.empty:
        return cov

    cov = cov.combine_first(cov.T)
    cov = ((cov + cov.T) / 2).astype(float)

    diag = pd.Series(np.diag(cov.to_numpy()), index=cov.index, dtype=float)
    valid = diag.replace([np.inf, -np.inf], np.nan).fillna(0.0) > 0
    cov = cov.loc[valid.index[valid], valid.index[valid]]
    if cov.empty:
        return cov

    cov = cov.fillna(0.0)
    cov_values = cov.to_numpy(dtype=float)
    cov_values = np.where(np.isfinite(cov_values), cov_values, 0.0)
    cov_values = (cov_values + cov_values.T) / 2
    diag_values = np.diag(cov_values)
    diag_floor = np.where(np.isfinite(diag_values) & (diag_values > 1e-12), diag_values, 1e-12)
    np.fill_diagonal(cov_values, diag_floor)
    return pd.DataFrame(cov_values, index=cov.index, columns=cov.columns)


def _get_quasi_diag(link: np.ndarray) -> list[int]:
    sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
    num_items = int(link[-1, 3])
    while sort_ix.max() >= num_items:
        sort_ix.index = range(0, sort_ix.shape[0] * 2, 2)
        df0 = sort_ix[sort_ix >= num_items]
        i = df0.index
        j = (df0.values - num_items).astype(int)
        sort_ix.loc[i] = link[j, 0]
        df1 = pd.Series(link[j, 1], index=i + 1)
        sort_ix = pd.concat([sort_ix, df1]).sort_index()
        sort_ix.index = range(sort_ix.shape[0])
    return sort_ix.astype(int).tolist()


def _cluster_variance(cov: pd.DataFrame, cluster_items: list[str]) -> float:
    cluster_cov = cov.loc[cluster_items, cluster_items]
    ivp = inverse_volatility_allocation(pd.Series(np.sqrt(np.diag(cluster_cov)), index=cluster_cov.index))
    weights = ivp.to_numpy()
    return float(weights.T @ cluster_cov.to_numpy() @ weights)


def hierarchical_risk_parity_allocation(
    returns: pd.DataFrame | None = None,
    covariance: pd.DataFrame | None = None,
    linkage_method: str = "single",
) -> pd.Series:
    if covariance is None:
        if returns is None or returns.empty:
            return pd.Series(dtype=float, name="weight")
        clean_returns = returns.replace([np.inf, -np.inf], np.nan).copy()
        clean_returns = clean_returns.dropna(axis=1, how="all")
        if clean_returns.empty:
            return pd.Series(dtype=float, name="weight")
        covariance = clean_returns.cov()

    cov = _sanitize_covariance(covariance)
    if cov.empty:
        return pd.Series(dtype=float, name="weight")
    if len(cov.index) == 1:
        return equal_weight_allocation(cov.index)

    corr = _cov_to_corr(cov)
    corr = corr.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    corr = ((corr + corr.T) / 2).clip(-1.0, 1.0)
    np.fill_diagonal(corr.values, 1.0)

    valid_corr = pd.Series(np.isfinite(corr.to_numpy()).all(axis=1), index=corr.index)
    corr = corr.loc[valid_corr[valid_corr].index, valid_corr[valid_corr].index]
    cov = cov.loc[corr.index, corr.columns]
    if corr.empty:
        return pd.Series(dtype=float, name="weight")
    if len(corr.index) == 1:
        return equal_weight_allocation(corr.index)

    distance = np.sqrt((1 - corr) / 2)
    distance = distance.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    distance = ((distance + distance.T) / 2).clip(lower=0.0)
    np.fill_diagonal(distance.values, 0.0)
    link = linkage(squareform(distance.to_numpy(), checks=False), method=linkage_method)
    sort_ix = _get_quasi_diag(link)
    sorted_index = corr.index[sort_ix].tolist()

    weights = pd.Series(1.0, index=sorted_index, dtype=float)
    clusters = [sorted_index]
    while clusters:
        cluster = clusters.pop(0)
        if len(cluster) <= 1:
            continue
        split = len(cluster) // 2
        left = cluster[:split]
        right = cluster[split:]
        left_var = _cluster_variance(cov, left)
        right_var = _cluster_variance(cov, right)
        alpha = 1 - left_var / (left_var + right_var)
        weights[left] *= alpha
        weights[right] *= 1 - alpha
        clusters.extend([left, right])

    return _normalize_weights(weights.rename("weight")).reindex(cov.index)


def maximize_sharpe_ratio(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    risk_free_rate: float = 0.0,
    max_weight: float = 0.25,
) -> pd.Series:
    """Find the portfolio weights that maximize the Sharpe ratio."""
    cov = _sanitize_covariance(covariance)
    if cov.empty or expected_returns.empty:
        return pd.Series(dtype=float, name="weight")

    # Align indices
    common_idx = cov.index.intersection(expected_returns.index)
    cov = cov.loc[common_idx, common_idx]
    er = expected_returns.loc[common_idx]
    n = len(common_idx)
    if n == 0:
        return pd.Series(dtype=float, name="weight")

    # Objective function: negative Sharpe ratio
    def objective(w):
        port_ret = float(w.T @ er.to_numpy())
        port_vol = float(np.sqrt(w.T @ cov.to_numpy() @ w))
        if port_vol <= 0:
            return 0.0
        return -(port_ret - risk_free_rate) / port_vol

    # Constraints: weights sum to 1.0
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}
    # Bounds: w in [0.0, max_weight]
    bounds = tuple((0.0, max_weight) for _ in range(n))
    # Initial guess: equal weight
    init_guess = np.ones(n) / n

    res = minimize(objective, init_guess, method="SLSQP", bounds=bounds, constraints=constraints)
    if not res.success:
        return equal_weight_allocation(common_idx)

    return _normalize_weights(pd.Series(res.x, index=common_idx, name="weight"))


def efficient_frontier(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    points: int = 15,
    max_weight: float = 0.25,
) -> list[dict[str, float | pd.Series]]:
    """Generate points along the efficient frontier by minimizing variance for target returns."""
    cov = _sanitize_covariance(covariance)
    if cov.empty or expected_returns.empty:
        return []

    common_idx = cov.index.intersection(expected_returns.index)
    cov = cov.loc[common_idx, common_idx]
    er = expected_returns.loc[common_idx]
    n = len(common_idx)
    if n == 0:
        return []

    min_ret = float(er.min())
    max_ret = float(er.max())
    # Generate linear spacing of returns between min and max expected return
    target_returns = np.linspace(min_ret, max_ret, points)

    frontier_points = []

    # Minimize variance objective
    def min_var_obj(w):
        return float(w.T @ cov.to_numpy() @ w)

    for target in target_returns:
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "eq", "fun": lambda w: float(w.T @ er.to_numpy()) - target}
        ]
        bounds = tuple((0.0, max_weight) for _ in range(n))
        init_guess = np.ones(n) / n

        res = minimize(min_var_obj, init_guess, method="SLSQP", bounds=bounds, constraints=constraints)
        if res.success:
            weights = pd.Series(res.x, index=common_idx, name="weight")
            port_vol = float(np.sqrt(weights.T @ cov.to_numpy() @ weights))
            frontier_points.append({
                "target_return": target,
                "volatility": port_vol,
                "weights": weights
            })

    return frontier_points
