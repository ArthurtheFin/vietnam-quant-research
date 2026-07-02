from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet, save_parquet
from src.data.validators import filter_primary_equity_symbols
from src.utils.scoring import deep_merge
from src.utils.logger import get_logger

LOGGER = get_logger("final_watchlist")


FINAL_WATCHLIST_COLUMNS = [
    "rank",
    "symbol",
    "date",
    "analysis_as_of",
    "data_age_days",
    "close",
    "final_score",
    "base_final_score",
    "warning_penalty",
    "candidate_tier",
    "confidence_label",
    "is_research_candidate",
    "is_trading_candidate",
    "is_client_ready",
    "exclusion_reason",
    "trend_score",
    "momentum_score",
    "relative_strength_score",
    "volume_score",
    "liquidity_score",
    "risk_score",
    "signal_score",
    "volatility_regime",
    "risk_reward_estimate",
    "reason",
    "warning",
    "eligibility_status",
    "eligibility_reason",
    "latest_volume",
    "cashflow_data_status",
    "confirmation_status",
]


DEFAULT_FINAL_WATCHLIST_CONFIG: dict[str, Any] = {
    "watchlist_size": 10,
    "benchmark_symbol": "VNINDEX",
    "min_history_days": 120,
    "min_price": 5.0,
    "min_value_ma20": 5_000_000_000.0,
    "min_volume_ma20": 50_000.0,
    "max_atr_pct": 0.08,
    "max_relaxed_atr_pct": 0.12,
    "max_distance_ma20": 0.18,
    "max_relaxed_distance_ma20": 0.28,
    "max_drawdown_60d": -0.30,
    "weights": {
        "trend": 25,
        "momentum": 20,
        "relative_strength": 20,
        "liquidity": 10,
        "volume": 5,
        "risk": 10,
        "signal": 10,
    },
    "paths": {
        "features": "data/processed/stock_features.parquet",
        "benchmark": "data/processed/benchmark_vnindex.parquet",
        "meta_ranking": "data/signals/meta_ranking.parquet",
        "alpha_scores": "data/signals/alpha_scores.parquet",
        "output_csv": "data/signals/final_watchlist.csv",
        "output_parquet": "data/signals/final_watchlist.parquet",
        "output_excel": "reports/final_watchlist.xlsx",
        "output_dir": "data/output",
    },
}


def build_final_watchlist_from_files(
    config: dict[str, Any] | None = None,
    base_dir: str | Path = ".",
) -> pd.DataFrame:
    cfg = deep_merge(DEFAULT_FINAL_WATCHLIST_CONFIG, config or {})
    base = Path(base_dir)
    paths = cfg["paths"]

    features = read_parquet(base / paths["features"])
    benchmark = read_parquet(base / paths["benchmark"])
    meta = read_parquet(base / paths["meta_ranking"])
    alpha = read_parquet(base / paths["alpha_scores"])
    outputs = build_watchlist_tiers(
        features=features,
        benchmark=benchmark,
        meta_ranking=meta,
        alpha_scores=alpha,
        config=cfg,
    )
    save_watchlist_outputs(outputs, cfg, base_dir=base)
    return outputs["client_ready_watchlist"].copy()


def build_watchlist_tiers(
    features: pd.DataFrame,
    benchmark: pd.DataFrame | None = None,
    meta_ranking: pd.DataFrame | None = None,
    alpha_scores: pd.DataFrame | None = None,
    config: dict[str, Any] | None = None,
    as_of_date: str | pd.Timestamp | None = None,
    candidate_symbols: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, pd.DataFrame]:
    cfg = deep_merge(DEFAULT_FINAL_WATCHLIST_CONFIG, config or {})
    size = int(cfg["watchlist_size"])
    if features.empty:
        raise ValueError("stock_features is empty. Run scripts/generate_features.py first.")

    latest = _latest_feature_snapshot(features, as_of_date=as_of_date)
    if candidate_symbols is not None:
        normalized_candidates = {
            str(symbol).strip().upper()
            for symbol in candidate_symbols
            if pd.notna(symbol) and str(symbol).strip()
        }
        latest = latest[latest["symbol"].astype(str).str.upper().isin(normalized_candidates)].copy()
    latest = _ensure_screening_columns(latest)
    if latest.empty:
        raise ValueError("No candidate symbols remain after applying universe filters.")
    if candidate_symbols is None and latest["symbol"].nunique() < size:
        raise ValueError(f"Need at least {size} unique symbols; found {latest['symbol'].nunique()}.")

    latest = _merge_benchmark(latest, benchmark)
    actual_as_of = latest["analysis_as_of"].iloc[0] if "analysis_as_of" in latest.columns and not latest.empty else as_of_date
    latest = _merge_latest_alpha(latest, alpha_scores, as_of_date=actual_as_of)
    latest = _merge_latest_meta(latest, meta_ranking, as_of_date=actual_as_of)
    latest = _score(latest, cfg)
    latest = _mark_filters(latest, cfg)
    latest = _apply_candidate_tiers(latest)

    # Try to load cashflow data if available to apply eligibility gate
    cashflow_board = None
    wcc = None
    cashflow_board_path = Path("data/output/cashflow_board.parquet")
    wcc_path = Path("data/output/watchlist_cashflow_confirmation.parquet")

    if cashflow_board_path.exists():
        try:
            cashflow_board = read_parquet(cashflow_board_path)
        except Exception:
            pass
    if wcc_path.exists():
        try:
            wcc = read_parquet(wcc_path)
        except Exception:
            pass

    latest = apply_eligibility_gate(latest, cashflow_board, wcc)

    latest = latest.sort_values(
        [
            "is_client_ready",
            "is_trading_candidate",
            "is_research_candidate",
            "final_score",
            "symbol",
        ],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)

    client_ready_candidates = latest[
        (latest["candidate_tier"] == "Client Ready") & (latest["eligibility_status"] == "ELIGIBLE")
    ].copy()
    client_ready = client_ready_candidates.head(size)
    client_ready_syms = set(client_ready["symbol"]) if not client_ready.empty else set()

    trading_candidates = latest[
        (latest["candidate_tier"].isin(["Client Ready", "Trading Watchlist"])) &
        (latest["eligibility_status"] == "ELIGIBLE") &
        (~latest["symbol"].isin(client_ready_syms))
    ].copy()
    trading = trading_candidates.head(20)
    trading_syms = set(trading["symbol"]) if not trading.empty else set()

    active_syms = client_ready_syms.union(trading_syms)

    research = latest[
        ((latest["eligibility_status"] == "ELIGIBLE") & (~latest["symbol"].isin(active_syms))) |
        (latest["eligibility_status"] == "REJECTED")
    ].copy()

    all_scored = latest.copy()
    eligible = latest[latest["eligibility_status"] == "ELIGIBLE"].copy()

    for frame in (research, trading, client_ready, eligible, all_scored):
        if not frame.empty:
            frame["rank"] = np.arange(1, len(frame) + 1)

    return {
        "scored_universe": latest,
        "research_candidates": research[FINAL_WATCHLIST_COLUMNS] if not research.empty else pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS),
        "trading_watchlist": trading[FINAL_WATCHLIST_COLUMNS] if not trading.empty else pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS),
        "client_ready_watchlist": client_ready[FINAL_WATCHLIST_COLUMNS] if not client_ready.empty else pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS),
        "eligible_candidates": eligible[FINAL_WATCHLIST_COLUMNS] if not eligible.empty else pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS),
        "all_scored_candidates": all_scored[FINAL_WATCHLIST_COLUMNS] if not all_scored.empty else pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS),
    }


def build_final_watchlist(
    features: pd.DataFrame,
    benchmark: pd.DataFrame | None = None,
    meta_ranking: pd.DataFrame | None = None,
    alpha_scores: pd.DataFrame | None = None,
    config: dict[str, Any] | None = None,
    as_of_date: str | pd.Timestamp | None = None,
    candidate_symbols: list[str] | tuple[str, ...] | set[str] | None = None,
) -> pd.DataFrame:
    outputs = build_watchlist_tiers(
        features=features,
        benchmark=benchmark,
        meta_ranking=meta_ranking,
        alpha_scores=alpha_scores,
        config=config,
        as_of_date=as_of_date,
        candidate_symbols=candidate_symbols,
    )
    return outputs["client_ready_watchlist"].copy()


def save_final_watchlist(watchlist: pd.DataFrame, config: dict[str, Any], base_dir: str | Path = ".") -> dict[str, Path]:
    base = Path(base_dir)
    paths = config["paths"]
    csv_path = base / paths["output_csv"]
    parquet_path = base / paths["output_parquet"]
    excel_path = base / paths["output_excel"]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    excel_path.parent.mkdir(parents=True, exist_ok=True)
    watchlist.to_csv(csv_path, index=False)
    save_parquet(watchlist, parquet_path)
    try:
        watchlist.to_excel(excel_path, index=False)
    except ImportError:
        pass
    return {"csv": csv_path, "parquet": parquet_path, "excel": excel_path}


def save_watchlist_outputs(
    outputs: dict[str, pd.DataFrame],
    config: dict[str, Any] | None = None,
    base_dir: str | Path = ".",
) -> dict[str, Path]:
    cfg = deep_merge(DEFAULT_FINAL_WATCHLIST_CONFIG, config or {})
    paths = cfg["paths"]
    base = Path(base_dir)
    output_dir = base / paths.get("output_dir", "data/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = save_final_watchlist(outputs.get("client_ready_watchlist", pd.DataFrame()), cfg, base_dir=base)

    mapping = {
        "research_candidates": output_dir / "research_candidates",
        "trading_watchlist": output_dir / "trading_watchlist",
        "client_ready_watchlist": output_dir / "client_ready_watchlist",
        "eligible_candidates": output_dir / "eligible_candidates",
        "all_scored_candidates": output_dir / "all_scored_candidates",
    }
    for name, stem in mapping.items():
        frame = outputs.get(name, pd.DataFrame())
        csv_path = stem.with_suffix(".csv")
        parquet_path = stem.with_suffix(".parquet")
        frame.to_csv(csv_path, index=False)
        save_parquet(frame, parquet_path)
        saved_paths[f"{name}_csv"] = csv_path
        saved_paths[f"{name}_parquet"] = parquet_path

    # Write watchlist metadata JSON
    from src.utils.pipeline_io import write_json
    
    meta_path = output_dir / "watchlist_metadata.json"
    meta_data = {
        "input_source": str(paths.get("features", "stock_features.parquet")),
        "input_candidate_count": int(len(outputs.get("scored_universe", pd.DataFrame()))),
        "eligible_candidate_count": int(len(outputs.get("eligible_candidates", pd.DataFrame()))),
        "client_ready_count": int(len(outputs.get("client_ready_watchlist", pd.DataFrame()))),
        "trading_watchlist_count": int(len(outputs.get("trading_watchlist", pd.DataFrame()))),
        "research_candidate_count": int(len(outputs.get("research_candidates", pd.DataFrame()))),
        "data_review_count": int(outputs.get("scored_universe", pd.DataFrame())["eligibility_status"].eq("REJECTED").sum()) if "scored_universe" in outputs else 0,
        "client_ready_threshold": 60.0,
        "trading_threshold": 55.0,
        "generated_files": [str(stem.with_suffix(".parquet")) for stem in mapping.values()] + [str(meta_path)],
        "generated_at": pd.Timestamp.now().isoformat(),
        "warnings": []
    }
    write_json(meta_data, meta_path)
    saved_paths["watchlist_metadata"] = meta_path
    
    return saved_paths


def _latest_by_symbol(df: pd.DataFrame, as_of_date: str | pd.Timestamp | None = None) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    if as_of_date is not None:
        out = out[out["date"] <= pd.Timestamp(as_of_date)]
    if out.empty:
        raise ValueError("No feature rows available at or before as_of_date.")
    return out.sort_values(["symbol", "date"]).groupby("symbol", as_index=False).tail(1).reset_index(drop=True)


def _latest_feature_snapshot(df: pd.DataFrame, as_of_date: str | pd.Timestamp | None = None) -> pd.DataFrame:
    out = filter_primary_equity_symbols(df).copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values(["symbol", "date"]).copy()
    out["history_days"] = out.groupby("symbol").cumcount() + 1
    if "return_60d" not in out.columns and "close" in out.columns:
        out["return_60d"] = out.groupby("symbol")["close"].pct_change(60)
    if "ma50" in out.columns:
        out["ma50_slope_20d"] = _safe_divide(out["ma50"], out.groupby("symbol")["ma50"].shift(20)) - 1.0

    if as_of_date is None:
        as_of_date = out["date"].max()
    else:
        as_of_date = pd.Timestamp(as_of_date)

    out = out[out["date"] <= as_of_date]
    if out.empty:
        raise ValueError(f"No feature rows available at or before {as_of_date}.")
    out = out.sort_values(["symbol", "date"]).groupby("symbol", as_index=False).tail(1)
    out["analysis_as_of"] = pd.Timestamp(as_of_date)
    out["data_age_days"] = (out["analysis_as_of"] - out["date"]).dt.days.astype(int)
    return out.reset_index(drop=True)


def _ensure_screening_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "history_days" not in out.columns:
        out["history_days"] = 0
    if "return_60d" not in out.columns and {"symbol", "close"}.issubset(out.columns):
        out["return_60d"] = np.nan
    if "value_ma20" not in out.columns and "avg_value_20d" in out.columns:
        out["value_ma20"] = out["avg_value_20d"]
    if "volume_ma20" not in out.columns and "avg_volume_20d" in out.columns:
        out["volume_ma20"] = out["avg_volume_20d"]
    defaults = {
        "ma20": np.nan,
        "ma50": np.nan,
        "ma200": np.nan,
        "distance_ma20": np.nan,
        "distance_ma50": np.nan,
        "above_ma20": False,
        "above_ma50": False,
        "above_ma200": False,
        "return_20d": np.nan,
        "return_60d": np.nan,
        "volume_zscore_20d": np.nan,
        "volume_ma20": np.nan,
        "value_ma20": np.nan,
        "atr_pct_14": np.nan,
        "realized_vol_20d": np.nan,
        "volatility_percentile": np.nan,
        "volatility_regime": "Unknown",
        "tail_ratio_60d": np.nan,
    }
    for column, default in defaults.items():
        if column not in out.columns:
            out[column] = default
    if "ma50_slope_20d" not in out.columns:
        out["ma50_slope_20d"] = np.nan
    return out


def _merge_benchmark(df: pd.DataFrame, benchmark: pd.DataFrame | None) -> pd.DataFrame:
    out = df.copy()
    if benchmark is None or benchmark.empty:
        out["benchmark_return_20d"] = np.nan
        out["benchmark_return_60d"] = np.nan
        out["relative_strength_score_raw"] = np.nan
        return out
    bench = benchmark.copy()
    bench["date"] = pd.to_datetime(bench["date"])
    if "return_60d" not in bench.columns and "close" in bench.columns:
        bench["return_60d"] = bench["close"].pct_change(60)
    keep = [c for c in ["date", "return_20d", "return_60d"] if c in bench.columns]
    bench = bench[keep].rename(columns={"return_20d": "benchmark_return_20d", "return_60d": "benchmark_return_60d"})
    out = out.merge(bench, on="date", how="left")
    out["excess_return_20d"] = out["return_20d"] - out["benchmark_return_20d"]
    out["excess_return_60d"] = out["return_60d"] - out["benchmark_return_60d"]
    return out


def _merge_latest_alpha(df: pd.DataFrame, alpha_scores: pd.DataFrame | None, as_of_date: str | pd.Timestamp | None = None) -> pd.DataFrame:
    if alpha_scores is None or alpha_scores.empty:
        df["alpha_score"] = np.nan
        return df
    alpha = _latest_by_symbol(alpha_scores, as_of_date=as_of_date)
    keep = [c for c in ["symbol", "alpha_score", "momentum_score", "rs_score", "trend_score", "volume_score", "volatility_score", "liquidity_score"] if c in alpha.columns]
    rename = {
        "momentum_score": "alpha_momentum_score",
        "rs_score": "alpha_rs_score",
        "trend_score": "alpha_trend_score",
        "volume_score": "alpha_volume_score",
        "volatility_score": "alpha_volatility_score",
        "liquidity_score": "alpha_liquidity_score",
    }
    return df.merge(alpha[keep].rename(columns=rename), on="symbol", how="left")


def _merge_latest_meta(df: pd.DataFrame, meta_ranking: pd.DataFrame | None, as_of_date: str | pd.Timestamp | None = None) -> pd.DataFrame:
    if meta_ranking is None or meta_ranking.empty:
        df["meta_score"] = np.nan
        return df
    meta = meta_ranking.copy()
    date_col = "analysis_date" if "analysis_date" in meta.columns else "date"
    if date_col in meta.columns:
        meta[date_col] = pd.to_datetime(meta[date_col])
        if as_of_date is not None:
            meta = meta[meta[date_col] <= pd.Timestamp(as_of_date)]
        meta = meta.sort_values(["symbol", date_col]).groupby("symbol", as_index=False).tail(1)
    keep = [c for c in ["symbol", "meta_score", "trade_edge_score", "setup_quality_score", "risk_penalty_score", "priority_bucket"] if c in meta.columns]
    return df.merge(meta[keep], on="symbol", how="left")


def _score(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    weights = cfg["weights"]
    trend_raw = pd.concat(
        [
            out["above_ma20"].astype(bool).astype(float),
            out["above_ma50"].astype(bool).astype(float),
            out["above_ma200"].astype(bool).astype(float),
            (out["ma20"] > out["ma50"]).fillna(False).astype(float),
            (out["ma50_slope_20d"] > 0).fillna(False).astype(float),
            (out["distance_ma20"].abs() <= float(cfg["max_distance_ma20"])).fillna(False).astype(float),
        ],
        axis=1,
    ).mean(axis=1)
    out["trend_score"] = (trend_raw * weights["trend"]).round(2)

    momentum_raw = pd.concat(
        [
            _rank(out["return_20d"]),
            _rank(out["return_60d"]),
            _rank(out.get("alpha_momentum_score", pd.Series(np.nan, index=out.index))),
            _rank(out.get("alpha_score", pd.Series(np.nan, index=out.index))),
        ],
        axis=1,
    ).mean(axis=1)
    out["momentum_score"] = (momentum_raw * weights["momentum"]).round(2)

    rs_raw = pd.concat(
        [
            _rank(out.get("excess_return_20d", pd.Series(np.nan, index=out.index))),
            _rank(out.get("excess_return_60d", pd.Series(np.nan, index=out.index))),
            _rank(out.get("alpha_rs_score", pd.Series(np.nan, index=out.index))),
        ],
        axis=1,
    ).mean(axis=1)
    out["relative_strength_score"] = (rs_raw * weights["relative_strength"]).round(2)

    out["liquidity_score"] = (_rank(out["value_ma20"]) * weights["liquidity"]).round(2)
    volume_raw = pd.concat(
        [
            _rank(out["volume_zscore_20d"].clip(-2, 4)),
            (out["volume_zscore_20d"].between(-0.5, 3.5)).fillna(False).astype(float),
        ],
        axis=1,
    ).mean(axis=1)
    out["volume_score"] = (volume_raw * weights["volume"]).round(2)

    risk_raw = pd.concat(
        [
            _rank(out["atr_pct_14"], higher_is_better=False),
            _rank(out["realized_vol_20d"], higher_is_better=False),
            _rank(out["volatility_percentile"], higher_is_better=False),
            _rank(out["tail_ratio_60d"], higher_is_better=False),
            _rank(out.get("risk_penalty_score", pd.Series(np.nan, index=out.index)), higher_is_better=False),
        ],
        axis=1,
    ).mean(axis=1)
    out["risk_score"] = (risk_raw * weights["risk"]).round(2)

    signal_raw = pd.concat(
        [
            _rank(out.get("meta_score", pd.Series(np.nan, index=out.index))),
            _rank(out.get("trade_edge_score", pd.Series(np.nan, index=out.index))),
            _rank(out.get("setup_quality_score", pd.Series(np.nan, index=out.index))),
        ],
        axis=1,
    ).mean(axis=1)
    out["signal_score"] = (signal_raw * weights["signal"]).round(2)
    out["base_final_score"] = out[["trend_score", "momentum_score", "relative_strength_score", "liquidity_score", "volume_score", "risk_score", "signal_score"]].sum(axis=1).clip(0, 100).round(2)
    out["risk_reward_estimate"] = _safe_divide(out["return_60d"], out["atr_pct_14"].abs())
    out["warning"] = out.apply(lambda row: "; ".join(_warnings(row, cfg)), axis=1)
    out["warning_penalty"] = out["warning"].map(_warning_penalty).astype(float)
    out["final_score"] = (out["base_final_score"] - out["warning_penalty"]).clip(0, 100).round(2)
    out["volatility_regime"] = out["volatility_regime"].fillna("Unknown").astype(str)
    out["risk_reward_estimate"] = out["risk_reward_estimate"].round(2)
    out["reason"] = out.apply(_reason_text, axis=1)
    out["warning"] = out["warning"].fillna("")
    return out


def _mark_filters(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    valid = out["close"].fillna(0).gt(float(cfg["min_price"])) & out["history_days"].fillna(0).ge(int(cfg["min_history_days"]))
    strict_liquidity = (out["value_ma20"].fillna(0) >= float(cfg["min_value_ma20"])) | (out["volume_ma20"].fillna(0) >= float(cfg["min_volume_ma20"]))
    strict_trend = out["above_ma50"].astype(bool) & out["above_ma200"].astype(bool)
    strict_momentum = out["return_20d"].fillna(0).gt(0) & out["return_60d"].fillna(0).gt(0)
    strict_risk = out["atr_pct_14"].fillna(0).le(float(cfg["max_atr_pct"]))
    strict_extension = out["distance_ma20"].abs().fillna(0).le(float(cfg["max_distance_ma20"]))
    relaxed_risk = out["atr_pct_14"].fillna(0).le(float(cfg["max_relaxed_atr_pct"]))
    relaxed_extension = out["distance_ma20"].abs().fillna(0).le(float(cfg["max_relaxed_distance_ma20"]))
    relaxed_liquidity = (out["value_ma20"].fillna(0) >= float(cfg["min_value_ma20"]) * 0.4) | (out["volume_ma20"].fillna(0) >= float(cfg["min_volume_ma20"]) * 0.4)
    out["strict_pass"] = valid & strict_liquidity & strict_trend & strict_momentum & strict_risk & strict_extension
    out["fallback_eligible"] = valid & relaxed_liquidity & relaxed_risk & relaxed_extension & out["above_ma200"].astype(bool)
    return out


def _rank(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    ranked = numeric.rank(pct=True)
    if not higher_is_better:
        ranked = 1.0 - ranked
    return ranked.fillna(0.5).clip(0, 1)


def _safe_divide(left: pd.Series, right: pd.Series) -> pd.Series:
    return pd.to_numeric(left, errors="coerce") / pd.to_numeric(right, errors="coerce").replace(0, np.nan)


def _warnings(row: pd.Series, cfg: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if pd.to_numeric(row.get("data_age_days", 0), errors="coerce") > 0:
        out.append("Stale data")
    if pd.isna(row.get("meta_score")):
        out.append("Missing backtest evidence")
    if row.get("distance_ma20", 0) > float(cfg["max_distance_ma20"]):
        out.append("Extended from MA20")
    if row.get("atr_pct_14", 0) > float(cfg["max_atr_pct"]):
        out.append("High volatility")
    if row.get("value_ma20", 0) < float(cfg["min_value_ma20"]):
        out.append("Low liquidity")
    if row.get("excess_return_20d", 0) < 0:
        out.append("Weak relative strength")
    market_regime = row.get("market_regime")
    if pd.notna(market_regime) and str(market_regime).strip().lower() in {"downtrend", "neutral", "unknown"}:
        out.append("Weak market regime")
    return out


def _warning_penalty(warning_text: str | float) -> float:
    if pd.isna(warning_text) or not str(warning_text).strip():
        return 0.0
    penalty_map = {
        "Stale data": 100.0,
        "Missing backtest evidence": 20.0,
        "Low liquidity": 20.0,
        "Weak market regime": 12.0,
        "High volatility": 10.0,
        "Weak relative strength": 8.0,
        "Extended from MA20": 5.0,
    }
    total = 0.0
    for token in [part.strip() for part in str(warning_text).split(";") if part.strip()]:
        total += penalty_map.get(token, 0.0)
    return total


def _apply_candidate_tiers(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    warning_series = out["warning"].fillna("")

    out["is_stale_data"] = warning_series.str.contains("Stale data", case=False, na=False)
    out["is_missing_backtest_evidence"] = warning_series.str.contains("Missing backtest evidence", case=False, na=False)
    out["is_low_liquidity_warning"] = warning_series.str.contains("Low liquidity", case=False, na=False)
    out["is_weak_market_regime"] = warning_series.str.contains("Weak market regime", case=False, na=False)

    out["is_research_candidate"] = (
        ~out["is_stale_data"]
        & (out["fallback_eligible"] | out["strict_pass"] | out["final_score"].ge(45.0))
    )
    out["is_trading_candidate"] = (
        out["is_research_candidate"]
        & out["strict_pass"]
        & ~out["is_low_liquidity_warning"]
        & out["final_score"].ge(55.0)
    )
    out["is_client_ready"] = (
        out["is_trading_candidate"]
        & ~out["is_missing_backtest_evidence"]
        & ~out["is_weak_market_regime"]
        & out["final_score"].ge(60.0)
    )

    out["candidate_tier"] = np.select(
        [
            out["is_client_ready"],
            out["is_trading_candidate"],
            out["is_research_candidate"],
        ],
        [
            "Client Ready",
            "Trading Watchlist",
            "Research Candidate",
        ],
        default="Excluded",
    )

    exclusion_reasons: list[str] = []
    for _, row in out.iterrows():
        reasons: list[str] = []
        if row["is_stale_data"]:
            reasons.append("Stale data")
        if row["is_low_liquidity_warning"]:
            reasons.append("Low liquidity")
        if row["is_missing_backtest_evidence"]:
            reasons.append("Missing backtest evidence")
        if row["is_weak_market_regime"]:
            reasons.append("Weak market regime")
        if not row["strict_pass"] and row["is_research_candidate"]:
            reasons.append("Below trading threshold")
        exclusion_reasons.append("; ".join(dict.fromkeys(reasons)))
    out["exclusion_reason"] = exclusion_reasons

    out["confidence_label"] = np.select(
        [
            out["is_client_ready"] & out["final_score"].ge(70.0),
            out["is_client_ready"],
            out["is_trading_candidate"],
            out["is_research_candidate"],
        ],
        [
            "High",
            "Medium-High",
            "Medium",
            "Low",
        ],
        default="Excluded",
    )
    return out


def _append_warning(extra: str):
    def append(value: str | float) -> str:
        current = "" if pd.isna(value) else str(value)
        return extra if not current else f"{current}; {extra}"

    return append


def _reason_text(row: pd.Series) -> str:
    phrases: list[str] = []
    if row["trend_score"] >= 17:
        phrases.append("Xu hướng tăng duy trì")
    if row["relative_strength_score"] >= 13:
        phrases.append("RS vượt VNINDEX")
    if row["momentum_score"] >= 13:
        phrases.append("động lượng tốt")
    if row["liquidity_score"] + row["volume_score"] >= 10:
        phrases.append("thanh khoản cải thiện")
    if row["risk_score"] >= 6:
        phrases.append("volatility vừa phải")
    if row["signal_score"] >= 7:
        phrases.append("có bằng chứng tín hiệu lịch sử")
    if not phrases:
        phrases.append("Điểm tổng hợp tốt hơn phần còn lại của vũ trụ")
    return ", ".join(phrases[:3]).capitalize() + "."


def apply_eligibility_gate(
    df: pd.DataFrame,
    cashflow_board: pd.DataFrame | None = None,
    watchlist_cashflow_confirmation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()

    # Ensure columns exist
    if "eligibility_status" not in out.columns:
        out["eligibility_status"] = "ELIGIBLE"
    if "eligibility_reason" not in out.columns:
        out["eligibility_reason"] = "None"
    if "latest_volume" not in out.columns:
        out["latest_volume"] = np.nan
    if "cashflow_data_status" not in out.columns:
        out["cashflow_data_status"] = "OK"
    if "confirmation_status" not in out.columns:
        out["confirmation_status"] = "WATCH"

    for idx, row in out.iterrows():
        sym = row["symbol"]

        close = row.get("close")
        volume = row.get("latest_volume")
        if pd.isna(volume) or volume is None:
            volume = row.get("volume")

        cf_row = None
        wcc_row = None
        if cashflow_board is not None and not cashflow_board.empty and sym in cashflow_board["symbol"].values:
            cf_row = cashflow_board[cashflow_board["symbol"] == sym].iloc[0]
            if pd.isna(volume) or volume is None or np.isnan(volume):
                volume = cf_row.get("volume")
        if watchlist_cashflow_confirmation is not None and not watchlist_cashflow_confirmation.empty and sym in watchlist_cashflow_confirmation["symbol"].values:
            wcc_row = watchlist_cashflow_confirmation[watchlist_cashflow_confirmation["symbol"] == sym].iloc[0]

        cf_status = cf_row.get("cashflow_data_status", "OK") if cf_row is not None else "OK"
        confirm_status = wcc_row.get("confirmation_status", "WATCH") if wcc_row is not None else "WATCH"
        cf_state = cf_row.get("cashflow_state", "NEUTRAL") if cf_row is not None else "NEUTRAL"
        data_age = row.get("data_age_days", 0)

        value_ma20 = row.get("value_ma20", cf_row.get("value_ma20", np.nan) if cf_row is not None else np.nan)
        volume_ma20 = row.get("volume_ma20", cf_row.get("volume_ma20", np.nan) if cf_row is not None else np.nan)

        reasons = []

        if pd.isna(close) or close <= 0:
            reasons.append("INVALID_CLOSE")

        if pd.isna(volume) or volume <= 0:
            reasons.append("ZERO_VOLUME_OR_MISSING_DATA")

        if cf_status in ("ZERO_VOLUME", "MISSING_DATA", "CHECK_REQUIRED"):
            reasons.append("CASHFLOW_CHECK_REQUIRED")

        if confirm_status in ("CHECK_REQUIRED", "REJECT"):
            reasons.append("CASHFLOW_CHECK_REQUIRED")

        if not pd.isna(data_age) and data_age > 1:
            reasons.append("STALE_DATA")

        # Gating threshold is min_value_ma20 = 5 billion and min_volume_ma20 = 50k
        if not pd.isna(value_ma20) and value_ma20 < 5_000_000_000.0:
            if pd.isna(volume_ma20) or volume_ma20 < 50_000.0:
                reasons.append("LOW_LIQUIDITY")

        if cf_state == "DISTRIBUTION_RISK":
            reasons.append("SEVERE_DISTRIBUTION_RISK")

        # Fill values in output
        out.at[idx, "latest_volume"] = volume if not pd.isna(volume) else 0.0
        out.at[idx, "cashflow_data_status"] = cf_status
        out.at[idx, "confirmation_status"] = confirm_status

        if reasons:
            out.at[idx, "eligibility_status"] = "REJECTED"
            out.at[idx, "eligibility_reason"] = "; ".join(sorted(set(reasons)))
            out.at[idx, "is_client_ready"] = False
            out.at[idx, "confidence_label"] = "REVIEW_REQUIRED"

            orig_tier = row.get("candidate_tier", "Research Candidate")
            if orig_tier == "Client Ready":
                out.at[idx, "candidate_tier"] = "Research Candidate"

            exc = row.get("exclusion_reason", "")
            reason_str = "; ".join(sorted(set(reasons)))
            if not exc or pd.isna(exc) or exc == "":
                out.at[idx, "exclusion_reason"] = f"Failed gates: {reason_str}"
            else:
                out.at[idx, "exclusion_reason"] = f"{exc}; Failed gates: {reason_str}"
        else:
            out.at[idx, "eligibility_status"] = "ELIGIBLE"
            out.at[idx, "eligibility_reason"] = "None"

    return out


def apply_post_cashflow_overlay(base_dir: str | Path = ".") -> None:
    base = Path(base_dir)

    cf_path = base / "data/output/cashflow_board.parquet"
    wcc_path = base / "data/output/watchlist_cashflow_confirmation.parquet"

    if not cf_path.exists() or not wcc_path.exists():
        LOGGER.warning("Cashflow board files do not exist. Skipping post-cashflow eligibility overlay.")
        return

    try:
        cf = read_parquet(cf_path)
        wcc = read_parquet(wcc_path)
    except Exception as e:
        LOGGER.error(f"Error loading cashflow data for overlay: {e}")
        return

    cr_path = base / "data/output/client_ready_watchlist.parquet"
    tw_path = base / "data/output/trading_watchlist.parquet"
    rc_path = base / "data/output/research_candidates.parquet"
    fw_path = base / "data/signals/final_watchlist.parquet"

    cr_df = read_parquet(cr_path) if cr_path.exists() else pd.DataFrame()
    tw_df = read_parquet(tw_path) if tw_path.exists() else pd.DataFrame()
    rc_df = read_parquet(rc_path) if rc_path.exists() else pd.DataFrame()
    fw_df = read_parquet(fw_path) if fw_path.exists() else pd.DataFrame()

    cr_gated = apply_eligibility_gate(cr_df, cf, wcc) if not cr_df.empty else pd.DataFrame()
    tw_gated = apply_eligibility_gate(tw_df, cf, wcc) if not tw_df.empty else pd.DataFrame()
    rc_gated = apply_eligibility_gate(rc_df, cf, wcc) if not rc_df.empty else pd.DataFrame()
    fw_gated = apply_eligibility_gate(fw_df, cf, wcc) if not fw_df.empty else pd.DataFrame()

    rejected_rows = []

    final_cr = pd.DataFrame()
    if not cr_gated.empty:
        rejected_df = cr_gated[cr_gated["eligibility_status"] == "REJECTED"].copy()
        for _, row in rejected_df.iterrows():
            sym = row["symbol"]
            cf_row = cf[cf["symbol"] == sym].iloc[0] if sym in cf["symbol"].values else None
            wcc_row = wcc[wcc["symbol"] == sym].iloc[0] if sym in wcc["symbol"].values else None

            reasons = str(row.get("eligibility_reason", ""))
            action = "Không allocate vốn cho đến khi dữ liệu giao dịch hợp lệ."
            if "ZERO_VOLUME" in reasons:
                action = "Kiểm tra lại dữ liệu volume từ nguồn SSI/sàn trước khi đưa vào client-ready."

            rejected_rows.append({
                "symbol": sym,
                "latest_date": str(row.get("date")),
                "latest_volume": float(cf_row.get("volume", 0.0)) if cf_row is not None else 0.0,
                "latest_close": float(row.get("close")),
                "cashflow_data_status": str(cf_row.get("cashflow_data_status", "OK")) if cf_row is not None else "OK",
                "confirmation_status": str(wcc_row.get("confirmation_status", "WATCH")) if wcc_row is not None else "WATCH",
                "eligibility_status": "REJECTED",
                "eligibility_reason": reasons,
                "previous_tier": "Client Ready",
                "recommended_action": action
            })
        final_cr = cr_gated[cr_gated["eligibility_status"] != "REJECTED"].copy()

    final_tw = pd.DataFrame()
    if not tw_gated.empty:
        rejected_tw = tw_gated[tw_gated["eligibility_status"] == "REJECTED"].copy()
        for _, row in rejected_tw.iterrows():
            sym = row["symbol"]
            if sym not in [r["symbol"] for r in rejected_rows]:
                cf_row = cf[cf["symbol"] == sym].iloc[0] if sym in cf["symbol"].values else None
                wcc_row = wcc[wcc["symbol"] == sym].iloc[0] if sym in wcc["symbol"].values else None
                reasons = str(row.get("eligibility_reason", ""))
                action = "Không allocate vốn cho đến khi dữ liệu giao dịch hợp lệ."
                rejected_rows.append({
                    "symbol": sym,
                    "latest_date": str(row.get("date")),
                    "latest_volume": float(cf_row.get("volume", 0.0)) if cf_row is not None else 0.0,
                    "latest_close": float(row.get("close")),
                    "cashflow_data_status": str(cf_row.get("cashflow_data_status", "OK")) if cf_row is not None else "OK",
                    "confirmation_status": str(wcc_row.get("confirmation_status", "WATCH")) if wcc_row is not None else "WATCH",
                    "eligibility_status": "REJECTED",
                    "eligibility_reason": reasons,
                    "previous_tier": "Trading Watchlist",
                    "recommended_action": action
                })
        final_tw = tw_gated[tw_gated["eligibility_status"] != "REJECTED"].copy()

    final_rc = rc_gated.copy() if not rc_gated.empty else pd.DataFrame()
    for r in rejected_rows:
        sym = r["symbol"]
        if not final_rc.empty and sym in final_rc["symbol"].values:
            idx = final_rc[final_rc["symbol"] == sym].index[0]
            final_rc.at[idx, "eligibility_status"] = "REJECTED"
            final_rc.at[idx, "eligibility_reason"] = r["eligibility_reason"]
            final_rc.at[idx, "candidate_tier"] = "Research Candidate"
            final_rc.at[idx, "is_client_ready"] = False
        else:
            orig_row = None
            for df in (cr_gated, tw_gated):
                if not df.empty and sym in df["symbol"].values:
                    orig_row = df[df["symbol"] == sym].iloc[0].copy()
                    break
            if orig_row is not None:
                orig_row["eligibility_status"] = "REJECTED"
                orig_row["eligibility_reason"] = r["eligibility_reason"]
                orig_row["candidate_tier"] = "Research Candidate"
                orig_row["is_client_ready"] = False
                final_rc = pd.concat([final_rc, pd.DataFrame([orig_row])], ignore_index=True)

    # Load and process eligible_candidates and all_scored_candidates in overlay
    ec_path = base / "data/output/eligible_candidates.parquet"
    asc_path = base / "data/output/all_scored_candidates.parquet"

    ec_df = read_parquet(ec_path) if ec_path.exists() else pd.DataFrame()
    asc_df = read_parquet(asc_path) if asc_path.exists() else pd.DataFrame()

    ec_gated = apply_eligibility_gate(ec_df, cf, wcc) if not ec_df.empty else pd.DataFrame()
    asc_gated = apply_eligibility_gate(asc_df, cf, wcc) if not asc_df.empty else pd.DataFrame()

    final_ec = ec_gated[ec_gated["eligibility_status"] == "ELIGIBLE"].copy() if not ec_gated.empty else pd.DataFrame()
    final_asc = asc_gated.copy() if not asc_gated.empty else pd.DataFrame()

    for df in (final_cr, final_tw, final_rc, final_ec, final_asc):
        if not df.empty:
            df["rank"] = np.arange(1, len(df) + 1)

    if not final_cr.empty:
        final_cr.to_csv(cr_path.with_suffix(".csv"), index=False)
        save_parquet(final_cr, cr_path)
    else:
        pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS).to_csv(cr_path.with_suffix(".csv"), index=False)
        save_parquet(pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS), cr_path)

    if not final_tw.empty:
        final_tw.to_csv(tw_path.with_suffix(".csv"), index=False)
        save_parquet(final_tw, tw_path)
    else:
        pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS).to_csv(tw_path.with_suffix(".csv"), index=False)
        save_parquet(pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS), tw_path)

    if not final_rc.empty:
        final_rc.to_csv(rc_path.with_suffix(".csv"), index=False)
        save_parquet(final_rc, rc_path)
    else:
        pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS).to_csv(rc_path.with_suffix(".csv"), index=False)
        save_parquet(pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS), rc_path)

    if not final_ec.empty:
        final_ec.to_csv(ec_path.with_suffix(".csv"), index=False)
        save_parquet(final_ec, ec_path)
    else:
        pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS).to_csv(ec_path.with_suffix(".csv"), index=False)
        save_parquet(pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS), ec_path)

    if not final_asc.empty:
        final_asc.to_csv(asc_path.with_suffix(".csv"), index=False)
        save_parquet(final_asc, asc_path)
    else:
        pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS).to_csv(asc_path.with_suffix(".csv"), index=False)
        save_parquet(pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS), asc_path)

    if not fw_gated.empty:
        final_fw = fw_gated[fw_gated["eligibility_status"] != "REJECTED"].copy()
        if not final_fw.empty:
            final_fw["rank"] = np.arange(1, len(final_fw) + 1)
            final_fw.to_csv(base / "data/signals/final_watchlist.csv", index=False)
            save_parquet(final_fw, fw_path)

    # Write data_review_watchlist
    dr_path = base / "data/output/data_review_watchlist.parquet"
    dr_cols = ["symbol", "latest_date", "latest_volume", "latest_close", "cashflow_data_status", "confirmation_status", "eligibility_status", "eligibility_reason", "previous_tier", "recommended_action"]
    if rejected_rows:
        dr_df = pd.DataFrame(rejected_rows)
    else:
        dr_df = pd.DataFrame(columns=dr_cols)

    dr_df.to_csv(dr_path.with_suffix(".csv"), index=False)
    save_parquet(dr_df, dr_path)

    # Write watchlist metadata JSON
    from src.utils.pipeline_io import write_json
    meta_path = base / "data/output/watchlist_metadata.json"
    meta_data = {
        "input_source": "stock_features.parquet",
        "input_candidate_count": int(len(final_asc)),
        "eligible_candidate_count": int(len(final_ec)),
        "client_ready_count": int(len(final_cr)),
        "trading_watchlist_count": int(len(final_tw)),
        "research_candidate_count": int(len(final_rc)),
        "data_review_count": int(len(rejected_rows)) + (int(final_asc["eligibility_status"].eq("REJECTED").sum()) if not final_asc.empty else 0),
        "client_ready_threshold": 60.0,
        "trading_threshold": 55.0,
        "generated_files": [
            str(cr_path), str(tw_path), str(rc_path), str(ec_path), str(asc_path), str(dr_path), str(meta_path)
        ],
        "generated_at": pd.Timestamp.now().isoformat(),
        "warnings": []
    }
    if not final_rc.empty:
        meta_data["data_review_count"] = int(final_rc["eligibility_status"].eq("REJECTED").sum())
    write_json(meta_data, meta_path)

    LOGGER.info(f"Post-cashflow eligibility overlay applied. Rejected symbols count: {len(rejected_rows)}")

