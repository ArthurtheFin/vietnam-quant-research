from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml

from src.data.loaders import read_parquet, save_parquet
from src.data.validators import filter_primary_equity_symbols
from src.utils.logger import get_logger
from src.utils.pipeline_io import (
    relative_path,
    utc_now_iso,
    validate_sector_board_metadata,
    write_json,
)


LOGGER = get_logger(__name__)
UNKNOWN_SECTOR = "UNKNOWN"
SECTOR_MAP_COLUMNS = ["symbol", "sector", "industry", "exchange", "source", "updated_at"]
SECTOR_OK_COVERAGE_THRESHOLD = 0.80
SECTOR_HIGH_UNKNOWN_THRESHOLD = 0.20


def _clean_nullable_text(series: pd.Series) -> pd.Series:
    out = series.copy()
    out = out.where(out.notna(), np.nan)
    out = out.astype(str).str.strip()
    return out.mask(out.str.lower().eq("nan") | out.eq(""), np.nan)


def _fill_bool_false(series: pd.Series) -> pd.Series:
    return series.astype("boolean").fillna(False).astype(bool)


def _clean_symbol_text(series: pd.Series) -> pd.Series:
    out = series.copy()
    out = out.where(out.notna(), np.nan)
    out = out.astype(str).str.upper().str.strip()
    return out.mask(out.str.lower().eq("nan") | out.eq(""), np.nan)


def _score_rank(series: pd.Series, higher_is_better: bool = True, default: float = 50.0) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return pd.Series(default, index=series.index, dtype="float64")
    base = valid if higher_is_better else -valid
    ranked = base.rank(pct=True, method="average") * 100.0
    out = pd.Series(default, index=series.index, dtype="float64")
    out.loc[ranked.index] = ranked
    return out.clip(lower=0.0, upper=100.0)


def _coerce_bool_fraction(series: pd.Series) -> float:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return np.nan
    return float(valid.mean())


def _latest_row(df: pd.DataFrame, symbol_col: str = "symbol", date_col: str = "date") -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=[date_col])
    if out.empty:
        return out
    return (
        out.sort_values([symbol_col, date_col])
        .groupby(symbol_col, as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )


def _rolling_compound_return(series: pd.Series, window: int) -> pd.Series:
    return (1.0 + pd.to_numeric(series, errors="coerce")).rolling(window, min_periods=max(3, window // 2)).apply(
        lambda values: np.prod(values) - 1.0,
        raw=True,
    )


def ensure_sector_map_template(path: str | Path) -> Path:
    template_path = Path(path)
    template_path.parent.mkdir(parents=True, exist_ok=True)
    if not template_path.exists():
        template_path.write_text(
            "symbol,sector,industry,exchange,source,updated_at\n",
            encoding="utf-8",
        )
    return template_path


def normalize_sector_map(
    sector_map: pd.DataFrame,
    default_source: str = "provided_sector_map",
    default_updated_at: str | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    default_updated_at = default_updated_at or pd.Timestamp.utcnow().date().isoformat()

    out = sector_map.copy()
    for column in SECTOR_MAP_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    out = out[SECTOR_MAP_COLUMNS].copy()
    out = out.dropna(how="all").reset_index(drop=True)

    out["symbol"] = _clean_symbol_text(out["symbol"])
    out["sector"] = _clean_nullable_text(out["sector"])
    out["industry"] = _clean_nullable_text(out["industry"])
    out["exchange"] = _clean_nullable_text(out["exchange"])
    out["source"] = _clean_nullable_text(out["source"]).fillna(default_source)
    out["updated_at"] = _clean_nullable_text(out["updated_at"]).fillna(default_updated_at)

    blank_symbols = int(out["symbol"].isna().sum())
    missing_sector_rows = int(out["sector"].isna().sum())
    duplicate_symbols = int(out["symbol"].dropna().duplicated().sum())

    out = out.dropna(subset=["symbol"]).drop_duplicates(subset=["symbol"], keep="last").reset_index(drop=True)
    return out, {
        "duplicate_symbols": duplicate_symbols,
        "blank_symbols": blank_symbols,
        "missing_sector_rows": missing_sector_rows,
    }


def load_sector_map(
    base_dir: str | Path = ".",
    sector_map_path: str | Path = "config/sector_map.csv",
    fallback_config_path: str | Path = "config/screens/stealth_accumulation.yaml",
    template_path: str | Path = "config/sector_map_template.csv",
) -> tuple[pd.DataFrame, dict[str, object]]:
    base = Path(base_dir)
    sector_map_file = base / sector_map_path
    fallback_file = base / fallback_config_path
    template_file = ensure_sector_map_template(base / template_path)

    warnings: list[str] = []
    source_path: str | None = None

    if sector_map_file.exists():
        df = pd.read_csv(sector_map_file)
        source_path = relative_path(sector_map_file, base)
    elif fallback_file.exists():
        cfg = yaml.safe_load(fallback_file.read_text(encoding="utf-8")) or {}
        symbol_map = (cfg.get("sector") or {}).get("symbol_map") or {}
        rows = [
            {
                "symbol": str(symbol).upper(),
                "sector": str(sector).strip(),
                "industry": np.nan,
                "exchange": np.nan,
                "source": relative_path(fallback_file, base),
                "updated_at": utc_now_iso(),
            }
            for symbol, sector in symbol_map.items()
            if str(symbol).strip() and str(sector).strip()
        ]
        df = pd.DataFrame(rows)
        source_path = relative_path(fallback_file, base)
        if not df.empty:
            warnings.append(
                "Using partial sector mapping from config/screens/stealth_accumulation.yaml; fill config/sector_map.csv or config/sector_map_template.csv for broader coverage."
            )
    else:
        df = pd.DataFrame(columns=["symbol", "sector", "industry", "exchange", "source", "updated_at"])

    if df.empty:
        warnings.append(
            "No dedicated sector mapping was found. Sector Board will label unmapped symbols as UNKNOWN until config/sector_map.csv is populated."
        )
        return df, {
            "source_path": source_path,
            "template_path": relative_path(template_file, base),
            "warnings": warnings,
            "rows": 0,
            "duplicate_symbols": 0,
            "blank_symbols": 0,
            "missing_sector_rows": 0,
        }

    out, stats = normalize_sector_map(
        df,
        default_source=source_path or "provided_sector_map",
        default_updated_at=pd.Timestamp.utcnow().date().isoformat(),
    )
    if stats["duplicate_symbols"] > 0:
        warnings.append(f"Sector map contains {stats['duplicate_symbols']} duplicate symbol rows; last occurrence was kept.")
    if stats["blank_symbols"] > 0:
        warnings.append(f"Sector map contains {stats['blank_symbols']} blank symbol row(s); they were dropped.")
    if stats["missing_sector_rows"] > 0:
        warnings.append(f"Sector map contains {stats['missing_sector_rows']} row(s) with missing sector.")

    return out[SECTOR_MAP_COLUMNS], {
        "source_path": source_path,
        "template_path": relative_path(template_file, base),
        "warnings": warnings,
        "rows": int(len(out)),
        "duplicate_symbols": stats["duplicate_symbols"],
        "blank_symbols": stats["blank_symbols"],
        "missing_sector_rows": stats["missing_sector_rows"],
    }


def attach_sector(
    features: pd.DataFrame,
    sector_map: pd.DataFrame | None = None,
    unknown_sector: str = UNKNOWN_SECTOR,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if features.empty:
        return features.copy(), {"warnings": ["stock_features is empty"], "mapping_coverage": 0.0}

    out = filter_primary_equity_symbols(features).copy()
    if "symbol" not in out.columns:
        return out, {"warnings": ["stock_features is missing symbol column"], "mapping_coverage": 0.0}

    out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
    if "sector" not in out.columns:
        out["sector"] = np.nan
    if "industry" not in out.columns:
        out["industry"] = np.nan

    warnings: list[str] = []
    if sector_map is not None and not sector_map.empty:
        merged = out.merge(
            sector_map[["symbol", "sector", "industry", "exchange"]].rename(
                columns={
                    "sector": "sector_map_sector",
                    "industry": "sector_map_industry",
                    "exchange": "sector_map_exchange",
                }
            ),
            on="symbol",
            how="left",
        )
        merged["sector"] = merged["sector"].combine_first(merged["sector_map_sector"])
        merged["industry"] = merged["industry"].combine_first(merged["sector_map_industry"])
        if "market" in merged.columns:
            merged["market"] = merged["market"].combine_first(merged["sector_map_exchange"])
        out = merged.drop(columns=[col for col in ["sector_map_sector", "sector_map_industry", "sector_map_exchange"] if col in merged.columns])
    else:
        warnings.append("No sector map rows are available, so all sectors default to UNKNOWN.")

    out["sector"] = out["sector"].fillna(unknown_sector).astype(str).str.strip().replace("", unknown_sector)
    out["industry"] = out["industry"].fillna("UNKNOWN").astype(str).str.strip().replace("", "UNKNOWN")
    symbol_view = out[["symbol", "sector"]].drop_duplicates(subset=["symbol"], keep="last").copy()
    total_symbols = int(symbol_view["symbol"].nunique())
    mapped_symbols = int(symbol_view["sector"].ne(unknown_sector).sum())
    missing_symbols = max(total_symbols - mapped_symbols, 0)
    mapping_coverage = float(mapped_symbols / total_symbols) if total_symbols else 0.0
    unknown_ratio = float(missing_symbols / total_symbols) if total_symbols else 1.0
    if mapping_coverage < SECTOR_OK_COVERAGE_THRESHOLD:
        warnings.append(
            f"Sector mapping coverage is only {mapping_coverage:.1%}; at least {SECTOR_OK_COVERAGE_THRESHOLD:.0%} is recommended for broad sector rotation conclusions."
        )
    if unknown_ratio >= SECTOR_HIGH_UNKNOWN_THRESHOLD:
        warnings.append(
            f"Sector mapping is incomplete: {unknown_ratio:.1%} of symbols are currently labeled {unknown_sector}."
        )

    return out, {
        "warnings": warnings,
        "mapping_coverage": mapping_coverage,
        "unknown_ratio": unknown_ratio,
        "total_symbols": total_symbols,
        "mapped_symbols": mapped_symbols,
        "missing_symbols": missing_symbols,
    }


def audit_sector_mapping(
    stock_features: pd.DataFrame,
    sector_map: pd.DataFrame | None = None,
    sector_map_source: str | None = None,
    unknown_sector: str = UNKNOWN_SECTOR,
) -> tuple[dict[str, object], pd.DataFrame]:
    universe = filter_primary_equity_symbols(stock_features).copy()
    if universe.empty or "symbol" not in universe.columns:
        empty_summary = {
            "generated_at": utc_now_iso(),
            "sector_map_source": sector_map_source,
            "total_symbols": 0,
            "mapped_symbols": 0,
            "missing_symbols": 0,
            "mapping_coverage": 0.0,
            "unknown_ratio": 1.0,
            "duplicate_symbols": 0,
            "missing_sector_rows": 0,
            "blank_symbols": 0,
        }
        return empty_summary, pd.DataFrame(columns=["symbol", "market", "sector", "industry", "exchange", "source", "updated_at", "reason"])

    if "date" in universe.columns:
        universe["date"] = pd.to_datetime(universe["date"], errors="coerce")
        universe = universe.sort_values(["symbol", "date"]).groupby("symbol", as_index=False).tail(1)
    else:
        universe = universe.drop_duplicates(subset=["symbol"], keep="last")
    universe["symbol"] = _clean_symbol_text(universe["symbol"])
    universe = universe.dropna(subset=["symbol"]).reset_index(drop=True)

    raw_map = sector_map.copy() if sector_map is not None else pd.DataFrame(columns=SECTOR_MAP_COLUMNS)
    normalized_map, map_stats = normalize_sector_map(
        raw_map,
        default_source=sector_map_source or "provided_sector_map",
        default_updated_at=pd.Timestamp.utcnow().date().isoformat(),
    )
    merged = universe.merge(normalized_map, on="symbol", how="left")
    sector_clean = _clean_nullable_text(merged["sector"])
    known_mask = sector_clean.notna() & sector_clean.str.upper().ne(unknown_sector)
    unknown_mask = sector_clean.fillna(unknown_sector).str.upper().eq(unknown_sector)

    total_symbols = int(merged["symbol"].nunique())
    mapped_symbols = int(known_mask.sum())
    missing_symbols = max(total_symbols - mapped_symbols, 0)
    mapping_coverage = float(mapped_symbols / total_symbols) if total_symbols else 0.0
    unknown_ratio = float(unknown_mask.sum() / total_symbols) if total_symbols else 1.0

    missing_mask = ~known_mask
    reason_series = pd.Series(
        np.where(sector_clean.isna(), "MISSING_IN_SECTOR_MAP", "UNKNOWN_IN_SECTOR_MAP"),
        index=merged.index,
    )
    missing_report = merged.loc[missing_mask, ["symbol"] + [col for col in ["market", "sector", "industry", "exchange", "source", "updated_at"] if col in merged.columns]].copy()
    missing_report["reason"] = reason_series.loc[missing_report.index].values
    missing_report = missing_report.sort_values(["reason", "symbol"]).reset_index(drop=True)

    summary = {
        "generated_at": utc_now_iso(),
        "sector_map_source": sector_map_source,
        "total_symbols": total_symbols,
        "mapped_symbols": mapped_symbols,
        "missing_symbols": missing_symbols,
        "mapping_coverage": mapping_coverage,
        "unknown_ratio": unknown_ratio,
        "duplicate_symbols": int(map_stats["duplicate_symbols"]),
        "missing_sector_rows": int(map_stats["missing_sector_rows"]),
        "blank_symbols": int(map_stats["blank_symbols"]),
        "n_sectors": int(normalized_map["sector"].dropna().nunique()) if not normalized_map.empty else 0,
    }
    return summary, missing_report


def _prepare_feature_history(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return features.copy()
    out = filter_primary_equity_symbols(features).copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values(["symbol", "date"]).reset_index(drop=True)

    if "turnover_proxy" not in out.columns:
        if "value" in out.columns:
            out["turnover_proxy"] = pd.to_numeric(out["value"], errors="coerce")
        else:
            out["turnover_proxy"] = pd.to_numeric(out.get("close", np.nan), errors="coerce") * pd.to_numeric(out.get("volume", np.nan), errors="coerce")

    grouped = out.groupby("symbol", group_keys=False)
    if "return_5d" not in out.columns and "close" in out.columns:
        out["return_5d"] = grouped["close"].pct_change(5)
    if "return_10d" not in out.columns and "close" in out.columns:
        out["return_10d"] = grouped["close"].pct_change(10)
    if "return_20d" not in out.columns and "close" in out.columns:
        out["return_20d"] = grouped["close"].pct_change(20)
    if "volume_ma20" not in out.columns and "volume" in out.columns:
        out["volume_ma20"] = grouped["volume"].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(20, min_periods=10).mean())
    if "value_ma20" not in out.columns:
        out["value_ma20"] = grouped["turnover_proxy"].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(20, min_periods=10).mean())
    if "volume_zscore_20d" not in out.columns and "volume" in out.columns:
        volume_mean = grouped["volume"].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(20, min_periods=10).mean())
        volume_std = grouped["volume"].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(20, min_periods=10).std())
        out["volume_zscore_20d"] = (pd.to_numeric(out["volume"], errors="coerce") - volume_mean) / volume_std.replace(0, np.nan)
    out["volume_ratio_20d"] = pd.to_numeric(out.get("volume", np.nan), errors="coerce") / pd.to_numeric(out.get("volume_ma20", np.nan), errors="coerce")
    out["turnover_20d"] = pd.to_numeric(out.get("value_ma20", np.nan), errors="coerce")
    return out


def _prepare_watchlist_flags(
    client_ready: pd.DataFrame | None = None,
    trading_watchlist: pd.DataFrame | None = None,
    research_candidates: pd.DataFrame | None = None,
) -> pd.DataFrame:
    client_ready = client_ready if client_ready is not None else pd.DataFrame()
    trading_watchlist = trading_watchlist if trading_watchlist is not None else pd.DataFrame()
    research_candidates = research_candidates if research_candidates is not None else pd.DataFrame()

    symbols = set()
    for frame in (client_ready, trading_watchlist, research_candidates):
        if not frame.empty and "symbol" in frame.columns:
            symbols.update(frame["symbol"].dropna().astype(str).str.upper().tolist())
    if not symbols:
        return pd.DataFrame(columns=["symbol", "is_client_ready", "is_trading_watchlist", "watchlist_score", "watchlist_reason"])

    universe = pd.DataFrame({"symbol": sorted(symbols)})

    def _prep(frame: pd.DataFrame, bool_col: str, score_col: str) -> pd.DataFrame:
        if frame.empty or "symbol" not in frame.columns:
            return pd.DataFrame(columns=["symbol", bool_col, score_col, "reason"])
        out = frame.copy()
        out["symbol"] = out["symbol"].astype(str).str.upper().str.strip()
        if "date" in out.columns:
            out["date"] = pd.to_datetime(out["date"], errors="coerce")
            out = out.sort_values(["symbol", "date"]).groupby("symbol", as_index=False).tail(1)
        keep_cols = ["symbol"]
        if "final_score" in out.columns:
            keep_cols.append("final_score")
        if "reason" in out.columns:
            keep_cols.append("reason")
        out = out[keep_cols].drop_duplicates(subset=["symbol"], keep="last")
        out[bool_col] = True
        out = out.rename(columns={"final_score": score_col, "reason": f"{bool_col}_reason"})
        return out

    ready = _prep(client_ready, "is_client_ready", "client_ready_score")
    trading = _prep(trading_watchlist, "is_trading_watchlist", "trading_watchlist_score")
    research = _prep(research_candidates, "is_research_candidate", "research_candidate_score")

    merged = universe.merge(ready, on="symbol", how="left")
    merged = merged.merge(trading, on="symbol", how="left")
    merged = merged.merge(research, on="symbol", how="left")
    merged["is_client_ready"] = _fill_bool_false(merged["is_client_ready"])
    merged["is_trading_watchlist"] = _fill_bool_false(merged["is_trading_watchlist"])
    merged["watchlist_score"] = pd.concat(
        [
            pd.to_numeric(merged.get("client_ready_score"), errors="coerce"),
            pd.to_numeric(merged.get("trading_watchlist_score"), errors="coerce"),
            pd.to_numeric(merged.get("research_candidate_score"), errors="coerce"),
        ],
        axis=1,
    ).max(axis=1, skipna=True)
    client_reason = merged["is_client_ready_reason"] if "is_client_ready_reason" in merged.columns else pd.Series(np.nan, index=merged.index)
    trading_reason = merged["is_trading_watchlist_reason"] if "is_trading_watchlist_reason" in merged.columns else pd.Series(np.nan, index=merged.index)
    research_reason = merged["is_research_candidate_reason"] if "is_research_candidate_reason" in merged.columns else pd.Series(np.nan, index=merged.index)
    merged["watchlist_reason"] = client_reason.combine_first(trading_reason).combine_first(research_reason)
    return merged[["symbol", "is_client_ready", "is_trading_watchlist", "watchlist_score", "watchlist_reason"]]


def _benchmark_returns(benchmark_df: pd.DataFrame | None = None) -> dict[str, float]:
    if benchmark_df is None or benchmark_df.empty:
        return {}
    bench = benchmark_df.copy()
    if "date" in bench.columns:
        bench["date"] = pd.to_datetime(bench["date"], errors="coerce")
        bench = bench.dropna(subset=["date"]).sort_values("date")
    if bench.empty:
        return {}
    if "return_5d" not in bench.columns and "close" in bench.columns:
        bench["return_5d"] = bench["close"].pct_change(5)
    if "return_10d" not in bench.columns and "close" in bench.columns:
        bench["return_10d"] = bench["close"].pct_change(10)
    if "return_20d" not in bench.columns and "close" in bench.columns:
        bench["return_20d"] = bench["close"].pct_change(20)
    latest = bench.iloc[-1]
    return {
        "return_5d": float(latest.get("return_5d")) if pd.notna(latest.get("return_5d")) else np.nan,
        "return_10d": float(latest.get("return_10d")) if pd.notna(latest.get("return_10d")) else np.nan,
        "return_20d": float(latest.get("return_20d")) if pd.notna(latest.get("return_20d")) else np.nan,
    }


def compute_sector_metrics(
    features_with_sector: pd.DataFrame,
    benchmark_df: pd.DataFrame | None = None,
    client_ready: pd.DataFrame | None = None,
    trading_watchlist: pd.DataFrame | None = None,
    research_candidates: pd.DataFrame | None = None,
    unknown_sector: str = UNKNOWN_SECTOR,
) -> pd.DataFrame:
    if features_with_sector.empty:
        return pd.DataFrame()

    prepared = _prepare_feature_history(features_with_sector)
    latest = _latest_row(prepared)
    if latest.empty:
        return pd.DataFrame()

    watchlist_flags = _prepare_watchlist_flags(client_ready, trading_watchlist, research_candidates)
    if not watchlist_flags.empty:
        latest = latest.merge(watchlist_flags, on="symbol", how="left")
    if "is_client_ready" not in latest.columns:
        latest["is_client_ready"] = False
    latest["is_client_ready"] = _fill_bool_false(latest["is_client_ready"])
    if "is_trading_watchlist" not in latest.columns:
        latest["is_trading_watchlist"] = False
    latest["is_trading_watchlist"] = _fill_bool_false(latest["is_trading_watchlist"])

    benchmark_returns = _benchmark_returns(benchmark_df)
    latest_date = pd.to_datetime(latest["date"], errors="coerce").max()

    rows: list[dict[str, object]] = []
    available_ma20 = "above_ma20" in latest.columns
    available_ma50 = "above_ma50" in latest.columns

    for sector, group in latest.groupby("sector", dropna=False):
        sector_name = str(sector or unknown_sector)
        row = {
            "sector": sector_name,
            "latest_date": None if pd.isna(latest_date) else latest_date.date().isoformat(),
            "n_symbols": int(group["symbol"].nunique()),
            "n_symbols_with_valid_data": int(group["close"].notna().sum()) if "close" in group.columns else int(len(group)),
            "sector_return_5d": float(pd.to_numeric(group.get("return_5d"), errors="coerce").mean()) if "return_5d" in group.columns else np.nan,
            "sector_return_10d": float(pd.to_numeric(group.get("return_10d"), errors="coerce").mean()) if "return_10d" in group.columns else np.nan,
            "sector_return_20d": float(pd.to_numeric(group.get("return_20d"), errors="coerce").mean()) if "return_20d" in group.columns else np.nan,
            "sector_median_return_20d": float(pd.to_numeric(group.get("return_20d"), errors="coerce").median()) if "return_20d" in group.columns else np.nan,
            "relative_return_20d_vs_vnindex": np.nan,
            "sector_turnover_20d": float(pd.to_numeric(group.get("turnover_20d"), errors="coerce").mean()) if "turnover_20d" in group.columns else np.nan,
            "sector_volume_ratio_20d": float(pd.to_numeric(group.get("volume_ratio_20d"), errors="coerce").mean()) if "volume_ratio_20d" in group.columns else np.nan,
            "sector_volume_zscore": float(pd.to_numeric(group.get("volume_zscore_20d"), errors="coerce").mean()) if "volume_zscore_20d" in group.columns else np.nan,
            "cashflow_proxy_score": np.nan,
            "pct_positive_5d": float((pd.to_numeric(group.get("return_5d"), errors="coerce") > 0).mean()) if "return_5d" in group.columns else np.nan,
            "pct_positive_20d": float((pd.to_numeric(group.get("return_20d"), errors="coerce") > 0).mean()) if "return_20d" in group.columns else np.nan,
            "pct_above_ma20": _coerce_bool_fraction(group["above_ma20"]) if available_ma20 else np.nan,
            "pct_above_ma50": _coerce_bool_fraction(group["above_ma50"]) if available_ma50 else np.nan,
            "sector_volatility_20d": float(pd.to_numeric(group.get("realized_vol_20d"), errors="coerce").mean()) if "realized_vol_20d" in group.columns else np.nan,
            "sector_avg_volatility_percentile": float(pd.to_numeric(group.get("volatility_percentile"), errors="coerce").mean()) if "volatility_percentile" in group.columns else np.nan,
            "sector_risk_label": "MEDIUM",
            "n_client_ready_symbols": int(_fill_bool_false(group["is_client_ready"]).sum()),
            "n_trading_watchlist_symbols": int(_fill_bool_false(group["is_trading_watchlist"]).sum()),
        }
        benchmark_return_20d = benchmark_returns.get("return_20d")
        if pd.notna(row["sector_return_20d"]) and benchmark_return_20d is not None and pd.notna(benchmark_return_20d):
            row["relative_return_20d_vs_vnindex"] = float(row["sector_return_20d"] - benchmark_return_20d)
        vol_pct = row["sector_avg_volatility_percentile"]
        if pd.isna(vol_pct):
            row["sector_risk_label"] = "MEDIUM"
        elif vol_pct < 0.33:
            row["sector_risk_label"] = "LOW"
        elif vol_pct < 0.67:
            row["sector_risk_label"] = "MEDIUM"
        else:
            row["sector_risk_label"] = "HIGH"
        rows.append(row)

    board = pd.DataFrame(rows)
    if board.empty:
        return board

    board["sector_strength_score"] = (
        0.45 * _score_rank(board["sector_return_20d"], higher_is_better=True)
        + 0.30 * _score_rank(board["relative_return_20d_vs_vnindex"], higher_is_better=True)
        + 0.25 * _score_rank(board["sector_median_return_20d"], higher_is_better=True)
    )
    board["cashflow_proxy_score"] = (
        0.55 * _score_rank(board["sector_turnover_20d"], higher_is_better=True)
        + 0.45 * _score_rank(board["sector_volume_ratio_20d"], higher_is_better=True)
    )
    board["sector_flow_score"] = (
        0.55 * board["cashflow_proxy_score"]
        + 0.45 * _score_rank(board["sector_volume_zscore"], higher_is_better=True)
    )

    breadth_components = []
    for col in ["pct_positive_5d", "pct_positive_20d", "pct_above_ma20", "pct_above_ma50"]:
        if col in board.columns:
            breadth_components.append(pd.to_numeric(board[col], errors="coerce") * 100.0)
    if breadth_components:
        board["sector_breadth_score"] = pd.concat(breadth_components, axis=1).mean(axis=1, skipna=True)
    else:
        board["sector_breadth_score"] = 50.0

    board["sector_risk_adjustment"] = _score_rank(board["sector_avg_volatility_percentile"], higher_is_better=False)
    board["sector_total_score"] = (
        0.40 * board["sector_strength_score"]
        + 0.25 * board["sector_flow_score"]
        + 0.25 * board["sector_breadth_score"]
        + 0.10 * board["sector_risk_adjustment"]
    ).clip(lower=0.0, upper=100.0)
    board["sector_rank"] = board["sector_total_score"].rank(method="first", ascending=False).astype(int)
    board["sector_label"] = np.select(
        [
            board["sector_total_score"] >= 75,
            board["sector_total_score"] >= 60,
            board["sector_total_score"] >= 45,
            board["sector_total_score"] >= 30,
        ],
        ["LEADING", "IMPROVING", "NEUTRAL", "WEAK"],
        default="AVOID",
    )
    return board.sort_values(["sector_rank", "sector"], ascending=[True, True]).reset_index(drop=True)


def build_sector_leaders(
    features_with_sector: pd.DataFrame,
    client_ready: pd.DataFrame | None = None,
    trading_watchlist: pd.DataFrame | None = None,
    research_candidates: pd.DataFrame | None = None,
    top_n: int = 5,
) -> pd.DataFrame:
    if features_with_sector.empty:
        return pd.DataFrame()

    prepared = _prepare_feature_history(features_with_sector)
    latest = _latest_row(prepared)
    if latest.empty:
        return latest

    flags = _prepare_watchlist_flags(client_ready, trading_watchlist, research_candidates)
    if not flags.empty:
        latest = latest.merge(flags, on="symbol", how="left")
    if "is_client_ready" not in latest.columns:
        latest["is_client_ready"] = False
    latest["is_client_ready"] = _fill_bool_false(latest["is_client_ready"])
    if "is_trading_watchlist" not in latest.columns:
        latest["is_trading_watchlist"] = False
    latest["is_trading_watchlist"] = _fill_bool_false(latest["is_trading_watchlist"])

    score_parts = []
    for column, higher_is_better in [
        ("return_20d", True),
        ("return_5d", True),
        ("volume_ratio_20d", True),
        ("value_ma20", True),
        ("watchlist_score", True),
    ]:
        if column in latest.columns:
            score_parts.append(_score_rank(latest[column], higher_is_better=higher_is_better))
    if score_parts:
        latest["leader_score"] = pd.concat(score_parts, axis=1).mean(axis=1, skipna=True)
    else:
        latest["leader_score"] = 50.0

    output_rows: list[pd.DataFrame] = []
    for sector, group in latest.groupby("sector", dropna=False):
        ranked = group.sort_values(["leader_score", "return_20d", "return_5d"], ascending=[False, False, False]).head(top_n).copy()
        ranked["leader_rank_in_sector"] = range(1, len(ranked) + 1)
        reasons = []
        for _, row in ranked.iterrows():
            reason_parts = []
            if pd.notna(row.get("return_20d")):
                reason_parts.append(f"20D return {row['return_20d']:.1%}")
            if pd.notna(row.get("volume_ratio_20d")):
                reason_parts.append(f"volume ratio {row['volume_ratio_20d']:.2f}x")
            if bool(row.get("is_client_ready", False)):
                reason_parts.append("client-ready confirmation")
            elif bool(row.get("is_trading_watchlist", False)):
                reason_parts.append("trading-watchlist confirmation")
            if not reason_parts:
                reason_parts.append("relative sector leadership")
            reasons.append(", ".join(reason_parts))
        ranked["leader_reason"] = reasons
        output_rows.append(ranked)

    if not output_rows:
        return pd.DataFrame()

    leaders = pd.concat(output_rows, ignore_index=True)
    keep_cols = [
        "sector",
        "symbol",
        "date",
        "leader_rank_in_sector",
        "return_5d",
        "return_20d",
        "volume_ratio_20d",
        "watchlist_score",
        "is_client_ready",
        "is_trading_watchlist",
        "leader_reason",
    ]
    leaders = leaders[[col for col in keep_cols if col in leaders.columns]].copy()
    leaders = leaders.rename(columns={"watchlist_score": "relative_strength_score", "date": "latest_date"})
    if "latest_date" in leaders.columns:
        leaders["latest_date"] = pd.to_datetime(leaders["latest_date"], errors="coerce").dt.date.astype(str)
    return leaders.sort_values(["sector", "leader_rank_in_sector"]).reset_index(drop=True)


def rank_sectors(sector_board: pd.DataFrame, leaders: pd.DataFrame | None = None) -> pd.DataFrame:
    if sector_board.empty:
        return sector_board.copy()
    out = sector_board.copy()
    if leaders is None or leaders.empty:
        out["top_symbol_1"] = np.nan
        out["top_symbol_2"] = np.nan
        out["top_symbol_3"] = np.nan
        return out

    for rank in [1, 2, 3]:
        rank_map = (
            leaders[leaders["leader_rank_in_sector"] == rank][["sector", "symbol"]]
            .drop_duplicates(subset=["sector"], keep="first")
            .set_index("sector")["symbol"]
        )
        out[f"top_symbol_{rank}"] = out["sector"].map(rank_map)
    return out


def build_sector_board(
    stock_features: pd.DataFrame,
    benchmark_vnindex: pd.DataFrame | None = None,
    client_ready: pd.DataFrame | None = None,
    trading_watchlist: pd.DataFrame | None = None,
    research_candidates: pd.DataFrame | None = None,
    sector_map: pd.DataFrame | None = None,
    sector_map_metadata: dict[str, object] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    sector_map_metadata = sector_map_metadata or {"warnings": []}
    attached, attach_meta = attach_sector(stock_features, sector_map=sector_map)
    audit_summary, _ = audit_sector_mapping(
        stock_features=stock_features,
        sector_map=sector_map,
        sector_map_source=sector_map_metadata.get("source_path"),
    )
    board = compute_sector_metrics(
        attached,
        benchmark_df=benchmark_vnindex,
        client_ready=client_ready,
        trading_watchlist=trading_watchlist,
        research_candidates=research_candidates,
    )
    leaders = build_sector_leaders(
        attached,
        client_ready=client_ready,
        trading_watchlist=trading_watchlist,
        research_candidates=research_candidates,
    )
    board = rank_sectors(board, leaders)

    warnings = list(sector_map_metadata.get("warnings", [])) + list(attach_meta.get("warnings", []))
    latest_date = None
    if not board.empty and "latest_date" in board.columns:
        latest_date = str(board["latest_date"].dropna().iloc[0])
    coverage = float(audit_summary.get("mapping_coverage", attach_meta.get("mapping_coverage", 0.0)))
    unknown_ratio = float(audit_summary.get("unknown_ratio", attach_meta.get("unknown_ratio", 1.0)))
    status = "OK"
    if board.empty:
        status = "ERROR"
        warnings.append("Sector Board could not be built because no sector rows were produced.")
    elif coverage < SECTOR_OK_COVERAGE_THRESHOLD or unknown_ratio >= SECTOR_HIGH_UNKNOWN_THRESHOLD:
        status = "WARNING"

    metadata = {
        "generated_at": utc_now_iso(),
        "status": status,
        "latest_date": latest_date,
        "n_sectors": int(board["sector"].nunique()) if "sector" in board.columns else 0,
        "sector_map_source": sector_map_metadata.get("source_path"),
        "sector_map_rows": int(sector_map_metadata.get("rows", 0)),
        "sector_map_template": sector_map_metadata.get("template_path"),
        "mapping_coverage": coverage,
        "unknown_ratio": unknown_ratio,
        "total_symbols": int(audit_summary.get("total_symbols", attach_meta.get("total_symbols", 0))),
        "mapped_symbols": int(audit_summary.get("mapped_symbols", attach_meta.get("mapped_symbols", 0))),
        "missing_symbols": int(audit_summary.get("missing_symbols", attach_meta.get("missing_symbols", 0))),
        "warnings": warnings,
        "generated_files": [],
    }
    return board, leaders, metadata


def write_sector_outputs(
    sector_board: pd.DataFrame,
    sector_leaders: pd.DataFrame,
    metadata: dict[str, object],
    base_dir: str | Path = ".",
    output_dir: str | Path = "data/output",
) -> dict[str, object]:
    base = Path(base_dir)
    out_dir = base / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    board_parquet = out_dir / "sector_board.parquet"
    board_csv = out_dir / "sector_board.csv"
    leaders_parquet = out_dir / "sector_leaders.parquet"
    leaders_csv = out_dir / "sector_leaders.csv"
    metadata_json = out_dir / "sector_board_metadata.json"

    save_parquet(sector_board, board_parquet)
    sector_board.to_csv(board_csv, index=False)
    save_parquet(sector_leaders, leaders_parquet)
    sector_leaders.to_csv(leaders_csv, index=False)

    generated_files = [
        relative_path(board_parquet, base),
        relative_path(board_csv, base),
        relative_path(leaders_parquet, base),
        relative_path(leaders_csv, base),
        relative_path(metadata_json, base),
    ]
    payload = dict(metadata)
    payload["generated_files"] = generated_files
    validate_sector_board_metadata(payload)
    write_json(payload, metadata_json)
    LOGGER.info("Sector Board outputs written: %s", ", ".join(generated_files))
    return payload


def load_sector_board_inputs(
    base_dir: str | Path = ".",
) -> dict[str, pd.DataFrame | dict[str, object]]:
    base = Path(base_dir)
    sector_map, sector_map_meta = load_sector_map(base)
    return {
        "stock_features": read_parquet(base / "data/processed/stock_features.parquet"),
        "benchmark_vnindex": read_parquet(base / "data/processed/benchmark_vnindex.parquet"),
        "client_ready": read_parquet(base / "data/output/client_ready_watchlist.parquet"),
        "trading_watchlist": read_parquet(base / "data/output/trading_watchlist.parquet"),
        "research_candidates": read_parquet(base / "data/output/research_candidates.parquet"),
        "sector_map": sector_map,
        "sector_map_metadata": sector_map_meta,
    }
