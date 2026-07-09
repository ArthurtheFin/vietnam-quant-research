from __future__ import annotations

import numpy as np
import pandas as pd


def _resolve_volatility_percentile(row: pd.Series) -> float | None:
    for col in ("volatility_percentile", "realized_vol_20d_percentile", "ewma_vol_20d_percentile"):
        value = row.get(col, None)
        if pd.notna(value):
            return value
    return None


def add_index_trend_features(
    market_features: pd.DataFrame,
    benchmark: pd.DataFrame | None,
    drawdown_window: int = 60,
    price_col: str = "close",
) -> pd.DataFrame:
    """Merge real VNINDEX price-derived signals into market_features:
    index_drawdown_pct (rolling drawdown off its own recent high -- a direct,
    model-free crash-severity signal) and index_above_ma50/ma200.

    Bug fix: index_above_ma50/index_above_ma200 were referenced by
    classify_market_regime but calculate_market_breadth only ever aggregates
    STOCK-level features, never the index price itself -- so those two
    conditions were always False, capping the max achievable score at 3/5 and
    making "Risk-on" structurally unreachable (confirmed: 0 Risk-on days in
    the full 2020-2026 history). This restores real values for both.
    """
    out = market_features.copy()
    out["date"] = pd.to_datetime(out["date"])

    if benchmark is None or benchmark.empty or price_col not in benchmark.columns:
        out["index_drawdown_pct"] = np.nan
        out["index_above_ma50"] = False
        out["index_above_ma200"] = False
        return out

    bench = benchmark[["date", price_col]].copy()
    bench["date"] = pd.to_datetime(bench["date"])
    bench = bench.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    bench["rolling_high"] = bench[price_col].rolling(drawdown_window, min_periods=20).max()
    bench["index_drawdown_pct"] = bench[price_col] / bench["rolling_high"] - 1.0
    bench["index_ma50"] = bench[price_col].rolling(50, min_periods=20).mean()
    bench["index_ma200"] = bench[price_col].rolling(200, min_periods=50).mean()
    bench["index_above_ma50"] = bench[price_col] > bench["index_ma50"]
    bench["index_above_ma200"] = bench[price_col] > bench["index_ma200"]

    out = out.merge(
        bench[["date", "index_drawdown_pct", "index_above_ma50", "index_above_ma200"]],
        on="date",
        how="left",
    )
    out["index_above_ma50"] = out["index_above_ma50"].fillna(False)
    out["index_above_ma200"] = out["index_above_ma200"].fillna(False)
    return out


def classify_market_regime(row: pd.Series) -> str:
    """Legacy 3-tier breadth score (Risk-on/Neutral/Risk-off). Formula
    unchanged from before; only the upstream index_above_ma50/200 data feed
    was fixed (see add_index_trend_features) so "Risk-on" is reachable again.
    """
    score = 0
    if row.get("index_above_ma50", False):
        score += 1
    if row.get("index_above_ma200", False):
        score += 1
    if row.get("pct_above_ma50", 0) >= 0.55:
        score += 1
    if row.get("advance_decline_ratio", 0) >= 1.2:
        score += 1
    vol_pct = _resolve_volatility_percentile(row)
    if pd.notna(vol_pct) and vol_pct < 0.8:
        score += 1
    if score >= 4:
        return "Risk-on"
    if score >= 2:
        return "Neutral"
    return "Risk-off"


def classify_crash_severity(
    row: pd.Series,
    correction_threshold: float = -0.10,
    crash_threshold: float = -0.20,
) -> str:
    """Direct, model-free severity tier from the index's own drawdown off its
    rolling high -- distinguishes a genuine structural crash (2022-style,
    real data: min drawdown -29.2%, 51.8% of days beyond -10%) from ordinary
    correction/chop (2023-2026: max drawdown -8.9% to -18.1%, 0-16% of days
    beyond -10%). The legacy breadth-threshold score conflates both into one
    oversized "Risk-off" bucket (75% of all days) that cannot tell them apart.
    """
    dd = row.get("index_drawdown_pct")
    if pd.isna(dd):
        return "Unknown"
    if dd <= crash_threshold:
        return "Crash"
    if dd <= correction_threshold:
        return "Correction"
    return "Normal"


def classify_breakout_signal(
    row: pd.Series,
    near_high_threshold: float = -0.03,
    breadth_threshold: float = 0.60,
    ad_ratio_threshold: float = 1.3,
    volume_ratio_threshold: float = 1.2,
) -> str:
    """Symmetric counterpart to crash severity: index near its own rolling
    high AND breadth/advance-decline/volume all confirming expansion -- a
    genuine breakout wave, not just an ordinary decent day. Breadth/AD ratio
    inputs use the smoothed (EMA) columns when available to avoid firing on
    single-day noise (see add_market_regime's persistence filter).
    """
    dd = row.get("index_drawdown_pct")
    if pd.isna(dd) or dd < near_high_threshold:
        return "Normal"
    pct_ma50 = row.get("pct_above_ma50_smooth", row.get("pct_above_ma50", 0))
    ad_ratio = row.get("advance_decline_ratio_smooth", row.get("advance_decline_ratio", 0))
    vol_ratio = row.get("up_down_volume_ratio", 0)
    if pct_ma50 >= breadth_threshold and ad_ratio >= ad_ratio_threshold and vol_ratio >= volume_ratio_threshold:
        return "Breakout"
    return "Normal"


def add_market_regime(
    market_features: pd.DataFrame,
    benchmark: pd.DataFrame | None = None,
    drawdown_window: int = 60,
    smooth_span: int = 5,
) -> pd.DataFrame:
    """Adds market_regime (legacy 3-tier), crash_severity (Normal/Correction/
    Crash), and breakout_signal (Normal/Breakout) columns.

    benchmark (optional, e.g. benchmark_vnindex.parquet or raw VNINDEX OHLC
    with a "close" column): without it, crash_severity/breakout_signal degrade
    to "Unknown"/"Normal" and market_regime keeps its pre-fix behavior
    (index_above_ma50/200 always False) -- fully backward compatible.

    smooth_span: EMA span applied to the noisiest breadth inputs
    (pct_above_ma50, advance_decline_ratio) before breakout classification --
    a persistence filter. Without it, market_regime flips ~27% of days
    (Neutral<->Risk-off) on raw single-day breadth noise (see strategy
    research); breakout_signal uses the smoothed columns to avoid the same.
    market_regime itself still uses raw (unsmoothed) inputs to stay
    backward-compatible with existing consumers (stealth_accumulation's
    regime_pass filter, meta_ranking's regime_score, dashboards).
    """
    out = market_features.sort_values("date").reset_index(drop=True).copy()
    out = add_index_trend_features(out, benchmark, drawdown_window=drawdown_window)

    if "pct_above_ma50" in out.columns:
        out["pct_above_ma50_smooth"] = out["pct_above_ma50"].ewm(span=smooth_span, min_periods=1).mean()
    if "advance_decline_ratio" in out.columns:
        out["advance_decline_ratio_smooth"] = out["advance_decline_ratio"].ewm(span=smooth_span, min_periods=1).mean()

    out["market_regime"] = out.apply(classify_market_regime, axis=1)
    out["crash_severity"] = out.apply(classify_crash_severity, axis=1)
    out["breakout_signal"] = out.apply(classify_breakout_signal, axis=1)
    return out
