from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.validators import filter_primary_equity_symbols
from src.data.loaders import save_parquet
from src.utils.scoring import (
    deep_merge as _deep_merge,
    safe_divide as _safe_divide,
    bell_score as _bell_score,
)


DEFAULT_LIGHT_SCAN_CONFIG: dict[str, Any] = {
    "lookback_days": 320,
    "min_history": 120,
    "top_n": 10,
    "filters": {
        "min_price": 10.0,
        "min_avg_value_20d": 8_000_000_000.0,
        "min_median_value_20d": 5_000_000_000.0,
    },
    "score_weights": {
        "liquidity": 0.25,
        "trend": 0.25,
        "breakout_readiness": 0.20,
        "volume_confirmation": 0.15,
        "stability": 0.15,
    },
}


def _pct_rank(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    rank = numeric.rank(pct=True, ascending=higher_is_better)
    return rank.fillna(0.5) * 100.0


def _inverse_rank_score(series: pd.Series, default: float = 50.0) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return pd.Series(default, index=series.index, dtype="float64")
    min_rank = float(valid.min())
    max_rank = float(valid.max())
    out = pd.Series(default, index=series.index, dtype="float64")
    if max_rank <= min_rank:
        out.loc[valid.index] = 100.0
        return out
    scaled = 1.0 - (valid - min_rank) / (max_rank - min_rank)
    out.loc[scaled.index] = (scaled.clip(lower=0.0, upper=1.0) * 100.0).astype(float)
    return out


def prepare_light_market_scan_features(
    price_df: pd.DataFrame,
    config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    if price_df.empty:
        return pd.DataFrame()

    cfg = _deep_merge(DEFAULT_LIGHT_SCAN_CONFIG, config or {})
    out = filter_primary_equity_symbols(price_df).copy()
    if out.empty:
        return out
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values(["symbol", "date"]).reset_index(drop=True)

    grouped = out.groupby("symbol", group_keys=False)
    out["return_1d"] = grouped["close"].pct_change() if "return_1d" not in out.columns else pd.to_numeric(out["return_1d"], errors="coerce")
    out["return_20d"] = grouped["close"].pct_change(20)
    out["return_60d"] = grouped["close"].pct_change(60)
    out["avg_value_20d"] = grouped["value"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    out["median_value_20d"] = grouped["value"].transform(lambda s: s.rolling(20, min_periods=10).median())
    out["avg_volume_20d"] = grouped["volume"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    out["volume_ma_5"] = grouped["volume"].transform(lambda s: s.rolling(5, min_periods=3).mean())
    out["volume_ratio_5_20"] = _safe_divide(out["volume_ma_5"], out["avg_volume_20d"])
    out["realized_vol_20d"] = grouped["return_1d"].transform(lambda s: s.rolling(20, min_periods=10).std()) * np.sqrt(252)
    out["rolling_high_20d_prev"] = grouped["high"].transform(lambda s: s.shift(1).rolling(20, min_periods=10).max())
    out["distance_to_breakout_20d"] = _safe_divide(out["close"], out["rolling_high_20d_prev"]) - 1.0
    out["history_days"] = grouped.cumcount() + 1
    out["scan_date"] = out["date"]
    return out


def latest_light_scan_snapshot(
    features: pd.DataFrame,
    config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()

    cfg = _deep_merge(DEFAULT_LIGHT_SCAN_CONFIG, config or {})
    latest = features.sort_values(["symbol", "date"]).groupby("symbol").tail(1).copy()
    latest = latest[latest["history_days"] >= int(cfg["min_history"])].copy()

    filters = cfg["filters"]
    latest["liquidity_pass"] = (
        pd.to_numeric(latest["close"], errors="coerce").fillna(0.0) >= float(filters["min_price"])
    ) & (
        pd.to_numeric(latest["avg_value_20d"], errors="coerce").fillna(0.0) >= float(filters["min_avg_value_20d"])
    ) & (
        pd.to_numeric(latest["median_value_20d"], errors="coerce").fillna(0.0) >= float(filters["min_median_value_20d"])
    )

    latest = latest[latest["liquidity_pass"]].copy()
    if latest.empty:
        return latest

    latest["liquidity_score"] = (
        0.7 * _pct_rank(latest["avg_value_20d"], higher_is_better=True)
        + 0.3 * _pct_rank(latest["median_value_20d"], higher_is_better=True)
    )
    latest["trend_score"] = (
        0.55 * _pct_rank(latest["return_20d"], higher_is_better=True)
        + 0.45 * _pct_rank(latest["return_60d"], higher_is_better=True)
    )
    latest["breakout_readiness_score"] = _bell_score(
        latest["distance_to_breakout_20d"].fillna(-0.05),
        center=-0.015,
        width=0.08,
    )
    latest["volume_confirmation_score"] = _bell_score(
        latest["volume_ratio_5_20"].fillna(1.0),
        center=1.10,
        width=0.90,
    )
    latest["stability_score"] = _pct_rank(latest["realized_vol_20d"], higher_is_better=False)

    weights = cfg["score_weights"]
    latest["light_scan_score"] = (
        float(weights["liquidity"]) * latest["liquidity_score"]
        + float(weights["trend"]) * latest["trend_score"]
        + float(weights["breakout_readiness"]) * latest["breakout_readiness_score"]
        + float(weights["volume_confirmation"]) * latest["volume_confirmation_score"]
        + float(weights["stability"]) * latest["stability_score"]
    )

    latest["watchlist_bucket"] = pd.cut(
        latest["light_scan_score"],
        bins=[-np.inf, 55, 70, 82, np.inf],
        labels=["Monitor", "Qualified", "Priority", "Prime"],
    ).astype(object)
    latest["auto_watchlist_flag"] = latest["watchlist_bucket"].isin(["Priority", "Prime"])
    return latest.sort_values(["light_scan_score", "avg_value_20d"], ascending=False).reset_index(drop=True)


def select_auto_watchlist(
    snapshot: pd.DataFrame,
    top_n: int = 10,
    sector_col: str = "sector",
    max_per_sector: int = 2,
    unknown_sector: str = "Unclassified",
) -> pd.DataFrame:
    if snapshot.empty:
        return pd.DataFrame()

    data = snapshot.copy()
    if sector_col not in data.columns:
        data[sector_col] = unknown_sector
    data[sector_col] = data[sector_col].fillna(unknown_sector)
    base_liquidity_score = (
        pd.to_numeric(data["liquidity_score"], errors="coerce").fillna(50.0)
        if "liquidity_score" in data.columns
        else pd.Series(50.0, index=data.index, dtype="float64")
    )
    data["recent_liquidity_rank_score"] = (
        _inverse_rank_score(data["recent_liquidity_rank"])
        if "recent_liquidity_rank" in data.columns
        else pd.Series(50.0, index=data.index, dtype="float64")
    )
    data["leadership_liquidity_score"] = (
        0.60 * base_liquidity_score
        + 0.40 * data["recent_liquidity_rank_score"]
    ).clip(lower=0.0, upper=100.0)
    data["selection_score"] = (
        0.65 * pd.to_numeric(data.get("light_scan_score", 0.0), errors="coerce").fillna(0.0)
        + 0.35 * data["leadership_liquidity_score"]
    ).clip(lower=0.0, upper=100.0)
    data = data.sort_values(
        ["selection_score", "light_scan_score", "avg_value_20d"],
        ascending=False,
    ).reset_index(drop=True)

    picks: list[pd.Series] = []
    sector_counts: dict[str, int] = {}
    for _, row in data.iterrows():
        sector = str(row.get(sector_col, unknown_sector) or unknown_sector)
        if sector_counts.get(sector, 0) >= int(max_per_sector):
            continue
        picks.append(row)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(picks) >= int(top_n):
            break

    if not picks:
        return pd.DataFrame()

    out = pd.DataFrame(picks).reset_index(drop=True)
    out["selection_rank"] = np.arange(1, len(out) + 1)
    return out


def save_auto_watchlist_outputs(
    snapshot: pd.DataFrame,
    watchlist: pd.DataFrame,
    out_dir: str | Path = "data/signals",
    prefix: str = "auto_watchlist",
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = out_dir / f"{prefix}_snapshot.parquet"
    watchlist_path = out_dir / f"{prefix}_top10.parquet"
    symbols_path = out_dir / f"{prefix}_symbols.parquet"

    save_parquet(snapshot, snapshot_path)
    save_parquet(watchlist, watchlist_path)
    save_parquet(watchlist[["symbol"]].drop_duplicates().reset_index(drop=True) if not watchlist.empty else pd.DataFrame({"symbol": []}), symbols_path)
    return {
        "snapshot": snapshot_path,
        "watchlist": watchlist_path,
        "symbols": symbols_path,
    }


def load_auto_watchlist_symbols(path: str | Path = "data/signals/auto_watchlist_symbols.parquet") -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    df = pd.read_parquet(p)
    if df.empty or "symbol" not in df.columns:
        return []
    return sorted(df["symbol"].dropna().astype(str).str.upper().unique().tolist())
