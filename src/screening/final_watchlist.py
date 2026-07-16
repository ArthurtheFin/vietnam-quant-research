from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.dataset_config import OFFICIAL_FEATURES_PATH
from src.data.loaders import read_parquet, save_parquet, save_csv_atomic
from src.data.validators import filter_primary_equity_symbols
from src.utils.scoring import deep_merge
from src.utils.logger import get_logger

SECTOR_MAP_PATH = Path("config/sector_map.csv")

LOGGER = get_logger("final_watchlist")


FINAL_WATCHLIST_COLUMNS = [
    "rank",
    "symbol",
    "date",
    "analysis_as_of",
    "data_age_days",
    "close",
    "value_ma20",
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
    "cashflow_verification",
    "rank_universe_size",
]


DEFAULT_FINAL_WATCHLIST_CONFIG: dict[str, Any] = {
    "watchlist_size": 10,
    "trading_watchlist_size": 20,
    "benchmark_symbol": "VNINDEX",
    "min_history_days": 120,
    "min_price": 5000.0,  # VND; close prices are raw VND, not thousands (audit C1)
    "min_value_ma20": 5_000_000_000.0,
    "min_volume_ma20": 50_000.0,
    "max_atr_pct": 0.08,
    "max_relaxed_atr_pct": 0.12,
    "max_distance_ma20": 0.23,  # loosened from 0.18 per FACTOR_RETEST_V2_REPORT.md NV4:
    # distance_ma20 shows no significant IC on clean full-2020+ data (max |t_NW|=1.61);
    # reducing this gate's weight rather than removing it outright, since it separately
    # posts the 2nd-highest raw event-detection lift of 47 candidates tested (not yet
    # statistically confirmed -- flagged for a dedicated follow-up, not acted on here)
    "max_relaxed_distance_ma20": 0.33,  # loosened from 0.28, same proportional widening
    "max_drawdown_60d": -0.30,
    "client_ready_threshold": 60.0,
    "trading_threshold": 55.0,
    # WATCHLIST_VALIDATION_PREREG.md / WATCHLIST_VALIDATION_REPORT.md (GD4):
    # first-ever IC/null-test of this composite. RESULT: Nhanh C ("ca hai
    # khong dat") -- neither base_final_score (composite, null-test fold
    # 2026 percentile=0.15 vs the required >=10 floor; IC full/residualized
    # t_NW=-0.40, not even same-signed across the 3 periods) nor the
    # "watchlist toi gian" alternative (v2_score + final_watchlist's own
    # strict_pass/fallback_eligible gate; null avg percentile=52.8 vs the
    # required >60; IC period 1 t_NW=+2.90, just under the 3.0 bar though
    # periods 2/3 cleared it at +3.03/+8.94) cleared the pre-registered bar.
    # `ranking_mode` below is set to "no_alpha_liquidity_sort" as a result --
    # see that key for what this changes. All 7 component scores below are
    # STILL COMPUTED (informational/diagnostic display only, `reason` text,
    # research use) but NONE of them drive `client_ready_watchlist`/
    # `trading_watchlist` selection or order anymore.
    #
    # Per-component evidence on record (WATCHLIST_VALIDATION_REPORT.md IC
    # table, full universe/residualized target unless noted):
    # - liquidity: t_NW=-4.19, ACTIVELY WRONG-SIGNED (current direction
    #   rewards high value_ma20; also contaminated either direction by
    #   survivorship bias per SURVIVORSHIP_BIAS_ESTIMATE.md) -- excluded
    #   from base_final_score's sum unconditionally (see _score()), the one
    #   component removal not contingent on the Nhanh C outcome above.
    # - risk: t_NW=+4.72, same-signed positive in all 3 periods (though
    #   period 1 alone is weak at +1.49) -- unvalidated for RANKING purposes
    #   under Nhanh C's blanket no-alpha-ranking rule. CLOSED (ROBUSTNESS_REPORT.md
    #   GD5 mục 3, decision round GD5.5): NOT an independent factor -- corr
    #   +0.822 with v2_score, its 3 real contributors are all volatility
    #   variants duplicating evidence v2 already uses. No standalone prereg;
    #   see _score()'s risk_raw block for the component-level breakdown.
    # - trend/momentum/relative_strength/volume/signal: all |t_NW|<2.2 or
    #   undefined (signal_score: data/signals/meta_ranking.parquet turned out
    #   to be a current-state snapshot with no real historical depth, not a
    #   time series -- IC undefined by construction, n=0). "unvalidated,
    #   giữ vì hiển thị tham khảo/nghiên cứu, không dùng để xếp hạng."
    # Note: momentum_score and relative_strength_score are numerically
    # IDENTICAL under _rank() (subtracting the same-day benchmark return is a
    # per-day constant, which does not change cross-sectional rank order) --
    # a real redundancy in the deployed formula, confirmed by their IC
    # numbers matching exactly in every row of the test; noted for any future
    # redesign, not changed here (not part of this round's locked scope).
    "ranking_mode": "no_alpha_liquidity_sort",  # WATCHLIST_VALIDATION_REPORT.md Nhanh C.
    # "score" (final_score-driven ranking) is the pre-GD4 behavior, kept as a
    # code path for tests/rollback, not used in production as of this round.
    "weights": {
        "trend": 27.78,
        "momentum": 22.22,
        "relative_strength": 22.22,
        "liquidity": 10,  # informational display column only -- excluded from base_final_score, see _score()
        "volume": 5.56,
        "risk": 11.11,
        "signal": 11.11,
    },
    "paths": {
        "features": OFFICIAL_FEATURES_PATH,
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
    # D5: stock_features.parquet carries forward_return_Nd columns for backtest/
    # research use; strip them here so no live scoring step can ever see them.
    from src.validation.guards import assert_no_forward_columns

    latest = assert_no_forward_columns(latest, context="final_watchlist.build_watchlist_tiers", mode="drop")
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
        except Exception as exc:
            LOGGER.warning("Failed to read cashflow board (%s); gate will treat it as missing.", exc)
    else:
        LOGGER.warning("Cashflow board artifact not found; Client Ready tier will be demoted (audit F1).")
    if wcc_path.exists():
        try:
            wcc = read_parquet(wcc_path)
        except Exception as exc:
            LOGGER.warning("Failed to read watchlist cashflow confirmation (%s).", exc)

    from src.validation.trading_status import excluded_symbols_by_status, low_coverage_symbols

    try:
        inactive_long_symbols = excluded_symbols_by_status()
    except Exception as exc:
        LOGGER.warning("Failed to read trading_status table (%s); no symbols excluded by status.", exc)
        inactive_long_symbols = set()

    try:
        low_coverage = low_coverage_symbols()
    except Exception as exc:
        LOGGER.warning("Failed to read coverage-ratio snapshot (%s); none flagged.", exc)
        low_coverage = set()

    latest = apply_eligibility_gate(latest, cashflow_board, wcc, inactive_long_symbols, low_coverage)

    return _redistribute_after_gate(latest, cfg)


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
    save_csv_atomic(watchlist, csv_path)
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
    from src.validation.guards import assert_no_forward_columns

    cfg = deep_merge(DEFAULT_FINAL_WATCHLIST_CONFIG, config or {})
    paths = cfg["paths"]
    base = Path(base_dir)
    output_dir = base / paths.get("output_dir", "data/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # D5: this can be called standalone (apply_post_cashflow_overlay) without going
    # through build_watchlist_tiers' drop step -- guard independently here too.
    outputs = {
        name: assert_no_forward_columns(frame, context=f"final_watchlist.save_watchlist_outputs[{name}]", mode="drop")
        for name, frame in outputs.items()
    }

    saved_paths = save_final_watchlist(outputs.get("client_ready_watchlist", pd.DataFrame()), cfg, base_dir=base)

    mapping = {
        "research_candidates": output_dir / "research_candidates",
        "trading_watchlist": output_dir / "trading_watchlist",
        "client_ready_watchlist": output_dir / "client_ready_watchlist",
        "eligible_candidates": output_dir / "eligible_candidates",
        "all_scored_candidates": output_dir / "all_scored_candidates",
        "data_review_watchlist": output_dir / "data_review_watchlist",
    }
    for name, stem in mapping.items():
        frame = outputs.get(name, pd.DataFrame())
        csv_path = stem.with_suffix(".csv")
        parquet_path = stem.with_suffix(".parquet")
        save_csv_atomic(frame, csv_path)
        save_parquet(frame, parquet_path)
        saved_paths[f"{name}_csv"] = csv_path
        saved_paths[f"{name}_parquet"] = parquet_path

    # Write watchlist metadata JSON
    from src.utils.pipeline_io import (
        build_lineage_metadata,
        relative_path,
        validate_lineage_metadata,
        write_json,
    )
    
    meta_path = output_dir / "watchlist_metadata.json"
    client_threshold = float(cfg.get("client_ready_threshold", 60.0))
    trading_threshold = float(cfg.get("trading_threshold", 55.0))
    meta_data = {
        "input_source": str(paths.get("features", "stock_features.parquet")),
        "input_candidate_count": int(len(outputs.get("scored_universe", pd.DataFrame()))),
        "eligible_candidate_count": int(len(outputs.get("eligible_candidates", pd.DataFrame()))),
        "client_ready_count": int(len(outputs.get("client_ready_watchlist", pd.DataFrame()))),
        "trading_watchlist_count": int(len(outputs.get("trading_watchlist", pd.DataFrame()))),
        "research_candidate_count": int(len(outputs.get("research_candidates", pd.DataFrame()))),
        "data_review_count": int(len(outputs.get("data_review_watchlist", pd.DataFrame()))),
        "client_ready_threshold": client_threshold,
        "trading_threshold": trading_threshold,
        "generated_files": [relative_path(stem.with_suffix(".parquet"), base) for stem in mapping.values()] + [relative_path(meta_path, base)],
        "generated_at": pd.Timestamp.now().isoformat(),
        "warnings": [],
        "lineage": validate_lineage_metadata(
            build_lineage_metadata(paths.get("features", OFFICIAL_FEATURES_PATH), base_dir=base),
            label="watchlist_metadata.json",
        ),
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
    # NOTE: NONE of the v1 shadow's per-component scores are merged in here
    # (momentum_score, rs_score, trend_score, volume_score, volatility_score,
    # liquidity_score). SCORE_FORENSIC_REPORT.md found the v1 composite had
    # no significant standalone IC anywhere tested, and specifically that
    # rs_score's IC flipped from +0.0141 (2023-2025) to -0.1060 in 2026 --
    # the largest negative-IC component in that fold, one of the primary
    # drivers of a real -59.7% backtest loss. It was being merged in here as
    # `alpha_rs_score` and consumed by relative_strength_score below (audit
    # critical finding P0-4 / gate #17) -- removed, along with the other four
    # renamed-but-never-consumed v1 columns (trend/volume/volatility/
    # liquidity), which were dead weight riding along in this DataFrame with
    # no consumer anywhere in _score() but still leaking into unrestricted
    # output paths like data_review_watchlist. v1's components remain
    # available for shadow comparison only in data/signals/alpha_scores.parquet
    # and data/signals/alpha_score_shadow_log.parquet -- never here.
    keep = [c for c in ["symbol", "alpha_score"] if c in alpha.columns]
    return df.merge(alpha[keep], on="symbol", how="left")


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
    from src.validation.guards import assert_no_forward_columns

    assert_no_forward_columns(df, context="final_watchlist._score", mode="raise")
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

    # alpha_score removed from this average: since SCORE_V2_REPORT.md,
    # alpha_score (from data/signals/alpha_scores.parquet) is the v2
    # composite (70% realized_vol_20d + 30% value_ma20, rewarding LOW vol
    # and LOW liquidity) -- a volatility/liquidity signal, not a momentum
    # one. Averaging it into "momentum" was a semantic mismatch left over
    # from before v2 was installed.
    #
    # alpha_momentum_score (the v1 shadow composite's own momentum_score)
    # is also removed from this average, not just alpha_score: SCORE_FORENSIC_REPORT.md
    # found this factor's IC was ~0 over 2023-2025 and -0.1050 in 2026 --
    # the single largest negative IC of any component in that fold, and a
    # direct hypothesis test confirmed the cohort it ranked highest went on
    # to underperform (see SCORE_FORENSIC_REPORT.md's momentum/RS section).
    # v1 remains available as a shadow score for ongoing comparison; it is
    # not a validated input for the live product screen.
    momentum_raw = pd.concat(
        [
            _rank(out["return_20d"]),
            _rank(out["return_60d"]),
        ],
        axis=1,
    ).mean(axis=1)
    out["momentum_score"] = (momentum_raw * weights["momentum"]).round(2)

    # alpha_rs_score removed from this average (audit P0-4 / gate #17):
    # SCORE_FORENSIC_REPORT.md found the v1 shadow's rs_score IC flipped to
    # -0.1060 in 2026, one of the primary drivers of a real -59.7% backtest
    # loss. Mirrors the momentum_score fix (commits 517a3d0/327b8d4) applied
    # to its sibling component earlier -- this was the missed twin.
    rs_raw = pd.concat(
        [
            _rank(out.get("excess_return_20d", pd.Series(np.nan, index=out.index))),
            _rank(out.get("excess_return_60d", pd.Series(np.nan, index=out.index))),
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

    # ROBUSTNESS_REPORT.md (GD5) mục 3 / WATCHLIST_VALIDATION_REPORT.md mục 2:
    # risk_score's 3 real contributors (atr_pct_14 t_NW=-5.70, realized_vol_20d
    # -5.48, volatility_percentile -3.16) are all volatility variants -- corr
    # +0.822 with v2_score, i.e. duplicate evidence of the same underlying
    # signal v2 already uses, not an independent factor (closed, no standalone
    # prereg). tail_ratio_60d: unvalidated, giữ vì hiển thị tham khảo -- t_NW=+0.98
    # (full, residualized), không có ý nghĩa thống kê, không đóng góp thật vào
    # bằng chứng của risk_score. risk_penalty_score: unvalidated, giữ vì hiển
    # thị tham khảo -- luôn NaN->0.5 trung lập trong lịch sử (data/signals/
    # meta_ranking.parquet là snapshot hiện tại, không phải chuỗi lịch sử, xem
    # WATCHLIST_VALIDATION_REPORT.md mục 2 phát hiện #4), không đóng góp biến
    # thiên cross-sectional nào.
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
    # liquidity_score excluded from the ranking sum (WATCHLIST_VALIDATION_PREREG.md /
    # _REPORT.md, GD4) -- computed above for informational display only, no
    # validated direction. The other 6 weights are pre-scaled (see `weights`
    # above) so this still sums to 100.
    out["base_final_score"] = out[["trend_score", "momentum_score", "relative_strength_score", "volume_score", "risk_score", "signal_score"]].sum(axis=1).clip(0, 100).round(2)
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

    # G1: how many candidates this score was ranked against — the 0-100 score is a
    # cross-sectional rank within this pool, not an absolute quality measure.
    out["rank_universe_size"] = int(len(out))

    out["is_stale_data"] = warning_series.str.contains("Stale data", case=False, na=False)
    out["is_missing_backtest_evidence"] = warning_series.str.contains("Missing backtest evidence", case=False, na=False)
    out["is_low_liquidity_warning"] = warning_series.str.contains("Low liquidity", case=False, na=False)
    out["is_weak_market_regime"] = warning_series.str.contains("Weak market regime", case=False, na=False)
    # G1: a real (non-NaN) negative excess return vs benchmark is a hard floor for
    # Client Ready, not just an 8-point warning penalty a high score can absorb.
    if "excess_return_20d" in out.columns:
        out["is_weak_relative_strength"] = pd.to_numeric(out["excess_return_20d"], errors="coerce").lt(0)
    else:
        out["is_weak_relative_strength"] = False

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
        & ~out["is_weak_relative_strength"]
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
        if row["is_weak_relative_strength"] and row["is_trading_candidate"]:
            reasons.append("Weak relative strength (demoted from Client Ready)")
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
    text = ", ".join(phrases[:3]).capitalize() + "."
    # G1: the 0-100 score is a rank within this pool, not an absolute measure —
    # say so explicitly rather than implying universe-wide quality.
    universe_size = row.get("rank_universe_size")
    if pd.notna(universe_size) and int(universe_size) > 0:
        text += f" (Xếp hạng tương đối trong {int(universe_size)} mã được chấm điểm.)"
    return text


def _ensure_watchlist_output_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if out.empty:
        return pd.DataFrame(columns=FINAL_WATCHLIST_COLUMNS)
    for col in FINAL_WATCHLIST_COLUMNS:
        if col not in out.columns:
            if col in [
                "rank", "data_age_days", "base_final_score", "warning_penalty",
                "trend_score", "momentum_score", "relative_strength_score",
                "volume_score", "liquidity_score", "risk_score", "signal_score",
                "latest_volume", "rank_universe_size", "value_ma20",
            ]:
                out[col] = np.nan
            elif col in ["is_research_candidate", "is_trading_candidate", "is_client_ready"]:
                out[col] = False
            elif col == "eligibility_status":
                out[col] = "UNKNOWN"
            elif col in ["cashflow_data_status", "confirmation_status"]:
                out[col] = "UNKNOWN"
            else:
                out[col] = None
    return out[FINAL_WATCHLIST_COLUMNS]


_SECTOR_MAP_CACHE: dict[str, str] | None = None


def _load_sector_map(path: Path = SECTOR_MAP_PATH) -> dict[str, str]:
    """WATCHLIST_VALIDATION_PREREG.md (GD4): sector mapping is NOT mandatory
    for eligibility (96.4% coverage, current impact only 4 research-tier
    symbols per audit/SECTOR_MAPPING_COVERAGE_REPORT.md NV7) but IS mandatory
    for the sector cap below -- unmapped symbols fall into their own "UNKNOWN"
    bucket, capped identically to a real sector (same convention already
    default in src/backtest/portfolio_backtest.py's max_per_sector, confirmed
    correct there, extended here to final_watchlist's own tier output which
    previously had no sector-cap logic at all)."""
    global _SECTOR_MAP_CACHE
    if _SECTOR_MAP_CACHE is not None:
        return _SECTOR_MAP_CACHE
    if not path.exists():
        _SECTOR_MAP_CACHE = {}
        return _SECTOR_MAP_CACHE
    df = read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    _SECTOR_MAP_CACHE = dict(zip(df["symbol"], df["sector"]))
    return _SECTOR_MAP_CACHE


def _select_with_sector_cap(ranked_pool: pd.DataFrame, limit: int, max_per_sector: int = 2) -> pd.DataFrame:
    """Greedy top-N-by-existing-rank-order selection capped at `max_per_sector`
    names per sector (symbols missing from config/sector_map.csv count as
    sector "UNKNOWN", capped the same as any real sector). `ranked_pool` must
    already be sorted in the desired priority order -- this only filters, it
    never re-sorts."""
    if ranked_pool.empty or limit <= 0:
        return ranked_pool.head(0)
    sector_map = _load_sector_map()
    sector_counts: dict[str, int] = {}
    keep_idx = []
    for idx, row in ranked_pool.iterrows():
        sector = sector_map.get(str(row["symbol"]), "UNKNOWN")
        if sector_counts.get(sector, 0) >= max_per_sector:
            continue
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        keep_idx.append(idx)
        if len(keep_idx) >= limit:
            break
    return ranked_pool.loc[keep_idx]


def _redistribute_after_gate(scored_universe: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, pd.DataFrame]:
    out = scored_universe.copy()
    if out.empty:
        empty = _ensure_watchlist_output_columns(pd.DataFrame())
        return {
            "scored_universe": out,
            "research_candidates": empty.copy(),
            "trading_watchlist": empty.copy(),
            "client_ready_watchlist": empty.copy(),
            "eligible_candidates": empty.copy(),
            "all_scored_candidates": empty.copy(),
            "data_review_watchlist": pd.DataFrame(columns=list(out.columns)),
        }

    client_threshold = float(cfg.get("client_ready_threshold", 60.0))
    trading_threshold = float(cfg.get("trading_threshold", 55.0))
    client_limit = int(cfg.get("watchlist_size", 10))
    trading_limit = int(cfg.get("trading_watchlist_size", 20))
    no_alpha_mode = str(cfg.get("ranking_mode", "score")) == "no_alpha_liquidity_sort"

    defaults: dict[str, Any] = {
        "final_score": 0.0,
        "trade_edge_score": 0.0,
        "setup_quality_score": 0.0,
        "eligibility_status": "ELIGIBLE",
        "cashflow_data_status": "OK",
        "confirmation_status": "WATCH",
        "eligibility_reason": "None",
        "exclusion_reason": "",
        "warning": "",
        "confidence_label": "Excluded",
        "is_stale_data": False,
        "is_missing_backtest_evidence": False,
        "is_low_liquidity_warning": False,
        "is_weak_market_regime": False,
    }
    if no_alpha_mode and "reason" in out.columns:
        # WATCHLIST_VALIDATION_REPORT.md Nhanh C: label this plainly in the
        # one free-text column every output row already carries, since
        # FINAL_WATCHLIST_COLUMNS is a fixed schema (adding a new column
        # would just get stripped by _ensure_watchlist_output_columns).
        # Idempotent: _redistribute_after_gate can run twice on the same rows
        # in one pipeline invocation (build_watchlist_tiers, then
        # apply_post_cashflow_overlay re-reading the saved output) -- guard
        # against double-prepending.
        disclaimer = "[Không xếp hạng alpha, chỉ sắp theo thanh khoản -- xem WATCHLIST_VALIDATION_REPORT.md] "
        reason_col = out["reason"].fillna("").astype(str)
        out["reason"] = np.where(reason_col.str.startswith(disclaimer), reason_col, disclaimer + reason_col)

    for column, default in defaults.items():
        if column not in out.columns:
            out[column] = default

    out["final_score"] = pd.to_numeric(out["final_score"], errors="coerce").fillna(0.0)
    out["trade_edge_score"] = pd.to_numeric(out["trade_edge_score"], errors="coerce").fillna(0.0)
    out["setup_quality_score"] = pd.to_numeric(out["setup_quality_score"], errors="coerce").fillna(0.0)
    out["cashflow_data_status"] = out["cashflow_data_status"].fillna("OK").astype(str)
    out["confirmation_status"] = out["confirmation_status"].fillna("WATCH").astype(str)
    out["eligibility_status"] = out["eligibility_status"].fillna("REJECTED").astype(str)
    out["eligibility_reason"] = out["eligibility_reason"].fillna("None").astype(str)
    out["warning"] = out["warning"].fillna("").astype(str)

    if no_alpha_mode:
        # WATCHLIST_VALIDATION_REPORT.md (GD4), Nhanh C: neither base_final_score
        # nor the v2-ranked "watchlist toi gian" cleared the pre-registered bar
        # (composite: null-test fold 2026 percentile=0.15 < the 10 floor; minimal
        # watchlist: null avg 52.8 < 60, IC period 1 t_NW=2.90 just under the 3.0
        # bar) -- final_watchlist has no validated alpha-ranking factor as of this
        # round. Rank by value_ma20 (liquidity, an operational measure, not a
        # tested alpha factor) instead of final_score.
        ranking = out.sort_values(
            ["value_ma20", "symbol"], ascending=[False, True], na_position="last",
        ).reset_index(drop=True)
    else:
        ranking = out.sort_values(
            ["final_score", "trade_edge_score", "setup_quality_score", "symbol"],
            ascending=[False, False, False, True],
            na_position="last",
        ).reset_index(drop=True)

    eligible_mask = ranking["eligibility_status"].isin(["ELIGIBLE", "WATCH_ONLY"])
    hard_reject_mask = ranking["eligibility_status"].eq("REJECTED")
    client_confirm_allowed = ~ranking["confirmation_status"].isin(["CHECK_REQUIRED", "REJECT"])
    trading_confirm_allowed = ranking["confirmation_status"].isin(["STRONG_CONFIRMED", "CONFIRMED", "NEUTRAL_CONFIRMED", "WATCH"])
    cashflow_ok_mask = ranking["cashflow_data_status"].eq("OK")
    client_warning_block = (
        ranking["is_stale_data"].astype(bool)
        | ranking["is_missing_backtest_evidence"].astype(bool)
        | ranking["is_weak_market_regime"].astype(bool)
    )

    client_score_ok = pd.Series(True, index=ranking.index) if no_alpha_mode else ranking["final_score"].ge(client_threshold)
    trading_score_ok = pd.Series(True, index=ranking.index) if no_alpha_mode else ranking["final_score"].ge(trading_threshold)

    client_pool = ranking[
        eligible_mask
        & cashflow_ok_mask
        & client_confirm_allowed
        & (~client_warning_block)
        & client_score_ok
    ].copy()
    client_ready = _select_with_sector_cap(client_pool, client_limit).copy()
    client_syms = set(client_ready["symbol"].astype(str))

    trading_pool = ranking[
        eligible_mask
        & cashflow_ok_mask
        & trading_confirm_allowed
        & trading_score_ok
        & (~ranking["symbol"].isin(client_syms))
    ].copy()
    trading = _select_with_sector_cap(trading_pool, trading_limit).copy()
    trading_syms = set(trading["symbol"].astype(str))

    data_review = ranking[hard_reject_mask].copy()
    data_review_syms = set(data_review["symbol"].astype(str))
    active_syms = client_syms.union(trading_syms)
    research = ranking[(~ranking["symbol"].isin(active_syms)) & (~ranking["symbol"].isin(data_review_syms))].copy()
    eligible = ranking[eligible_mask].copy()

    out["is_client_ready"] = out["symbol"].isin(client_syms)
    out["is_trading_candidate"] = out["symbol"].isin(trading_syms)
    out["is_research_candidate"] = (~out["symbol"].isin(active_syms)) & (~out["symbol"].isin(data_review_syms))
    out_reject_mask = out["symbol"].isin(data_review_syms)
    out["candidate_tier"] = np.select(
        [
            out["is_client_ready"],
            out["is_trading_candidate"],
            out_reject_mask,
            out["is_research_candidate"],
        ],
        [
            "Client Ready",
            "Trading Watchlist",
            "Data Review",
            "Research Candidate",
        ],
        default="Excluded",
    )

    def _reason_for_research(row: pd.Series) -> str:
        if str(row.get("eligibility_status", "")) == "REJECTED":
            return str(row.get("eligibility_reason", "REJECTED"))
        if no_alpha_mode:
            return "Outside liquidity rank cutoff (no validated alpha ranking -- see WATCHLIST_VALIDATION_REPORT.md)"
        if pd.to_numeric(row.get("final_score"), errors="coerce") < trading_threshold:
            return "Below trading threshold"
        if str(row.get("cashflow_data_status", "OK")) != "OK":
            return "Cashflow data not ready"
        if str(row.get("confirmation_status", "WATCH")) not in {"STRONG_CONFIRMED", "CONFIRMED", "NEUTRAL_CONFIRMED", "WATCH"}:
            return "Trading confirmation pending"
        return "Reserved for deeper research"

    out["exclusion_reason"] = out.apply(
        lambda row: ""
        if row["symbol"] in active_syms
        else (
            str(row.get("eligibility_reason", "REJECTED"))
            if str(row.get("eligibility_status", "")) == "REJECTED"
            else _reason_for_research(row)
        ),
        axis=1,
    )
    out.loc[out["is_client_ready"], "confidence_label"] = np.where(
        out.loc[out["is_client_ready"], "final_score"].ge(70.0),
        "High",
        "Medium-High",
    )
    out.loc[out["is_trading_candidate"], "confidence_label"] = "Medium"
    out.loc[out["candidate_tier"] == "Research Candidate", "confidence_label"] = "Low"
    out.loc[out["candidate_tier"] == "Data Review", "confidence_label"] = "REVIEW_REQUIRED"

    display_sort_cols = ["value_ma20", "symbol"] if no_alpha_mode else ["final_score", "symbol"]
    display_sort_ascending = [False, True]

    outputs = {
        "scored_universe": out.sort_values(
            ["is_client_ready", "is_trading_candidate", "is_research_candidate"] + display_sort_cols,
            ascending=[False, False, False] + display_sort_ascending,
        ).reset_index(drop=True),
        "research_candidates": out[out["symbol"].isin(research["symbol"])].copy(),
        "trading_watchlist": out[out["symbol"].isin(trading_syms)].copy(),
        "client_ready_watchlist": out[out["symbol"].isin(client_syms)].copy(),
        "eligible_candidates": out[out["symbol"].isin(eligible["symbol"])].copy(),
        "all_scored_candidates": out.copy(),
        "data_review_watchlist": out[out["symbol"].isin(data_review["symbol"])].copy(),
    }

    for key, frame in outputs.items():
        if key == "scored_universe":
            continue
        if not frame.empty:
            frame = frame.sort_values(display_sort_cols, ascending=display_sort_ascending).reset_index(drop=True)
            frame["rank"] = np.arange(1, len(frame) + 1)
            outputs[key] = _ensure_watchlist_output_columns(frame) if key != "data_review_watchlist" else frame.copy()
        else:
            outputs[key] = _ensure_watchlist_output_columns(pd.DataFrame()) if key != "data_review_watchlist" else pd.DataFrame(columns=list(out.columns))

    outputs["scored_universe"]["rank"] = np.arange(1, len(outputs["scored_universe"]) + 1)
    return outputs

def apply_eligibility_gate(
    df: pd.DataFrame,
    cashflow_board: pd.DataFrame | None = None,
    watchlist_cashflow_confirmation: pd.DataFrame | None = None,
    inactive_long_symbols: set[str] | None = None,
    low_coverage_symbols: set[str] | None = None,
) -> pd.DataFrame:
    """`inactive_long_symbols`: symbols to reject as INACTIVE_LONG, sourced
    from src.validation.trading_status.excluded_symbols_by_status() by the
    caller (never hardcoded here) -- audit PATH_TO_100.md Universe/Eligibility
    item, first step toward a point-in-time universe (Gate #3), not a full
    solution (still can't see symbols delisted before entering today's
    listed-symbol universe at all).

    `low_coverage_symbols`: symbols whose rolling trading-day coverage ratio
    is below threshold, sourced from
    src.validation.trading_status.low_coverage_symbols() -- folded into the
    existing LOW_LIQUIDITY reason (not a separate reason/status), per
    trading_status.py's docstring: coverage ratio alone cannot reliably
    distinguish "thin but real" from "suspended", so it must not create a
    second, competing classification."""
    if df.empty:
        return df.copy()
    inactive_long_symbols = inactive_long_symbols or set()
    low_coverage_symbols = low_coverage_symbols or set()

    out = df.copy()

    # F1: verify cashflow artifact presence/recency — never silently default to OK.
    as_of = None
    for col in ("analysis_as_of", "date"):
        if col in out.columns:
            as_of = pd.to_datetime(out[col], errors="coerce").max()
            break

    cashflow_verification = "VERIFIED"
    if cashflow_board is None or cashflow_board.empty:
        cashflow_verification = "UNVERIFIED_MISSING_ARTIFACT"
    elif "date" in cashflow_board.columns and as_of is not None:
        board_date = pd.to_datetime(cashflow_board["date"], errors="coerce").max()
        if pd.isna(board_date) or board_date < as_of:
            cashflow_verification = "UNVERIFIED_STALE_ARTIFACT"
    elif "date" not in cashflow_board.columns:
        LOGGER.warning("Cashflow board has no date column; recency cannot be verified.")
    out["cashflow_verification"] = cashflow_verification

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

        # Rolling coverage-ratio proxy (audit PATH_TO_100.md Universe/Eligibility
        # item) -- folded into the same LOW_LIQUIDITY reason, not a new one
        # (see trading_status.py's low_coverage_symbols docstring).
        if sym in low_coverage_symbols:
            reasons.append("LOW_LIQUIDITY")

        if cf_state == "DISTRIBUTION_RISK":
            reasons.append("SEVERE_DISTRIBUTION_RISK")

        if sym in inactive_long_symbols:
            reasons.append("INACTIVE_LONG")

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

    # F1: without a same-day cashflow board, Client Ready cannot be certified —
    # demote to Trading Watchlist (not a full reject) and say why.
    if cashflow_verification != "VERIFIED" and "candidate_tier" in out.columns:
        LOGGER.warning(
            "Cashflow board %s — demoting Client Ready candidates to Trading Watchlist.",
            cashflow_verification,
        )
        demote_mask = (out["eligibility_status"] == "ELIGIBLE") & (out["candidate_tier"] == "Client Ready")
        for idx in out.index[demote_mask]:
            out.at[idx, "is_client_ready"] = False
            out.at[idx, "candidate_tier"] = "Trading Watchlist"
            out.at[idx, "eligibility_reason"] = f"CASHFLOW_{cashflow_verification}"

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
    except Exception as exc:
        LOGGER.error("Error loading cashflow data for overlay: %s", exc)
        return

    asc_path = base / "data/output/all_scored_candidates.parquet"
    cr_path = base / "data/output/client_ready_watchlist.parquet"
    tw_path = base / "data/output/trading_watchlist.parquet"
    rc_path = base / "data/output/research_candidates.parquet"
    fw_path = base / "data/signals/final_watchlist.parquet"

    universe = read_parquet(asc_path) if asc_path.exists() else pd.DataFrame()
    if universe.empty:
        frames = [
            read_parquet(path)
            for path in (cr_path, tw_path, rc_path, fw_path)
            if path.exists()
        ]
        frames = [frame for frame in frames if not frame.empty]
        if frames:
            universe = pd.concat(frames, ignore_index=True)
            sort_cols = [col for col in ["symbol", "final_score"] if col in universe.columns]
            if sort_cols:
                ascending = [True, False] if sort_cols == ["symbol", "final_score"] else [True]
                universe = universe.sort_values(sort_cols, ascending=ascending)
            universe = universe.drop_duplicates(subset=["symbol"], keep="first").reset_index(drop=True)

    if universe.empty:
        LOGGER.warning("No scored universe available for post-cashflow overlay.")
        return

    from src.validation.trading_status import excluded_symbols_by_status, low_coverage_symbols

    try:
        inactive_long_symbols = excluded_symbols_by_status()
    except Exception as exc:
        LOGGER.warning("Failed to read trading_status table (%s); no symbols excluded by status.", exc)
        inactive_long_symbols = set()

    try:
        low_coverage = low_coverage_symbols()
    except Exception as exc:
        LOGGER.warning("Failed to read coverage-ratio snapshot (%s); none flagged.", exc)
        low_coverage = set()

    gated_universe = apply_eligibility_gate(universe, cf, wcc, inactive_long_symbols, low_coverage)
    outputs = _redistribute_after_gate(gated_universe, DEFAULT_FINAL_WATCHLIST_CONFIG)
    save_watchlist_outputs(outputs, config=DEFAULT_FINAL_WATCHLIST_CONFIG, base_dir=base)

    save_csv_atomic(outputs["client_ready_watchlist"], fw_path.with_suffix(".csv"))
    save_parquet(outputs["client_ready_watchlist"], fw_path)
    LOGGER.info(
        "Applied post-cashflow overlay. client_ready=%s trading=%s research=%s data_review=%s",
        len(outputs["client_ready_watchlist"]),
        len(outputs["trading_watchlist"]),
        len(outputs["research_candidates"]),
        len(outputs["data_review_watchlist"]),
    )

