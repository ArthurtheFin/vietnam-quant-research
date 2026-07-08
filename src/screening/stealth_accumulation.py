from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.utils.scoring import (
    deep_merge as _deep_merge,
    safe_divide as _safe_divide,
    clip_score as _clip_score,
    bell_score as _bell_score,
    cross_sectional_score as _cross_sectional_score,
    regime_score as _regime_score,
)


DEFAULT_SCREEN_CONFIG: dict[str, Any] = {
    "name": "stealth_accumulation",
    "universe": {
        "symbols": [],
        "markets": [],
    },
    "windows": {
        "base_window": 20,
        "trend_window": 60,
        "liquidity_window": 20,
        "volume_fast_window": 5,
        "volume_slow_window": 20,
        "market_window": 20,
        "min_history": 60,
    },
    "filters": {
        "min_price": 10.0,
        "min_avg_value_20d": 10_000_000_000.0,
        "allowed_volatility_regimes": ["Low Vol", "Normal Vol", "High Vol", "Stress Vol"],
        "allowed_market_regimes": ["Neutral", "Risk-off", "Unknown"],
        "trend_filters": {
            "require_above_ma50": True,
            "require_above_ma200": True,
            "require_ma50_above_ma200": False,
        },
    },
    "thresholds": {
        "stage_a_min_score": 55.0,
        "stage_b_min_score": 65.0,
        "stage_c_min_score": 75.0,
        "watchlist_min_net_score": 60.0,
        "max_fakeout_risk": 55.0,
    },
    "output": {
        "top_n": 10,
    },
    "sector": {
        "enabled": True,
        "column": "sector",
        "unknown_label": "Unclassified",
        "max_names_per_sector": 2,
        "symbol_map": {},
    },
    "backtest": {
        "top_n": 5,
        "holding_periods": [5, 10, 20],
        "only_watchlist": False,
        "sector_aware": True,
        "benchmark_symbol": "VNINDEX",
        "benchmark_path": "data/processed/benchmark_vnindex.parquet",
        "cost_model": {
            "round_trip_cost": 0.004,
            "base_slippage_bps": 10.0,
            "atr_slippage_weight": 0.05,
            "liquidity_target_avg_value": 25_000_000_000.0,
            "low_liquidity_penalty_bps": 15.0,
            "regime_slippage_multiplier": {
                "Low Vol": 0.85,
                "Normal Vol": 1.00,
                "High Vol": 1.15,
                "Stress Vol": 1.35,
                "Panic Vol": 1.60,
                "Unknown": 1.10,
            },
        },
    },
}


def load_screen_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        raw_cfg = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULT_SCREEN_CONFIG, raw_cfg)


# Utility functions imported from src.utils.scoring:
# _deep_merge, _safe_divide, _clip_score, _bell_score, _cross_sectional_score, _regime_score


def _rolling_compound_return(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window, min_periods=max(5, window // 2)).apply(lambda x: np.prod(1 + x) - 1, raw=True)


def _forward_compound_return_with_delay(s: pd.Series, window: int, delay: int = 1) -> pd.Series:
    shifted = (1 + s.astype(float)).shift(-max(int(delay), 1))
    return shifted.iloc[::-1].rolling(window, min_periods=window).apply(np.prod, raw=True).iloc[::-1] - 1


def _estimate_trade_costs(
    selections: pd.DataFrame,
    cost_model: dict[str, Any] | None = None,
) -> pd.Series:
    if selections.empty:
        return pd.Series(dtype=float)

    model = cost_model or {}
    round_trip_cost = float(model.get("round_trip_cost", 0.0))
    base_slippage = float(model.get("base_slippage_bps", 0.0)) / 10_000
    atr_slippage_weight = float(model.get("atr_slippage_weight", 0.0))
    liquidity_target = float(model.get("liquidity_target_avg_value", 0.0))
    low_liquidity_penalty = float(model.get("low_liquidity_penalty_bps", 0.0)) / 10_000
    regime_multipliers = {str(k): float(v) for k, v in (model.get("regime_slippage_multiplier") or {}).items()}

    atr_pct = selections.get("atr_pct_14", pd.Series(index=selections.index, dtype=float)).fillna(0.0).clip(lower=0.0)
    slippage = base_slippage + atr_pct * atr_slippage_weight
    regime_multiplier = (
        selections.get("volatility_regime", pd.Series(index=selections.index, dtype=object))
        .astype(str)
        .map(regime_multipliers)
        .fillna(1.0)
    )
    slippage = slippage * regime_multiplier

    liquidity_penalty = pd.Series(0.0, index=selections.index, dtype=float)
    if liquidity_target > 0 and low_liquidity_penalty > 0 and "avg_value_20d" in selections.columns:
        avg_value = selections["avg_value_20d"].astype(float).replace(0, np.nan)
        liquidity_gap = ((liquidity_target / avg_value) - 1).clip(lower=0.0, upper=2.0).fillna(0.0)
        liquidity_penalty = liquidity_gap * low_liquidity_penalty

    total_cost = round_trip_cost + slippage + liquidity_penalty
    return total_cost.clip(lower=0.0)


def _read_optional_frame(path: str | Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    if p.is_dir():
        candidates = sorted([candidate for candidate in p.glob("*") if candidate.is_file()])
        if not candidates:
            return pd.DataFrame()
        p = candidates[0]
    if p.suffix == ".parquet":
        return pd.read_parquet(p)
    if p.suffix.lower() in {".csv", ".txt"}:
        return pd.read_csv(p)
    return pd.DataFrame()


def _realized_selection_return(
    price_frame: pd.DataFrame,
    signal_date: pd.Timestamp,
    holding_period: int,
    entry_delay_days: int = 1,
    entry_price_col: str = "open",
    exit_price_col: str = "close",
    signal_price_col: str = "close",
) -> tuple[float, float] | None:
    if price_frame.empty:
        return None

    frame = price_frame.sort_values("date").reset_index(drop=True)
    match_idx = frame.index[frame["date"] == pd.to_datetime(signal_date)]
    if len(match_idx) == 0:
        return None

    signal_idx = int(match_idx[0])
    entry_idx = signal_idx + int(entry_delay_days)
    exit_idx = signal_idx + int(entry_delay_days) + int(holding_period) - 1
    if entry_idx >= len(frame) or exit_idx >= len(frame):
        return None

    entry_price = frame.loc[entry_idx, entry_price_col]
    exit_price = frame.loc[exit_idx, exit_price_col]
    signal_price = frame.loc[signal_idx, signal_price_col] if signal_price_col in frame.columns else np.nan
    if pd.isna(entry_price) or pd.isna(exit_price) or entry_price <= 0:
        return None

    realized_return = float(exit_price / entry_price - 1)
    signal_to_entry_gap = float(entry_price / signal_price - 1) if pd.notna(signal_price) and signal_price > 0 else np.nan
    return realized_return, signal_to_entry_gap


def _prepare_benchmark_frame(
    holding_periods: list[int] | tuple[int, ...],
    screen_df: pd.DataFrame,
    benchmark_df: pd.DataFrame | None = None,
    benchmark_symbol: str = "VNINDEX",
    benchmark_path: str | Path | None = None,
    entry_delay_days: int = 1,
    date_col: str = "date",
    symbol_col: str = "symbol",
    price_col: str = "close",
    return_col: str = "return_1d",
) -> tuple[pd.DataFrame, str]:
    benchmark = pd.DataFrame()
    source = "unavailable"

    if benchmark_df is not None and not benchmark_df.empty:
        benchmark = benchmark_df.copy()
        source = "benchmark_df"
    elif symbol_col in screen_df.columns:
        symbol_mask = screen_df[symbol_col].astype(str).str.upper() == str(benchmark_symbol).upper()
        if symbol_mask.any():
            benchmark = screen_df.loc[symbol_mask].copy()
            source = str(benchmark_symbol).upper()

    if benchmark.empty and benchmark_path:
        benchmark = _read_optional_frame(benchmark_path)
        if not benchmark.empty:
            source = Path(benchmark_path).name

    if benchmark.empty:
        if {"date", "market_proxy_return_1d"}.issubset(screen_df.columns):
            benchmark = (
                screen_df[["date", "market_proxy_return_1d"]]
                .drop_duplicates(subset=["date"])
                .sort_values("date")
                .rename(columns={"market_proxy_return_1d": return_col})
            )
            source = "market_proxy"
        else:
            return pd.DataFrame(), source

    benchmark = benchmark.copy()
    benchmark[date_col] = pd.to_datetime(benchmark[date_col])
    benchmark = benchmark.sort_values(date_col).reset_index(drop=True)

    if return_col not in benchmark.columns:
        if price_col not in benchmark.columns:
            return pd.DataFrame(), source
        benchmark[return_col] = benchmark[price_col].pct_change()

    keep_cols = [date_col, return_col]
    benchmark = benchmark[keep_cols].drop_duplicates(subset=[date_col], keep="last").copy()

    for horizon in holding_periods:
        forward_col = f"benchmark_forward_return_{int(horizon)}d"
        benchmark[forward_col] = _forward_compound_return_with_delay(
            benchmark[return_col],
            int(horizon),
            delay=max(int(entry_delay_days), 1),
        )

    return benchmark, source


def _merge_feature_frame(base_df: pd.DataFrame, other_df: pd.DataFrame | None, feature_cols: list[str]) -> pd.DataFrame:
    if other_df is None or other_df.empty:
        return base_df

    base = base_df.copy()
    base["date"] = pd.to_datetime(base["date"])

    other = other_df.copy()
    other["date"] = pd.to_datetime(other["date"])
    join_cols = ["symbol", "date"] + [c for c in feature_cols if c in other.columns]
    merged = base.merge(other[join_cols], on=["symbol", "date"], how="left", suffixes=("", "_feature"))

    for col in feature_cols:
        feature_col = f"{col}_feature"
        if feature_col not in merged.columns:
            continue
        if col in merged.columns:
            merged[col] = merged[col].fillna(merged[feature_col])
        else:
            merged[col] = merged[feature_col]
        merged = merged.drop(columns=[feature_col])
    return merged


def _ensure_core_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values(["symbol", "date"]).reset_index(drop=True)
    grouped = out.groupby("symbol", group_keys=False)

    def populate_col(col_name, calc_series):
        if col_name not in out.columns:
            out[col_name] = calc_series
        else:
            out[col_name] = out[col_name].fillna(calc_series)

    populate_col("return_1d", grouped["close"].pct_change())
    populate_col("return_20d", grouped["close"].pct_change(20))
    for horizon in (5, 10, 20):
        forward_col = f"forward_return_{horizon}d"
        populate_col(forward_col, grouped["close"].shift(-horizon) / out["close"] - 1)

    prior_close = grouped["close"].shift(1)
    true_range = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prior_close).abs(),
            (out["low"] - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    populate_col("true_range", true_range)
    populate_col("atr_14", grouped["true_range"].transform(lambda s: s.rolling(14, min_periods=7).mean()))
    populate_col("atr_pct_14", _safe_divide(out["atr_14"], out["close"]))

    populate_col("realized_vol_20d", grouped["return_1d"].transform(lambda s: s.rolling(20, min_periods=10).std()) * np.sqrt(252))
    populate_col("ewma_vol_20d", grouped["return_1d"].transform(lambda s: s.ewm(span=20, min_periods=10).std()) * np.sqrt(252))
    
    vol_pct = out.groupby("date")["realized_vol_20d"].rank(pct=True)
    populate_col("volatility_percentile", vol_pct)
    
    bins = [-np.inf, 0.2, 0.5, 0.75, 0.9, np.inf]
    labels = ["Low Vol", "Normal Vol", "High Vol", "Stress Vol", "Panic Vol"]
    vol_reg = pd.cut(out["volatility_percentile"], bins=bins, labels=labels)
    vol_reg = vol_reg.astype(object).fillna("Unknown")
    populate_col("volatility_regime", vol_reg)
    out["volatility_regime"] = out["volatility_regime"].fillna("Unknown").replace({np.nan: "Unknown", "nan": "Unknown", None: "Unknown"})

    if "tail_ratio_60d" not in out.columns:
        out["tail_ratio_60d"] = 1.0
    else:
        out["tail_ratio_60d"] = out["tail_ratio_60d"].fillna(1.0)

    return out


def prepare_stealth_accumulation_features(
    price_df: pd.DataFrame,
    volatility_df: pd.DataFrame | None = None,
    distribution_df: pd.DataFrame | None = None,
    market_df: pd.DataFrame | None = None,
    config: dict[str, Any] | None = None,
    benchmark_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if price_df.empty:
        return pd.DataFrame()

    cfg = _deep_merge(DEFAULT_SCREEN_CONFIG, config or {})
    windows = cfg["windows"]
    base_window = int(windows["base_window"])
    # trend_window reserved for future use
    liquidity_window = int(windows["liquidity_window"])
    volume_fast_window = int(windows["volume_fast_window"])
    volume_slow_window = int(windows["volume_slow_window"])
    market_window = int(windows["market_window"])
    min_history = int(windows["min_history"])

    df = price_df.copy()
    df = _merge_feature_frame(
        df,
        volatility_df,
        ["return_1d", "return_20d", "atr_14", "atr_pct_14", "realized_vol_20d", "ewma_vol_20d", "volatility_percentile", "volatility_regime"],
    )
    df = _merge_feature_frame(df, distribution_df, ["tail_ratio_60d"])
    df = _ensure_core_columns(df)

    if market_df is not None and not market_df.empty:
        market_features = market_df.copy()
        market_features["date"] = pd.to_datetime(market_features["date"])
        keep_cols = [c for c in ["date", "market_regime", "up_down_volume_ratio", "advance_decline_ratio"] if c in market_features.columns]
        df = df.merge(market_features[keep_cols], on="date", how="left")
        if "market_regime" not in df.columns:
            df["market_regime"] = "Unknown"
        df["market_regime"] = df["market_regime"].astype(object).fillna("Unknown")
        if "up_down_volume_ratio" not in df.columns:
            df["up_down_volume_ratio"] = np.nan
        if "advance_decline_ratio" not in df.columns:
            df["advance_decline_ratio"] = np.nan
    else:
        df["market_regime"] = "Unknown"
        df["up_down_volume_ratio"] = np.nan
        df["advance_decline_ratio"] = np.nan

    symbols = cfg["universe"].get("symbols") or []
    if symbols:
        symbol_set = {str(symbol).upper() for symbol in symbols}
        df = df[df["symbol"].astype(str).str.upper().isin(symbol_set)].copy()

    if "market" in df.columns:
        df["market"] = df.sort_values("date").groupby("symbol")["market"].ffill().bfill()

    markets = cfg["universe"].get("markets") or []
    if markets and "market" in df.columns:
        market_set = {str(market).upper() for market in markets}
        df = df[df["market"].astype(str).str.upper().isin(market_set)].copy()

    if df.empty:
        return pd.DataFrame()

    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    grouped = df.groupby("symbol", group_keys=False)

    sector_cfg = cfg.get("sector", {})
    sector_col = str(sector_cfg.get("column", "sector"))
    unknown_sector = str(sector_cfg.get("unknown_label", "Unclassified"))
    if sector_col not in df.columns:
        df[sector_col] = np.nan
    symbol_map = {str(k).upper(): str(v) for k, v in (sector_cfg.get("symbol_map") or {}).items()}
    if symbol_map:
        mapped_sector = df["symbol"].astype(str).str.upper().map(symbol_map)
        df[sector_col] = df[sector_col].fillna(mapped_sector)
    df[sector_col] = df[sector_col].fillna(unknown_sector)

    # G2: prefer the real VNINDEX benchmark as market proxy. The old equal-weight
    # mean of the input basket compared symbols against themselves (bank-heavy).
    market_proxy_source = "internal_equal_weight"
    daily_market = pd.DataFrame()
    bench = benchmark_df
    if bench is None or bench.empty:
        bench_path = (cfg.get("backtest") or {}).get("benchmark_path")
        if bench_path:
            bench = _read_optional_frame(bench_path)
    if bench is not None and not bench.empty and "date" in bench.columns:
        bench = bench.copy()
        bench["date"] = pd.to_datetime(bench["date"], errors="coerce")
        bench = bench.dropna(subset=["date"]).sort_values("date")
        if "return_1d" not in bench.columns and "close" in bench.columns:
            bench["return_1d"] = pd.to_numeric(bench["close"], errors="coerce").pct_change()
        if "return_1d" in bench.columns:
            daily_market = (
                bench[["date", "return_1d"]]
                .rename(columns={"return_1d": "market_proxy_return_1d"})
                .drop_duplicates(subset=["date"], keep="last")
                .reset_index(drop=True)
            )
            market_proxy_source = "benchmark_vnindex"
    if daily_market.empty:
        daily_market = (
            df.groupby("date")["return_1d"]
            .mean()
            .rename("market_proxy_return_1d")
            .reset_index()
            .sort_values("date")
        )
    daily_market["market_proxy_return_20d"] = _rolling_compound_return(daily_market["market_proxy_return_1d"], market_window)
    df = df.merge(daily_market, on="date", how="left")
    df["market_proxy_source"] = market_proxy_source

    sector_daily = (
        df.groupby(["date", sector_col])["return_1d"]
        .mean()
        .rename("sector_proxy_return_1d")
        .reset_index()
        .sort_values(["date", sector_col])
    )
    sector_daily["sector_proxy_return_20d"] = (
        sector_daily.groupby(sector_col)["sector_proxy_return_1d"]
        .transform(lambda s: _rolling_compound_return(s, market_window))
    )
    df = df.merge(sector_daily, on=["date", sector_col], how="left")

    candle_range = (df["high"] - df["low"]).replace(0, np.nan)
    df["close_location_value"] = _safe_divide(df["close"] - df["low"], candle_range).clip(0, 1)
    df["upper_wick_pct"] = _safe_divide(df["high"] - df["close"], candle_range).clip(lower=0)

    df["avg_value_20d"] = grouped["value"].transform(lambda s: s.rolling(liquidity_window, min_periods=max(10, liquidity_window // 2)).mean())
    df["avg_volume_20d"] = grouped["volume"].transform(lambda s: s.rolling(liquidity_window, min_periods=max(10, liquidity_window // 2)).mean())
    df["value_ma_10"] = grouped["value"].transform(lambda s: s.rolling(10, min_periods=5).mean())
    df["value_ma_60"] = grouped["value"].transform(lambda s: s.rolling(60, min_periods=20).mean())
    df["volume_ma_fast"] = grouped["volume"].transform(lambda s: s.rolling(volume_fast_window, min_periods=max(3, volume_fast_window // 2)).mean())
    df["volume_ma_slow"] = grouped["volume"].transform(lambda s: s.rolling(volume_slow_window, min_periods=max(10, volume_slow_window // 2)).mean())
    df["value_ratio_10_60"] = _safe_divide(df["value_ma_10"], df["value_ma_60"])
    df["volume_ratio_5_20"] = _safe_divide(df["volume_ma_fast"], df["volume_ma_slow"])

    df["rolling_high_20d"] = grouped["high"].transform(lambda s: s.rolling(base_window, min_periods=max(10, base_window // 2)).max())
    df["rolling_low_20d"] = grouped["low"].transform(lambda s: s.rolling(base_window, min_periods=max(10, base_window // 2)).min())
    df["rolling_low_5d"] = grouped["low"].transform(lambda s: s.rolling(5, min_periods=3).min())
    df["rolling_high_20d_prev"] = df.groupby("symbol")["rolling_high_20d"].shift(1)
    df["base_range_20d"] = _safe_divide(df["rolling_high_20d"], df["rolling_low_20d"]) - 1
    df["price_position_20d"] = _safe_divide(df["close"] - df["rolling_low_20d"], df["rolling_high_20d"] - df["rolling_low_20d"]).clip(0, 1)
    df["pullback_from_high_20d"] = _safe_divide(df["close"], df["rolling_high_20d"]) - 1
    df["distance_to_pivot"] = _safe_divide(df["close"], df["rolling_high_20d_prev"]) - 1
    df["higher_low_ratio"] = _safe_divide(df["rolling_low_5d"], df["rolling_low_20d"]) - 1

    # Calculate Bollinger Band Width & Squeeze
    bb_std = grouped["close"].transform(lambda s: s.rolling(20, min_periods=max(2, 20 // 3)).std())
    bb_ma = grouped["close"].transform(lambda s: s.rolling(20, min_periods=max(2, 20 // 3)).mean())
    df["bb_width"] = _safe_divide(4 * bb_std, bb_ma)

    # Redefine GroupBy object to pick up the new columns (bb_width, base_range_20d, etc.)
    grouped = df.groupby("symbol", group_keys=False)

    df["bb_width_percentile"] = grouped["bb_width"].transform(lambda s: s.rolling(120, min_periods=max(2, 120 // 3)).rank(pct=True))
    df["bb_squeeze"] = (df["bb_width_percentile"] <= 0.25) | (df["bb_width"] <= 0.08)

    df["base_range_percentile"] = grouped["base_range_20d"].transform(lambda s: s.rolling(120, min_periods=max(2, 120 // 3)).rank(pct=True))
    df["range_squeeze"] = (df["base_range_percentile"] <= 0.25) | (df["base_range_20d"] <= 0.08)

    df["is_compressed"] = df["bb_squeeze"] & df["range_squeeze"]
    df["ready_for_breakout"] = df["is_compressed"] & (df["price_position_20d"] >= 0.70)

    down_clv = df["close_location_value"].where(df["return_1d"] <= 0)
    up_value = df["value"].where(df["return_1d"] > 0, 0.0)
    down_value = df["value"].where(df["return_1d"] <= 0, 0.0)
    relative_on_market_down = (df["return_1d"] - df["market_proxy_return_1d"]).where(df["market_proxy_return_1d"] < 0)

    df["down_day_clv_10d"] = down_clv.groupby(df["symbol"]).transform(lambda s: s.rolling(10, min_periods=4).mean())
    df["up_value_10d"] = up_value.groupby(df["symbol"]).transform(lambda s: s.rolling(10, min_periods=4).sum())
    df["down_value_10d"] = down_value.groupby(df["symbol"]).transform(lambda s: s.rolling(10, min_periods=4).sum())
    df["up_down_value_ratio_10d"] = _safe_divide(df["up_value_10d"], df["down_value_10d"]).replace([np.inf, -np.inf], np.nan)
    df["market_down_alpha_20d"] = relative_on_market_down.groupby(df["symbol"]).transform(lambda s: s.rolling(market_window, min_periods=5).mean())
    df["relative_strength_20d"] = df["return_20d"] - df["market_proxy_return_20d"]
    df["sector_relative_strength_20d"] = df["return_20d"] - df["sector_proxy_return_20d"]
    df["sector_tailwind_20d"] = df["sector_proxy_return_20d"] - df["market_proxy_return_20d"]

    # G2: a 1-2 name "sector" proxy is mostly the symbol itself — self-comparison.
    # Neutralize sector RS there (NaN ranks to 50 in cross-sectional scoring).
    sector_sizes = df.groupby(sector_col)["symbol"].transform("nunique")
    df["sector_rs_reliable"] = sector_sizes >= 3
    df.loc[~df["sector_rs_reliable"], ["sector_relative_strength_20d", "sector_tailwind_20d"]] = np.nan

    df["history_days"] = grouped.cumcount() + 1
    df["liquidity_pass"] = (df["avg_value_20d"] >= float(cfg["filters"]["min_avg_value_20d"])) & (df["close"] >= float(cfg["filters"]["min_price"]))
    allowed_volatility = set(cfg["filters"].get("allowed_volatility_regimes") or [])
    allowed_market = set(cfg["filters"].get("allowed_market_regimes") or [])
    df["regime_pass"] = True
    if allowed_volatility:
        df["regime_pass"] &= df["volatility_regime"].astype(str).isin(allowed_volatility)
    if allowed_market and "market_regime" in df.columns:
        df["regime_pass"] &= df["market_regime"].astype(str).isin(allowed_market)
    df["history_pass"] = df["history_days"] >= min_history

    df["ma50"] = grouped["close"].transform(lambda s: s.rolling(50, min_periods=max(2, 50 // 3)).mean())
    df["ma200"] = grouped["close"].transform(lambda s: s.rolling(200, min_periods=max(2, 200 // 3)).mean())

    trend_cfg = cfg["filters"].get("trend_filters") or {}
    require_above_ma50 = bool(trend_cfg.get("require_above_ma50", True))
    require_above_ma200 = bool(trend_cfg.get("require_above_ma200", True))
    require_ma50_above_ma200 = bool(trend_cfg.get("require_ma50_above_ma200", False))

    df["trend_pass"] = True
    if require_above_ma50:
        df["trend_pass"] &= (df["close"] >= df["ma50"]) | df["ma50"].isna()
    if require_above_ma200:
        df["trend_pass"] &= (df["close"] >= df["ma200"]) | df["ma200"].isna()
    if require_ma50_above_ma200:
        df["trend_pass"] &= (df["ma50"] >= df["ma200"]) | df["ma50"].isna() | df["ma200"].isna()

    df["liquidity_score"] = _cross_sectional_score(df, "avg_value_20d", higher_is_better=True)
    df["tight_range_score"] = _cross_sectional_score(df, "base_range_20d", higher_is_better=False)
    df["volatility_dryup_score"] = (
        0.5 * _cross_sectional_score(df, "atr_pct_14", higher_is_better=False)
        + 0.5 * _cross_sectional_score(df, "volatility_percentile", higher_is_better=False)
    )
    df["quiet_volume_score"] = (
        0.5 * _bell_score(df["volume_ratio_5_20"].fillna(1.0), center=0.90, width=0.60)
        + 0.5 * _bell_score(df["value_ratio_10_60"].fillna(1.0), center=1.00, width=0.70)
    )
    df["absorption_score"] = (
        0.45 * _clip_score(df["down_day_clv_10d"].fillna(0.5), low=0.45, high=0.85)
        + 0.35 * _cross_sectional_score(df, "up_down_value_ratio_10d", higher_is_better=True)
        + 0.20 * _clip_score(df["pullback_from_high_20d"].fillna(-0.20), low=-0.15, high=-0.01)
    )
    df["relative_strength_score"] = (
        0.45 * _cross_sectional_score(df, "relative_strength_20d", higher_is_better=True)
        + 0.30 * _cross_sectional_score(df, "market_down_alpha_20d", higher_is_better=True)
        + 0.25 * _cross_sectional_score(df, "sector_relative_strength_20d", higher_is_better=True)
    )
    df["pressure_score"] = (
        0.45 * _clip_score(df["price_position_20d"].fillna(0.5), low=0.55, high=1.0)
        + 0.30 * _clip_score(df["higher_low_ratio"].fillna(0.0), low=0.0, high=0.08)
        + 0.25 * _cross_sectional_score(df, "return_20d", higher_is_better=True)
    )
    df["near_pivot_score"] = _bell_score(df["distance_to_pivot"].fillna(-0.02), center=-0.01, width=0.06)
    df["breadth_support_score"] = (
        0.55 * _clip_score(df["advance_decline_ratio"].fillna(1.0), low=0.85, high=1.25)
        + 0.45 * _clip_score(df["up_down_volume_ratio"].fillna(1.0), low=0.90, high=1.30)
    )
    df["sector_support_score"] = (
        0.65 * _cross_sectional_score(df, "sector_tailwind_20d", higher_is_better=True)
        + 0.35 * _cross_sectional_score(df, "sector_proxy_return_20d", higher_is_better=True)
    )

    market_support_map = {
        "Neutral": 60.0,
        "Risk-off": 40.0,
        "Unknown": 50.0,
    }
    volatility_support_map = {
        "Low Vol": 85.0,
        "Normal Vol": 70.0,
        "High Vol": 55.0,
        "Stress Vol": 40.0,
        "Panic Vol": 20.0,
        "Unknown": 45.0,
    }
    df["market_support_score"] = _regime_score(df["market_regime"], market_support_map)
    df["volatility_support_score"] = _regime_score(df["volatility_regime"], volatility_support_map)

    df["accumulation_score"] = (
        0.25 * df["tight_range_score"].fillna(50.0)
        + 0.20 * df["volatility_dryup_score"].fillna(50.0)
        + 0.20 * df["quiet_volume_score"].fillna(50.0)
        + 0.20 * df["absorption_score"].fillna(50.0)
        + 0.15 * df["relative_strength_score"].fillna(50.0)
    )
    df["breakout_quality_score"] = (
        0.25 * df["pressure_score"].fillna(50.0)
        + 0.25 * df["near_pivot_score"].fillna(50.0)
        + 0.15 * df["liquidity_score"].fillna(50.0)
        + 0.15 * df["volatility_support_score"].fillna(50.0)
        + 0.10 * df["market_support_score"].fillna(50.0)
        + 0.05 * df["breadth_support_score"].fillna(50.0)
        + 0.05 * df["sector_support_score"].fillna(50.0)
    )

    df["overextension_risk_score"] = _clip_score(df["distance_to_pivot"].fillna(0.0), low=0.02, high=0.10)
    df["upper_wick_risk_score"] = _clip_score(df["upper_wick_pct"].fillna(0.0), low=0.30, high=0.85)
    df["volatility_spike_risk_score"] = (
        0.6 * _clip_score(df["volatility_percentile"].fillna(0.5), low=0.65, high=1.0)
        + 0.4 * _clip_score(df["realized_vol_20d"].fillna(0.30), low=0.40, high=0.90)
    )
    df["exhaustion_volume_risk_score"] = _clip_score(df["volume_ratio_5_20"].fillna(1.0), low=1.35, high=2.50)
    df["tail_risk_score"] = _clip_score(df["tail_ratio_60d"].fillna(1.0), low=0.70, high=1.20, invert=True)
    df["fakeout_risk_score"] = (
        0.25 * df["overextension_risk_score"].fillna(0.0)
        + 0.20 * df["upper_wick_risk_score"].fillna(0.0)
        + 0.25 * df["volatility_spike_risk_score"].fillna(0.0)
        + 0.15 * df["exhaustion_volume_risk_score"].fillna(0.0)
        + 0.15 * df["tail_risk_score"].fillna(0.0)
    )

    # Normalized scoring: weights sum to 1.0, fakeout inverted so higher = better
    df["net_accumulation_score"] = (
        0.50 * df["accumulation_score"]
        + 0.25 * df["breakout_quality_score"]
        + 0.25 * (100.0 - df["fakeout_risk_score"])
    ).clip(lower=0, upper=100)

    thresholds = cfg["thresholds"]
    df["accumulation_stage"] = "No Structure"
    df.loc[
        df["history_pass"]
        & df["liquidity_pass"]
        & df["regime_pass"]
        & df["trend_pass"]
        & (df["accumulation_score"] >= float(thresholds["stage_a_min_score"]))
        & (df["fakeout_risk_score"] <= float(thresholds["max_fakeout_risk"]) + 5),
        "accumulation_stage",
    ] = "Stage A: Silent Accumulation"
    df.loc[
        df["history_pass"]
        & df["liquidity_pass"]
        & df["regime_pass"]
        & df["trend_pass"]
        & (df["accumulation_score"] >= float(thresholds["stage_b_min_score"]))
        & (df["pressure_score"] >= 60)
        & (df["fakeout_risk_score"] <= float(thresholds["max_fakeout_risk"])),
        "accumulation_stage",
    ] = "Stage B: Pressure Building"
    df.loc[
        df["history_pass"]
        & df["liquidity_pass"]
        & df["regime_pass"]
        & df["trend_pass"]
        & df["is_compressed"]
        & (df["fakeout_risk_score"] <= float(thresholds["max_fakeout_risk"]) + 10),
        "accumulation_stage",
    ] = "Stage S: Tight Squeeze"
    df.loc[
        df["history_pass"]
        & df["liquidity_pass"]
        & df["regime_pass"]
        & df["trend_pass"]
        & (df["net_accumulation_score"] >= float(thresholds["stage_c_min_score"]))
        & (df["breakout_quality_score"] >= 65)
        & df["distance_to_pivot"].between(-0.01, 0.04, inclusive="both")
        & (df["fakeout_risk_score"] <= float(thresholds["max_fakeout_risk"]) - 5),
        "accumulation_stage",
    ] = "Stage C: Valid Expansion"

    df["screen_pass"] = df["history_pass"] & df["liquidity_pass"] & df["regime_pass"] & df["trend_pass"]
    df["watchlist_flag"] = (
        df["screen_pass"]
        & (
            (df["net_accumulation_score"] >= float(thresholds["watchlist_min_net_score"]))
            | (df["accumulation_stage"] == "Stage S: Tight Squeeze")
        )
        & (df["fakeout_risk_score"] <= float(thresholds["max_fakeout_risk"]))
        & (df["accumulation_stage"] != "No Structure")
    )

    return df.sort_values(["date", "net_accumulation_score", "symbol"], ascending=[True, False, True]).reset_index(drop=True)


def _apply_sector_cap(
    snapshot: pd.DataFrame,
    top_n: int,
    max_names_per_sector: int | None = None,
    sector_col: str = "sector",
    unknown_label: str = "Unclassified",
) -> pd.DataFrame:
    if snapshot.empty:
        return snapshot.copy()

    ranked = snapshot.sort_values(["net_accumulation_score", "accumulation_score", "symbol"], ascending=[False, False, True]).reset_index(drop=True)
    if max_names_per_sector is None or max_names_per_sector <= 0 or sector_col not in ranked.columns:
        ranked = ranked.head(top_n).copy()
        ranked["selection_rank"] = np.arange(1, len(ranked) + 1)
        return ranked

    sector_counts: dict[str, int] = {}
    selected_rows: list[pd.Series] = []
    for _, row in ranked.iterrows():
        sector = str(row.get(sector_col, unknown_label) or unknown_label)
        if sector_counts.get(sector, 0) >= int(max_names_per_sector):
            continue
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        selected_rows.append(row)
        if len(selected_rows) >= top_n:
            break

    selected = pd.DataFrame(selected_rows)
    if selected.empty:
        return selected
    selected = selected.reset_index(drop=True)
    selected["selection_rank"] = np.arange(1, len(selected) + 1)
    return selected


def latest_screen_snapshot(
    screen_df: pd.DataFrame,
    as_of: str | pd.Timestamp | None = None,
    top_n: int = 10,
    only_watchlist: bool = True,
    sector_aware: bool = False,
    max_names_per_sector: int | None = None,
    sector_col: str = "sector",
    unknown_sector: str = "Unclassified",
) -> pd.DataFrame:
    if screen_df.empty:
        return pd.DataFrame()

    snapshot = screen_df.copy()
    snapshot["date"] = pd.to_datetime(snapshot["date"])
    target_date = pd.to_datetime(as_of) if as_of is not None else snapshot["date"].max()
    snapshot = snapshot[snapshot["date"] == target_date].copy()
    if only_watchlist and "watchlist_flag" in snapshot.columns:
        snapshot = snapshot[snapshot["watchlist_flag"]].copy()
    elif "screen_pass" in snapshot.columns:
        snapshot = snapshot[snapshot["screen_pass"]].copy()
    if sector_aware:
        return _apply_sector_cap(
            snapshot,
            top_n=top_n,
            max_names_per_sector=max_names_per_sector,
            sector_col=sector_col,
            unknown_label=unknown_sector,
        )
    return snapshot.sort_values(["net_accumulation_score", "accumulation_score", "symbol"], ascending=[False, False, True]).head(top_n).reset_index(drop=True)


def backtest_stealth_accumulation_screen(
    screen_df: pd.DataFrame,
    top_n: int = 5,
    holding_periods: list[int] | tuple[int, ...] = (5, 10, 20),
    only_watchlist: bool = False,
    sector_aware: bool = False,
    max_names_per_sector: int | None = None,
    sector_col: str = "sector",
    unknown_sector: str = "Unclassified",
    benchmark_df: pd.DataFrame | None = None,
    benchmark_symbol: str = "VNINDEX",
    benchmark_path: str | Path | None = None,
    cost_model: dict[str, Any] | None = None,
    entry_delay_days: int = 1,
    entry_price_col: str = "open",
    exit_price_col: str = "close",
) -> dict[str, pd.DataFrame]:
    if screen_df.empty:
        empty = pd.DataFrame()
        return {"by_date": empty, "summary": empty, "selections": empty}

    df = screen_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "net_accumulation_score", "symbol"], ascending=[True, False, True]).reset_index(drop=True)

    selection_rows: list[pd.DataFrame] = []
    for date, snapshot in df.groupby("date"):
        current = snapshot.copy()
        if only_watchlist and "watchlist_flag" in current.columns:
            current = current[current["watchlist_flag"]].copy()
        elif "screen_pass" in current.columns:
            current = current[current["screen_pass"]].copy()
        if current.empty:
            continue

        if sector_aware:
            selected = _apply_sector_cap(
                current,
                top_n=top_n,
                max_names_per_sector=max_names_per_sector,
                sector_col=sector_col,
                unknown_label=unknown_sector,
            )
        else:
            selected = current.head(top_n).copy().reset_index(drop=True)
            selected["selection_rank"] = np.arange(1, len(selected) + 1)
        if selected.empty:
            continue
        selected["selection_date"] = date
        selected["selection_type"] = "sector_aware" if sector_aware else "raw"
        selection_rows.append(selected)

    if not selection_rows:
        empty = pd.DataFrame()
        return {"by_date": empty, "summary": empty, "selections": empty}

    selections = pd.concat(selection_rows, ignore_index=True)
    benchmark, benchmark_source = _prepare_benchmark_frame(
        holding_periods=holding_periods,
        screen_df=df,
        benchmark_df=benchmark_df,
        benchmark_symbol=benchmark_symbol,
        benchmark_path=benchmark_path,
        entry_delay_days=entry_delay_days,
    )

    symbol_price_map = {
        str(symbol): group.sort_values("date").reset_index(drop=True)
        for symbol, group in df.groupby("symbol")
    }

    by_date_rows: list[dict[str, Any]] = []
    for horizon in holding_periods:
        forward_col = f"forward_return_{int(horizon)}d"
        benchmark_forward_col = f"benchmark_forward_return_{int(horizon)}d"
        benchmark_by_date: pd.Series | None = None
        if not benchmark.empty and benchmark_forward_col in benchmark.columns:
            benchmark_by_date = benchmark.set_index("date")[benchmark_forward_col]
        grouped = selections.groupby("selection_date")
        for date, group in grouped:
            realized_rows = []
            for idx, row in group.iterrows():
                symbol = str(row["symbol"])
                symbol_prices = symbol_price_map.get(symbol)
                realized = _realized_selection_return(
                    symbol_prices,
                    signal_date=pd.to_datetime(row["selection_date"]),
                    holding_period=int(horizon),
                    entry_delay_days=entry_delay_days,
                    entry_price_col=entry_price_col,
                    exit_price_col=exit_price_col,
                )
                if realized is None:
                    fallback_return = row.get(forward_col, np.nan)
                    if pd.isna(fallback_return):
                        continue
                    realized_return = float(fallback_return)
                    signal_to_entry_gap = np.nan
                else:
                    realized_return, signal_to_entry_gap = realized
                realized_rows.append(
                    {
                        "index": idx,
                        "realized_forward_return": realized_return,
                        "signal_to_entry_gap": signal_to_entry_gap,
                    }
                )

            realized_df = pd.DataFrame(realized_rows)
            if realized_df.empty:
                continue
            realized_df = realized_df.set_index("index")
            aligned_group = group.loc[realized_df.index]
            returns = realized_df["realized_forward_return"]
            signal_gaps = realized_df["signal_to_entry_gap"]
            cost_series = _estimate_trade_costs(aligned_group, cost_model=cost_model)
            net_returns = returns - cost_series
            benchmark_return = float(benchmark_by_date.get(date)) if benchmark_by_date is not None and date in benchmark_by_date.index else np.nan
            avg_forward_return = float(returns.mean())
            avg_net_forward_return = float(net_returns.mean())
            avg_trading_cost = float(cost_series.mean()) if not cost_series.empty else 0.0
            avg_signal_to_entry_gap = float(signal_gaps.mean()) if signal_gaps.notna().any() else np.nan
            excess_return = avg_forward_return - benchmark_return if pd.notna(benchmark_return) else np.nan
            net_excess_return = avg_net_forward_return - benchmark_return if pd.notna(benchmark_return) else np.nan
            by_date_rows.append(
                {
                    "selection_date": date,
                    "holding_period_days": int(horizon),
                    "portfolio_type": "sector_aware" if sector_aware else "raw",
                    "avg_forward_return": avg_forward_return,
                    "avg_net_forward_return": avg_net_forward_return,
                    "avg_trading_cost": avg_trading_cost,
                    "avg_signal_to_entry_gap": avg_signal_to_entry_gap,
                    "median_forward_return": float(returns.median()),
                    "median_net_forward_return": float(net_returns.median()),
                    "hit_rate": float((returns > 0).mean()),
                    "net_hit_rate": float((net_returns > 0).mean()),
                    "selection_count": int(len(returns)),
                    "benchmark_return": benchmark_return,
                    "excess_return": excess_return,
                    "net_excess_return": net_excess_return,
                    "beat_benchmark": bool(excess_return > 0) if pd.notna(excess_return) else np.nan,
                    "beat_benchmark_net": bool(net_excess_return > 0) if pd.notna(net_excess_return) else np.nan,
                    "benchmark_source": benchmark_source,
                }
            )

    by_date = pd.DataFrame(by_date_rows)
    if by_date.empty:
        return {"by_date": by_date, "summary": by_date, "selections": selections}

    summary_rows: list[dict[str, Any]] = []
    for horizon, group in by_date.groupby("holding_period_days"):
        vol = float(group["avg_forward_return"].std())
        mean_return = float(group["avg_forward_return"].mean())
        sharpe_like = mean_return / vol * np.sqrt(252 / int(horizon)) if vol > 0 else np.nan
        net_vol = float(group["avg_net_forward_return"].std())
        net_mean_return = float(group["avg_net_forward_return"].mean())
        net_sharpe_like = net_mean_return / net_vol * np.sqrt(252 / int(horizon)) if net_vol > 0 else np.nan
        benchmark_mean = float(group["benchmark_return"].dropna().mean()) if group["benchmark_return"].notna().any() else np.nan
        excess = group["excess_return"].dropna()
        excess_mean = float(excess.mean()) if not excess.empty else np.nan
        excess_vol = float(excess.std()) if len(excess) > 1 else np.nan
        info_ratio_like = excess_mean / excess_vol * np.sqrt(252 / int(horizon)) if pd.notna(excess_vol) and excess_vol > 0 else np.nan
        net_excess = group["net_excess_return"].dropna()
        net_excess_mean = float(net_excess.mean()) if not net_excess.empty else np.nan
        net_excess_vol = float(net_excess.std()) if len(net_excess) > 1 else np.nan
        net_information_ratio_like = net_excess_mean / net_excess_vol * np.sqrt(252 / int(horizon)) if pd.notna(net_excess_vol) and net_excess_vol > 0 else np.nan
        summary_rows.append(
            {
                "portfolio_type": group["portfolio_type"].iloc[0],
                "holding_period_days": int(horizon),
                "observations": int(len(group)),
                "avg_forward_return": mean_return,
                "avg_net_forward_return": net_mean_return,
                "avg_trading_cost": float(group["avg_trading_cost"].mean()),
                "avg_signal_to_entry_gap": float(group["avg_signal_to_entry_gap"].mean()) if group["avg_signal_to_entry_gap"].notna().any() else np.nan,
                "avg_benchmark_return": benchmark_mean,
                "avg_excess_return": excess_mean,
                "avg_net_excess_return": net_excess_mean,
                "median_forward_return": float(group["avg_forward_return"].median()),
                "median_net_forward_return": float(group["avg_net_forward_return"].median()),
                "hit_rate": float((group["avg_forward_return"] > 0).mean()),
                "net_hit_rate": float((group["avg_net_forward_return"] > 0).mean()),
                "excess_hit_rate": float((group["excess_return"] > 0).mean()) if group["excess_return"].notna().any() else np.nan,
                "net_excess_hit_rate": float((group["net_excess_return"] > 0).mean()) if group["net_excess_return"].notna().any() else np.nan,
                "avg_selection_count": float(group["selection_count"].mean()),
                "volatility_of_avg_returns": vol,
                "volatility_of_avg_net_returns": net_vol,
                "sharpe_like": sharpe_like,
                "net_sharpe_like": net_sharpe_like,
                "information_ratio_like": info_ratio_like,
                "net_information_ratio_like": net_information_ratio_like,
                "benchmark_source": group["benchmark_source"].dropna().iloc[0] if group["benchmark_source"].notna().any() else benchmark_source,
            }
        )

    summary = pd.DataFrame(summary_rows).sort_values(["holding_period_days", "portfolio_type"]).reset_index(drop=True)
    return {"by_date": by_date, "summary": summary, "selections": selections}


def compare_screen_backtests(
    screen_df: pd.DataFrame,
    top_n: int = 5,
    holding_periods: list[int] | tuple[int, ...] = (5, 10, 20),
    only_watchlist: bool = False,
    max_names_per_sector: int = 2,
    sector_col: str = "sector",
    unknown_sector: str = "Unclassified",
    benchmark_df: pd.DataFrame | None = None,
    benchmark_symbol: str = "VNINDEX",
    benchmark_path: str | Path | None = None,
    cost_model: dict[str, Any] | None = None,
    entry_delay_days: int = 1,
    entry_price_col: str = "open",
    exit_price_col: str = "close",
) -> dict[str, pd.DataFrame]:
    raw = backtest_stealth_accumulation_screen(
        screen_df=screen_df,
        top_n=top_n,
        holding_periods=holding_periods,
        only_watchlist=only_watchlist,
        sector_aware=False,
        sector_col=sector_col,
        unknown_sector=unknown_sector,
        benchmark_df=benchmark_df,
        benchmark_symbol=benchmark_symbol,
        benchmark_path=benchmark_path,
        cost_model=cost_model,
        entry_delay_days=entry_delay_days,
        entry_price_col=entry_price_col,
        exit_price_col=exit_price_col,
    )
    sector = backtest_stealth_accumulation_screen(
        screen_df=screen_df,
        top_n=top_n,
        holding_periods=holding_periods,
        only_watchlist=only_watchlist,
        sector_aware=True,
        max_names_per_sector=max_names_per_sector,
        sector_col=sector_col,
        unknown_sector=unknown_sector,
        benchmark_df=benchmark_df,
        benchmark_symbol=benchmark_symbol,
        benchmark_path=benchmark_path,
        cost_model=cost_model,
        entry_delay_days=entry_delay_days,
        entry_price_col=entry_price_col,
        exit_price_col=exit_price_col,
    )

    summary = pd.concat([raw["summary"], sector["summary"]], ignore_index=True) if not raw["summary"].empty or not sector["summary"].empty else pd.DataFrame()
    by_date = pd.concat([raw["by_date"], sector["by_date"]], ignore_index=True) if not raw["by_date"].empty or not sector["by_date"].empty else pd.DataFrame()
    selections = pd.concat([raw["selections"], sector["selections"]], ignore_index=True) if not raw["selections"].empty or not sector["selections"].empty else pd.DataFrame()
    return {"summary": summary, "by_date": by_date, "selections": selections}


def run_stealth_accumulation_screen(
    price_df: pd.DataFrame,
    volatility_df: pd.DataFrame | None = None,
    distribution_df: pd.DataFrame | None = None,
    market_df: pd.DataFrame | None = None,
    config: dict[str, Any] | None = None,
    benchmark_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    return prepare_stealth_accumulation_features(
        price_df=price_df,
        volatility_df=volatility_df,
        distribution_df=distribution_df,
        market_df=market_df,
        config=config,
        benchmark_df=benchmark_df,
    )
