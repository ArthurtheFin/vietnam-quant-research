from __future__ import annotations

import numpy as np
import pandas as pd


def _clip_quantile_edges(series: pd.Series, lower_q: float = 0.01, upper_q: float = 0.99) -> tuple[float, float]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return -1.0, 1.0
    lo = float(clean.quantile(lower_q))
    hi = float(clean.quantile(upper_q))
    if not np.isfinite(lo) or not np.isfinite(hi) or lo == hi:
        center = float(clean.median()) if not clean.empty else 0.0
        spread = float(clean.std(ddof=0)) if len(clean) > 1 else 1.0
        spread = spread if np.isfinite(spread) and spread > 0 else 1.0
        lo = center - 3 * spread
        hi = center + 3 * spread
    return lo, hi


def rolling_shannon_entropy(
    series: pd.Series,
    window: int = 63,
    n_bins: int = 24,
    lower_q: float = 0.01,
    upper_q: float = 0.99,
    normalize: bool = True,
) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    clean = values.dropna()
    out = pd.Series(np.nan, index=values.index, dtype=float)
    if len(clean) < window or n_bins < 2:
        return out

    # Compute bin edges per-window to avoid look-ahead bias (no global edges)
    h_max = np.log(int(n_bins))

    for end in range(window, len(values) + 1):
        sample = values.iloc[end - window : end].dropna()
        if len(sample) < window:
            continue
        counts, _ = np.histogram(sample, bins=n_bins)
        total = counts.sum()
        if total <= 0:
            continue
        probs = counts / total
        probs = probs[probs > 0]
        entropy = float(-np.sum(probs * np.log(probs)))
        if normalize and h_max > 0:
            entropy /= h_max
        out.iloc[end - 1] = entropy
    return out


def add_entropy_features(
    df: pd.DataFrame,
    windows: list[int] | None = None,
    return_col: str = "return_1d",
    price_col: str = "close",
    symbol_col: str = "symbol",
    date_col: str = "date",
    n_bins: int = 24,
    classify: bool = True,
) -> pd.DataFrame:
    windows = windows or [21, 63, 126]
    out = df.sort_values([symbol_col, date_col]).copy()
    out[date_col] = pd.to_datetime(out[date_col])
    if return_col not in out.columns:
        out[return_col] = out.groupby(symbol_col)[price_col].pct_change()

    for window in windows:
        entropy_col = f"entropy_{window}d"
        out[entropy_col] = (
            out.groupby(symbol_col, group_keys=False)[return_col]
            .apply(lambda s: rolling_shannon_entropy(s, window=window, n_bins=n_bins))
        )

    if classify:
        base_col = f"entropy_{windows[0]}d"
        if base_col in out.columns:
            out["entropy_regime"] = classify_entropy_regime(out[base_col])
            out["entropy_regime_shift"] = detect_entropy_regime_shift(out[base_col])
    return out


def classify_entropy_regime(
    entropy_series: pd.Series,
    low_threshold: float = 0.35,
    high_threshold: float = 0.70,
) -> pd.Series:
    s = pd.to_numeric(entropy_series, errors="coerce")
    out = pd.Series("Unknown", index=s.index, dtype=object)
    out.loc[s.notna() & (s <= low_threshold)] = "Structured"
    out.loc[s.notna() & (s > low_threshold) & (s < high_threshold)] = "Transitional"
    out.loc[s.notna() & (s >= high_threshold)] = "Chaotic"
    return out


def detect_entropy_regime_shift(
    entropy_series: pd.Series,
    lookback: int = 10,
    shift_threshold: float = 0.12,
) -> pd.Series:
    s = pd.to_numeric(entropy_series, errors="coerce")
    delta = s - s.shift(int(lookback))
    labels = pd.Series("Stable", index=s.index, dtype=object)
    labels.loc[delta >= shift_threshold] = "Entropy Expansion"
    labels.loc[delta <= -shift_threshold] = "Entropy Compression"
    labels.loc[s.isna()] = "Unknown"
    return labels


def build_market_entropy_profile(
    df: pd.DataFrame,
    date_col: str = "date",
    symbol_col: str = "symbol",
    return_col: str = "return_1d",
    price_col: str = "close",
    windows: list[int] | None = None,
    n_bins: int = 24,
) -> pd.DataFrame:
    windows = windows or [21, 63, 126]
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    if return_col not in out.columns:
        out = out.sort_values([symbol_col, date_col]).copy()
        out[return_col] = out.groupby(symbol_col)[price_col].pct_change()

    market_returns = (
        out.groupby(date_col)[return_col]
        .mean()
        .rename("market_proxy_return_1d")
        .sort_index()
    )
    breadth = (
        out.assign(_up=lambda x: pd.to_numeric(x[return_col], errors="coerce") > 0)
        .groupby(date_col)["_up"]
        .mean()
        .rename("advance_ratio")
        .sort_index()
    )
    result = pd.concat([market_returns, breadth], axis=1).reset_index()

    for window in windows:
        result[f"market_entropy_{window}d"] = rolling_shannon_entropy(
            result["market_proxy_return_1d"],
            window=window,
            n_bins=n_bins,
        )
    base_col = f"market_entropy_{windows[0]}d"
    result["market_entropy_regime"] = classify_entropy_regime(result[base_col])
    result["market_entropy_shift"] = detect_entropy_regime_shift(result[base_col])
    return result
