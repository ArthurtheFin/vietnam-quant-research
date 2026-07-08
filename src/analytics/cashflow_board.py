from __future__ import annotations

import os
import json
from pathlib import Path
import numpy as np
import pandas as pd

from src.data.loaders import read_parquet, save_parquet
from src.utils.logger import get_logger
from src.utils.pipeline_io import (
    relative_path,
    utc_now_iso,
    write_json,
)
from src.analytics.sector_board import attach_sector, load_sector_map

LOGGER = get_logger(__name__)


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


def _fill_bool_false(series: pd.Series) -> pd.Series:
    return series.astype("boolean").fillna(False).astype(bool)


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


def load_cashflow_inputs(base_dir: str | Path = ".") -> dict[str, pd.DataFrame | dict[str, object]]:
    base = Path(base_dir)
    sector_map, sector_map_meta = load_sector_map(base)
    
    # Safe load datasets
    def _read_safe(p: Path) -> pd.DataFrame:
        if not p.exists():
            LOGGER.warning(f"File not found: {p}")
            return pd.DataFrame()
        return read_parquet(p)

    return {
        "stock_features": _read_safe(base / "data/processed/stock_features.parquet"),
        "benchmark_vnindex": _read_safe(base / "data/processed/benchmark_vnindex.parquet"),
        "client_ready": _read_safe(base / "data/output/client_ready_watchlist.parquet"),
        "trading_watchlist": _read_safe(base / "data/output/trading_watchlist.parquet"),
        "research_candidates": _read_safe(base / "data/output/research_candidates.parquet"),
        "sector_map": sector_map,
        "sector_map_metadata": sector_map_meta,
    }


def compute_symbol_cashflow_metrics(
    features_with_sector: pd.DataFrame,
    benchmark_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, bool]:
    if features_with_sector.empty:
        return pd.DataFrame(), False

    out = features_with_sector.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"]).sort_values(["symbol", "date"]).reset_index(drop=True)

    value_proxy_used = False
    if "value" not in out.columns or out["value"].isna().all():
        out["cashflow_value"] = pd.to_numeric(out.get("close", np.nan), errors="coerce") * pd.to_numeric(out.get("volume", np.nan), errors="coerce")
        value_proxy_used = True
    else:
        out["cashflow_value"] = pd.to_numeric(out["value"], errors="coerce")
        # If there are still mostly NaNs in value, fall back to proxy
        if out["cashflow_value"].isna().sum() / len(out) > 0.5:
            out["cashflow_value"] = out["cashflow_value"].fillna(
                pd.to_numeric(out.get("close", np.nan), errors="coerce") * pd.to_numeric(out.get("volume", np.nan), errors="coerce")
            )
            value_proxy_used = True

    grouped = out.groupby("symbol", group_keys=False)

    # volume rolling
    volume_col = "volume" if "volume" in out.columns else "volume_ma20"  # fallback
    if volume_col in out.columns:
        out["volume_ma5"] = grouped[volume_col].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(5, min_periods=3).mean())
        out["volume_ma20"] = grouped[volume_col].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(20, min_periods=10).mean())
        out["volume_ratio_5d"] = pd.to_numeric(out[volume_col], errors="coerce") / out["volume_ma5"]
        out["volume_ratio_20d"] = pd.to_numeric(out[volume_col], errors="coerce") / out["volume_ma20"]
        
        # calculate zscore if not present or has all nan
        if "volume_zscore_20d" not in out.columns or out["volume_zscore_20d"].isna().all():
            vol_std = grouped[volume_col].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(20, min_periods=10).std())
            out["volume_zscore_20d"] = (pd.to_numeric(out[volume_col], errors="coerce") - out["volume_ma20"]) / vol_std.replace(0, np.nan)
    else:
        out["volume_ratio_5d"] = np.nan
        out["volume_ratio_20d"] = np.nan
        out["volume_zscore_20d"] = np.nan

    # value rolling
    out["cashflow_value_20d"] = grouped["cashflow_value"].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(20, min_periods=10).mean())
    out["cashflow_value_ratio_20d"] = out["cashflow_value"] / out["cashflow_value_20d"]

    # Check for recent zero volume count on history
    if "volume" in out.columns:
        out["zero_vol_5d_count"] = grouped["volume"].transform(
            lambda s: (pd.to_numeric(s, errors="coerce") == 0).rolling(5, min_periods=1).sum()
        ).fillna(0).astype(int)
    else:
        out["zero_vol_5d_count"] = 0

    # performance metrics
    if "return_5d" not in out.columns and "close" in out.columns:
        out["return_5d"] = grouped["close"].pct_change(5)
    if "return_10d" not in out.columns and "close" in out.columns:
        out["return_10d"] = grouped["close"].pct_change(10)
    if "return_20d" not in out.columns and "close" in out.columns:
        out["return_20d"] = grouped["close"].pct_change(20)

    # get latest row per symbol
    latest = _latest_row(out)
    if latest.empty:
        return latest, value_proxy_used

    # Data Quality and Liquidity Flags
    latest["zero_volume_flag"] = _fill_bool_false(latest["volume"] == 0)
    latest["missing_volume_flag"] = _fill_bool_false(latest["volume"].isna())
    latest["liquidity_flag"] = _fill_bool_false(latest["cashflow_value_20d"] >= 100000000.0)
    latest["data_quality_flag"] = _fill_bool_false(
        latest["zero_volume_flag"] | latest["missing_volume_flag"] | latest["close"].isna() | (latest["zero_vol_5d_count"] >= 3)
    )

    status_list = []
    for idx, row in latest.iterrows():
        is_missing = pd.isna(row.get("volume")) or pd.isna(row.get("close"))
        is_zero = row.get("volume") == 0
        is_low_liq = pd.isna(row.get("cashflow_value_20d")) or row.get("cashflow_value_20d") < 100000000.0
        is_anomaly = row.get("zero_vol_5d_count", 0) >= 3
        
        if is_missing:
            status = "MISSING_DATA"
        elif is_zero:
            status = "ZERO_VOLUME"
        elif is_anomaly:
            status = "CHECK_REQUIRED"
        elif is_low_liq:
            status = "LOW_LIQUIDITY"
        else:
            status = "OK"
        status_list.append(status)
    latest["cashflow_data_status"] = status_list

    # cashflow intensity score
    latest["cashflow_intensity_score"] = 0.5 * _score_rank(latest["volume_ratio_20d"]) + 0.5 * _score_rank(latest["cashflow_value_ratio_20d"])

    # outperformance vs benchmark
    bench_return_20d = 0.0
    if benchmark_df is not None and not benchmark_df.empty:
        bench = benchmark_df.copy()
        if "date" in bench.columns:
            bench["date"] = pd.to_datetime(bench["date"], errors="coerce")
            bench = bench.dropna(subset=["date"]).sort_values("date")
        if not bench.empty:
            latest_bench_row = bench.iloc[-1]
            if "return_20d" in latest_bench_row:
                bench_return_20d = float(latest_bench_row["return_20d"])
            elif "close" in bench.columns:
                bench["return_20d"] = bench["close"].pct_change(20)
                bench_return_20d = float(bench.iloc[-1].get("return_20d", 0.0))

    latest["relative_return_20d_vs_vnindex"] = pd.to_numeric(latest.get("return_20d", 0.0), errors="coerce") - bench_return_20d

    # standard confirmations
    latest["price_volume_confirmation"] = _fill_bool_false((latest["return_5d"] > 0.0) & (latest["volume_ratio_20d"] > 1.2))
    latest["breakout_volume_confirmation"] = _fill_bool_false((latest["return_5d"] > 0.03) & (latest["volume_zscore_20d"] > 1.5))
    
    if "volatility_percentile" in latest.columns:
        vol_pct = pd.to_numeric(latest["volatility_percentile"], errors="coerce").fillna(0.5)
    else:
        vol_pct = pd.Series(0.5, index=latest.index)
        
    latest["accumulation_signal"] = _fill_bool_false(
        (latest["return_10d"] >= -0.02) & (latest["return_10d"] <= 0.05) & 
        (latest["volume_ratio_20d"] > 1.0) & (vol_pct < 0.60)
    )
    latest["distribution_risk"] = _fill_bool_false(
        (latest["return_5d"] < -0.02) & 
        ((latest["volume_ratio_20d"] > 1.2) | (latest["volume_zscore_20d"] > 1.0))
    )
    latest["dry_up_signal"] = _fill_bool_false(
        (latest["return_10d"] >= -0.03) & (latest["return_10d"] <= 0.03) & 
        (latest["volume_ratio_20d"] < 0.7)
    )
    
    # DRY_UP_WATCH signal (volatility < 40%, return consolidates between -2% and 3%, volume ratio < 0.7)
    latest["dry_up_watch_signal"] = _fill_bool_false(
        (latest["return_10d"] >= -0.02) & (latest["return_10d"] <= 0.03) &
        (latest["volume_ratio_20d"] < 0.7) & (vol_pct < 0.40) &
        latest["cashflow_data_status"].isin(["OK", "LOW_LIQUIDITY"])
    )

    # Classify State
    latest["cashflow_state"] = np.select(
        [
            latest["cashflow_data_status"].isin(["MISSING_DATA", "ZERO_VOLUME"]),
            latest["distribution_risk"],
            latest["breakout_volume_confirmation"] | (latest["price_volume_confirmation"] & (latest["return_5d"] >= 0.01)),
            latest["accumulation_signal"],
            latest["dry_up_watch_signal"],
            (latest["volume_ratio_20d"] < 0.8) & (latest["return_5d"] <= 0.0),
        ],
        [
            "CHECK_REQUIRED",
            "DISTRIBUTION_RISK",
            "CONFIRMED_INFLOW",
            "ACCUMULATION",
            "DRY_UP_WATCH",
            "WEAK_FLOW",
        ],
        default="NEUTRAL",
    )

    # Calculate Cashflow Score
    # 35% volume/value confirmation
    vol_val_part = latest["cashflow_intensity_score"]
    # 25% price confirmation
    ret_5d_rank = _score_rank(latest["return_5d"])
    ret_20d_rank = _score_rank(latest["return_20d"])
    price_part = 0.6 * ret_5d_rank + 0.4 * ret_20d_rank
    # 20% relative strength vs VNINDEX
    rs_part = _score_rank(latest["relative_return_20d_vs_vnindex"])
    # 10% liquidity
    liq_part = _score_rank(latest["cashflow_value_20d"])
    # 10% risk penalty (100 - volatility_percentile)
    vol_score = vol_pct * 100.0
    risk_part = 100.0 - vol_score

    raw_score = (
        0.35 * vol_val_part +
        0.25 * price_part +
        0.20 * rs_part +
        0.10 * liq_part +
        0.10 * risk_part
    )
    
    # Apply deduction if distribution risk is flagged
    score = np.where(latest["cashflow_state"] == "DISTRIBUTION_RISK", raw_score - 15.0, raw_score)
    latest["cashflow_score"] = np.clip(pd.to_numeric(score, errors="coerce"), 0.0, 100.0)
    latest["cashflow_score"] = latest["cashflow_score"].fillna(50.0)

    # Classify label
    latest["cashflow_label"] = np.select(
        [
            latest["cashflow_state"] == "CHECK_REQUIRED",
            (latest["cashflow_state"] == "CONFIRMED_INFLOW") & (latest["cashflow_score"] >= 70.0),
            (latest["cashflow_state"] == "ACCUMULATION") | (latest["cashflow_state"] == "DRY_UP_WATCH") | (latest["cashflow_score"] >= 60.0),
            latest["cashflow_state"] == "DISTRIBUTION_RISK",
            (latest["cashflow_state"] == "WEAK_FLOW") | (latest["cashflow_score"] < 40.0),
        ],
        [
            "NEUTRAL",
            "STRONG",
            "IMPROVING",
            "RISKY",
            "WEAK",
        ],
        default="NEUTRAL",
    )

    latest["cashflow_rank"] = latest["cashflow_score"].rank(method="first", ascending=False).fillna(999).astype(int)

    return latest, value_proxy_used


def compute_sector_cashflow_metrics(
    symbol_cashflow: pd.DataFrame,
    latest_date: str | None = None,
) -> pd.DataFrame:
    if symbol_cashflow.empty:
        return pd.DataFrame()

    rows = []
    for sector, group in symbol_cashflow.groupby("sector", dropna=False):
        sector_name = str(sector or "UNKNOWN")
        n_symbols = int(group["symbol"].nunique())
        
        # Valid symbols mask (has volume > 0 and close and volume are non-missing)
        valid_mask = group["volume"].notna() & (group["volume"] > 0) & group["close"].notna()
        n_symbols_valid = int(group.loc[valid_mask, "symbol"].nunique())
        
        # Sector aggregations
        sector_cashflow_value_20d = float(pd.to_numeric(group["cashflow_value_20d"], errors="coerce").sum())
        sector_cashflow_intensity = float(pd.to_numeric(group["cashflow_intensity_score"], errors="coerce").mean())
        sector_avg_volume_ratio_20d = float(pd.to_numeric(group["volume_ratio_20d"], errors="coerce").mean())
        
        # State fractions
        sector_pct_confirmed_inflow = float((group["cashflow_state"] == "CONFIRMED_INFLOW").mean())
        sector_pct_accumulation = float((group["cashflow_state"] == "ACCUMULATION").mean())
        sector_pct_distribution_risk = float((group["cashflow_state"] == "DISTRIBUTION_RISK").mean())
        
        avg_cf_score = float(group["cashflow_score"].mean()) if not group.empty else 50.0
        median_cf_score = float(group["cashflow_score"].median()) if not group.empty else 50.0
        
        # Top 3 cashflow symbols in sector
        top_symbols_list = (
            group.sort_values("cashflow_score", ascending=False)
            .head(3)["symbol"]
            .tolist()
        )
        top_cashflow_symbols = ", ".join(top_symbols_list)
        
        rows.append({
            "sector": sector_name,
            "latest_date": latest_date,
            "n_symbols": n_symbols,
            "n_symbols_with_valid_cashflow": n_symbols_valid,
            "sector_liquidity_20d": sector_cashflow_value_20d,
            "sector_cashflow_intensity": sector_cashflow_intensity,
            "sector_avg_volume_ratio_20d": sector_avg_volume_ratio_20d,
            "sector_pct_confirmed_inflow": sector_pct_confirmed_inflow,
            "sector_pct_accumulation": sector_pct_accumulation,
            "sector_pct_distribution_risk": sector_pct_distribution_risk,
            "avg_cf_score": avg_cf_score,
            "median_cf_score": median_cf_score,
            "top_cashflow_symbols": top_cashflow_symbols,
        })
        
    sector_board = pd.DataFrame(rows)
    if sector_board.empty:
        return sector_board
        
    # Classify sample size
    sector_board["sector_sample_size_label"] = np.select(
        [
            sector_board["n_symbols_with_valid_cashflow"] < 5,
            sector_board["n_symbols_with_valid_cashflow"] <= 15
        ],
        ["SMALL", "NORMAL"],
        default="LARGE"
    )

    # Compute raw score
    raw_score = (
        0.30 * sector_board["avg_cf_score"] +
        0.20 * sector_board["median_cf_score"] +
        0.30 * (sector_board["sector_pct_confirmed_inflow"] * 100.0) +
        0.20 * (sector_board["sector_pct_accumulation"] * 100.0)
    )

    # Determine 70th percentile threshold for sector liquidity
    liq_threshold = sector_board["sector_liquidity_20d"].quantile(0.70)
    if pd.isna(liq_threshold) or liq_threshold <= 0:
        liq_threshold = 1000000000.0  # 1B VND fallback
        
    # Apply Calibration / Penalties for SMALL sectors
    is_small = sector_board["sector_sample_size_label"] == "SMALL"
    is_top_liq = sector_board["sector_liquidity_20d"] >= liq_threshold
    
    calibrated_score = np.where(
        is_small & ~is_top_liq,
        raw_score * 0.7,  # 30% penalty
        raw_score
    )
    # Small sectors with high liquidity still get 10% penalty
    calibrated_score = np.where(
        is_small & is_top_liq,
        calibrated_score * 0.9,  # 10% penalty
        calibrated_score
    )
    
    sector_board["sector_cashflow_score"] = np.clip(calibrated_score, 0.0, 100.0)
    sector_board["sector_cashflow_rank"] = sector_board["sector_cashflow_score"].rank(method="first", ascending=False).astype(int)
    
    # Sector Labels
    labels = np.select(
        [
            sector_board["sector_cashflow_score"] >= 70.0,
            sector_board["sector_cashflow_score"] >= 55.0,
            (sector_board["sector_pct_distribution_risk"] > 0.20) & (sector_board["sector_cashflow_score"] < 50.0),
            sector_board["sector_cashflow_score"] < 40.0,
        ],
        [
            "STRONG_INFLOW",
            "IMPROVING",
            "DISTRIBUTION_RISK",
            "WEAK",
        ],
        default="NEUTRAL",
    )
    sector_board["sector_cashflow_label"] = labels
    
    # Demote label for SMALL sectors: cap at IMPROVING (or NEUTRAL if low liquidity)
    sector_board["sector_cashflow_label"] = np.where(
        (sector_board["sector_sample_size_label"] == "SMALL") & (sector_board["sector_cashflow_label"] == "STRONG_INFLOW"),
        np.where(is_top_liq, "IMPROVING", "NEUTRAL"),
        sector_board["sector_cashflow_label"]
    )
    
    # Score Quality
    liq_50 = sector_board["sector_liquidity_20d"].quantile(0.50)
    liq_20 = sector_board["sector_liquidity_20d"].quantile(0.20)
    
    quality = np.select(
        [
            (sector_board["sector_sample_size_label"] == "LARGE") & (sector_board["sector_liquidity_20d"] >= liq_50),
            (sector_board["sector_sample_size_label"] == "SMALL") | (sector_board["sector_liquidity_20d"] < liq_20),
        ],
        ["HIGH", "LOW"],
        default="MEDIUM"
    )
    sector_board["sector_score_quality"] = quality
    
    # Score Warnings
    warnings_list = []
    for idx, row in sector_board.iterrows():
        warns = []
        if row["sector_sample_size_label"] == "SMALL":
            warns.append("Small sample size (N < 5) may skew score")
        if row["sector_liquidity_20d"] < 500000000.0:  # 500M VND
            warns.append("Low sector liquidity")
        warnings_list.append("; ".join(warns) if warns else "")
    sector_board["sector_score_warning"] = warnings_list
    
    # Clean up columns
    sector_board = sector_board.drop(columns=["avg_cf_score", "median_cf_score"])
    
    return sector_board.sort_values("sector_cashflow_rank").reset_index(drop=True)


def build_cashflow_watchlist_confirmation(
    symbol_cashflow: pd.DataFrame,
    client_ready: pd.DataFrame | None = None,
    trading_watchlist: pd.DataFrame | None = None,
    research_candidates: pd.DataFrame | None = None,
) -> pd.DataFrame:
    client_ready = client_ready if client_ready is not None else pd.DataFrame()
    trading_watchlist = trading_watchlist if trading_watchlist is not None else pd.DataFrame()
    research_candidates = research_candidates if research_candidates is not None else pd.DataFrame()

    watchlist_rows = []
    
    def _add_watchlist(df: pd.DataFrame, tier_name: str) -> None:
        if df.empty or "symbol" not in df.columns:
            return
        symbols = df["symbol"].dropna().astype(str).str.upper().str.strip().unique()
        for sym in symbols:
            watchlist_rows.append({
                "symbol": sym,
                "watchlist_tier": tier_name
            })
            
    _add_watchlist(client_ready, "client_ready")
    _add_watchlist(trading_watchlist, "trading_watchlist")
    _add_watchlist(research_candidates, "research_candidates")
    
    if not watchlist_rows:
        return pd.DataFrame(columns=[
            "symbol", "sector", "watchlist_tier", "cashflow_score", "cashflow_state",
            "cashflow_label", "confirmation_status", "cashflow_reason", "cashflow_action_note"
        ])
        
    watchlist_df = pd.DataFrame(watchlist_rows)
    # Deduplicate keeping client_ready > trading_watchlist > research_candidates
    watchlist_df["tier_rank"] = watchlist_df["watchlist_tier"].map({
        "client_ready": 1,
        "trading_watchlist": 2,
        "research_candidates": 3
    })
    watchlist_df = (
        watchlist_df.sort_values(["symbol", "tier_rank"])
        .drop_duplicates(subset=["symbol"], keep="first")
        .drop(columns=["tier_rank"])
    )
    
    # Merge with cashflow metrics
    cf_subset = symbol_cashflow[[
        "symbol", "sector", "cashflow_score", "cashflow_state", "cashflow_label",
        "volume_ratio_20d", "return_5d", "cashflow_data_status"
    ]]
    
    merged = watchlist_df.merge(cf_subset, on="symbol", how="inner")
    if merged.empty:
        return pd.DataFrame(columns=[
            "symbol", "sector", "watchlist_tier", "cashflow_score", "cashflow_state",
            "cashflow_label", "confirmation_status", "cashflow_reason", "cashflow_action_note"
        ])
        
    status_list = []
    reason_list = []
    action_note_list = []
    
    for _, row in merged.iterrows():
        tier = row["watchlist_tier"]
        label = row["cashflow_label"]
        state = row["cashflow_state"]
        vol_ratio = row["volume_ratio_20d"]
        ret_5d = row["return_5d"]
        data_status = row["cashflow_data_status"]
        
        status = "WATCH"
        reason = "Theo dõi: dòng tiền ở trạng thái trung tính."
        action_note = "Quan sát hành vi giá ở các ngưỡng hỗ trợ, chưa vội hành động."
        
        if data_status in ("MISSING_DATA", "ZERO_VOLUME"):
            status = "CHECK_REQUIRED"
            reason = "Cần kiểm tra: volume hiện tại bằng 0 hoặc thiếu dữ liệu, không đủ cơ sở kết luận dòng tiền."
            action_note = "Tạm ngưng giao dịch để xác minh dữ liệu giá/khối lượng từ sàn."
        elif data_status == "LOW_LIQUIDITY":
            status = "CAUTION"
            reason = f"Cảnh báo: Cổ phiếu có thanh khoản cực thấp (giá trị giao dịch 20D < 100 triệu VND)."
            action_note = "Hạn chế mua mới, cẩn trọng rủi ro thanh khoản thấp."
        elif state == "DISTRIBUTION_RISK":
            if tier == "research_candidates":
                status = "REJECT"
                reason = "Loại bỏ: Tín hiệu phân phối rõ rệt (giá giảm mạnh trên khối lượng lớn)."
                action_note = "Loại khỏi watchlist theo dõi dòng tiền ngắn hạn."
            else:
                status = "CAUTION"
                reason = f"Cảnh báo: Áp lực phân phối (giá giảm {ret_5d:.1%} trên volume lớn {vol_ratio:.2f}x)."
                action_note = "Dừng mua mới và cân nhắc hạ tỷ trọng vị thế hiện tại."
        elif state == "DRY_UP_WATCH":
            status = "WATCH"
            reason = f"Theo dõi kiệt cung (Dry-up): giá giữ nền ổn định, volume cạn kiệt ({vol_ratio:.2f}x trung bình)."
            action_note = "Theo dõi chặt chẽ, chuẩn bị mua thăm dò khi có tín hiệu breakout xác nhận."
        else:
            if tier == "client_ready":
                if label == "STRONG":
                    status = "STRONG_CONFIRMED"
                    reason = f"Xác nhận mạnh: volume tăng mạnh {vol_ratio:.2f}x trung bình, giá tăng {ret_5d:.1%}."
                    action_note = "Khuyến nghị MUA/GIA TĂNG tỷ trọng khi đạt điểm breakout."
                elif label == "IMPROVING":
                    status = "CONFIRMED"
                    reason = f"Xác nhận: dòng tiền đang cải thiện (trạng thái {state}, volume ratio {vol_ratio:.2f}x)."
                    action_note = "Khuyến nghị NẮM GIỮ hoặc TÍCH LŨY THÊM tại vùng nền giá."
                elif label == "WEAK":
                    status = "WATCH"
                    reason = f"Theo dõi: dòng tiền yếu, volume ratio chỉ đạt {vol_ratio:.2f}x trung bình."
                    action_note = "Hạn chế mua đuổi, quan sát thêm phản ứng tại các vùng hỗ trợ."
                else:
                    status = "NEUTRAL_CONFIRMED"
                    reason = f"Xác nhận trung tính: dòng tiền ổn định ở mức trung bình ({vol_ratio:.2f}x)."
                    action_note = "Nắm giữ vị thế hiện tại, chưa cần hành động mua/bán vội."
            elif tier == "trading_watchlist":
                if state == "ACCUMULATION":
                    status = "CONFIRMED"
                    reason = "Xác nhận: Phát hiện dấu hiệu tích lũy âm thầm (Stealth Accumulation)."
                    action_note = "Khuyến nghị TÍCH LŨY thăm dò tại vùng nền giá."
                elif label in ("STRONG", "IMPROVING"):
                    status = "CONFIRMED"
                    reason = f"Xác nhận: Dòng tiền vào hỗ trợ xu hướng tăng (volume ratio {vol_ratio:.2f}x)."
                    action_note = "Nắm giữ và canh điểm mua gia tăng vị thế."
                elif label == "WEAK":
                    status = "WATCH"
                    reason = f"Theo dõi: Thiết lập kỹ thuật thiếu sự xác nhận từ volume ({vol_ratio:.2f}x)."
                    action_note = "Kiên nhẫn chờ đợi dòng tiền lớn vào xác nhận trước khi mở vị thế."
                else:
                    status = "NEUTRAL_CONFIRMED"
                    reason = "Theo dõi trung tính: khối lượng duy trì ổn định quanh mức trung bình."
                    action_note = "Nắm giữ vị thế cũ, chưa mở mua mới."
            elif tier == "research_candidates":
                if label in ("STRONG", "IMPROVING"):
                    status = "CONFIRMED"
                    reason = f"Ứng viên nâng hạng: Dòng tiền vào mạnh mẽ ({vol_ratio:.2f}x trung bình), giá tăng tốt."
                    action_note = "Khuyến nghị NÂNG HẠNG lên trading watchlist để theo dõi điểm mua."
                elif label == "WEAK":
                    status = "WATCH"
                    reason = f"Theo dõi: Sức mạnh dòng tiền yếu ({vol_ratio:.2f}x), chưa có động lực."
                    action_note = "Giữ trong danh sách ứng viên nghiên cứu, chưa đưa vào giao dịch."
                else:
                    status = "WATCH"
                    reason = "Theo dõi trung tính: dòng tiền chưa có sự đột phá."
                    action_note = "Tiếp tục quan sát thêm."
                    
        # I1 guard: trạng thái xác nhận dòng tiền phải đồng thuận label + state + volume.
        # Ngoại lệ: state ACCUMULATION (stealth) — volume thấp là bản chất của tín hiệu.
        if status in ("STRONG_CONFIRMED", "CONFIRMED") and state != "ACCUMULATION":
            vol_ok = pd.notna(vol_ratio) and float(vol_ratio) >= 0.7
            if state == "WEAK_FLOW" or not vol_ok:
                status = "WATCH"
                vol_text = f"{vol_ratio:.2f}x" if pd.notna(vol_ratio) else "N/A"
                reason = (
                    f"Mâu thuẫn tín hiệu: nhãn dòng tiền tích cực ({label}) nhưng trạng thái {state}, "
                    f"volume ratio {vol_text} — hạ về theo dõi chờ xác nhận."
                )
                action_note = "Chưa hành động; chờ volume xác nhận (>= 0.7x trung bình 20 phiên)."

        status_list.append(status)
        reason_list.append(reason)
        action_note_list.append(action_note)

    merged["confirmation_status"] = status_list
    merged["cashflow_reason"] = reason_list
    merged["cashflow_action_note"] = action_note_list
    
    keep_cols = [
        "symbol", "sector", "watchlist_tier", "cashflow_score", "cashflow_state",
        "cashflow_label", "confirmation_status", "cashflow_reason", "cashflow_action_note"
    ]
    return merged[keep_cols].sort_values(["watchlist_tier", "cashflow_score"], ascending=[True, False]).reset_index(drop=True)


def write_cashflow_outputs(
    cashflow_board: pd.DataFrame,
    sector_cashflow: pd.DataFrame,
    watchlist_confirmation: pd.DataFrame,
    metadata: dict[str, object],
    base_dir: str | Path = ".",
    output_dir: str | Path = "data/output",
) -> dict[str, object]:
    base = Path(base_dir)
    out_dir = base / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    
    cf_board_parquet = out_dir / "cashflow_board.parquet"
    cf_board_csv = out_dir / "cashflow_board.csv"
    sec_cf_parquet = out_dir / "sector_cashflow.parquet"
    sec_cf_csv = out_dir / "sector_cashflow.csv"
    watch_confirm_parquet = out_dir / "watchlist_cashflow_confirmation.parquet"
    watch_confirm_csv = out_dir / "watchlist_cashflow_confirmation.csv"
    metadata_json = out_dir / "cashflow_board_metadata.json"
    
    save_parquet(cashflow_board, cf_board_parquet)
    cashflow_board.to_csv(cf_board_csv, index=False)
    
    save_parquet(sector_cashflow, sec_cf_parquet)
    sector_cashflow.to_csv(sec_cf_csv, index=False)
    
    save_parquet(watchlist_confirmation, watch_confirm_parquet)
    watchlist_confirmation.to_csv(watch_confirm_csv, index=False)
    
    generated_files = [
        relative_path(cf_board_parquet, base),
        relative_path(cf_board_csv, base),
        relative_path(sec_cf_parquet, base),
        relative_path(sec_cf_csv, base),
        relative_path(watch_confirm_parquet, base),
        relative_path(watch_confirm_csv, base),
        relative_path(metadata_json, base),
    ]
    
    payload = dict(metadata)
    payload["generated_files"] = generated_files
    # Ensure no absolute paths are present in generated_files
    payload["generated_files"] = [str(p) for p in generated_files]
    write_json(payload, metadata_json)
    
    LOGGER.info("Cashflow Board outputs written successfully: %s", ", ".join(payload["generated_files"]))
    return payload


def build_cashflow_board(
    stock_features: pd.DataFrame,
    benchmark_vnindex: pd.DataFrame | None = None,
    client_ready: pd.DataFrame | None = None,
    trading_watchlist: pd.DataFrame | None = None,
    research_candidates: pd.DataFrame | None = None,
    sector_map: pd.DataFrame | None = None,
    sector_map_metadata: dict[str, object] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    sector_map_metadata = sector_map_metadata or {"warnings": [], "source_path": None}
    
    # 1. Attach Sector
    attached, attach_meta = attach_sector(stock_features, sector_map=sector_map)
    
    # 2. Compute Symbol Cashflow Metrics
    symbol_cf, value_proxy_used = compute_symbol_cashflow_metrics(attached, benchmark_df=benchmark_vnindex)
    
    # Latest Date
    latest_date = None
    if not symbol_cf.empty and "date" in symbol_cf.columns:
        latest_date = pd.to_datetime(symbol_cf["date"], errors="coerce").max()
        if pd.notna(latest_date):
            latest_date = latest_date.date().isoformat()
            
    # 3. Compute Sector Cashflow Metrics
    sector_cf = compute_sector_cashflow_metrics(symbol_cf, latest_date=latest_date)
    
    # 4. Build Watchlist Confirmation
    watchlist_confirm = build_cashflow_watchlist_confirmation(
        symbol_cf,
        client_ready=client_ready,
        trading_watchlist=trading_watchlist,
        research_candidates=research_candidates
    )
    
    warnings = list(sector_map_metadata.get("warnings", [])) + list(attach_meta.get("warnings", []))
    status = "OK"
    if symbol_cf.empty:
        status = "ERROR"
        warnings.append("No symbol rows were produced.")
    elif attach_meta.get("mapping_coverage", 0.0) < 0.80:
        status = "WARNING"
        
    n_data_quality_warnings = int(symbol_cf["data_quality_flag"].sum()) if "data_quality_flag" in symbol_cf.columns else 0
    n_low_liquidity_symbols = int((symbol_cf["cashflow_data_status"] == "LOW_LIQUIDITY").sum()) if "cashflow_data_status" in symbol_cf.columns else 0
    n_zero_volume_symbols = int(symbol_cf["zero_volume_flag"].sum()) if "zero_volume_flag" in symbol_cf.columns else 0
    
    confirmation_counts = {}
    if "confirmation_status" in watchlist_confirm.columns:
        counts = watchlist_confirm["confirmation_status"].value_counts().to_dict()
        confirmation_counts = {str(k): int(v) for k, v in counts.items()}
        
    sector_score_warnings = []
    if "sector_score_warning" in sector_cf.columns:
        sector_score_warnings = [
            f"{row['sector']}: {row['sector_score_warning']}"
            for _, row in sector_cf.iterrows()
            if row["sector_score_warning"]
        ]
        
    metadata = {
        "generated_at": utc_now_iso(),
        "status": status,
        "latest_date": latest_date,
        "n_symbols": int(symbol_cf["symbol"].nunique()) if not symbol_cf.empty else 0,
        "n_sectors": int(sector_cf["sector"].nunique()) if not sector_cf.empty else 0,
        "value_proxy_used": value_proxy_used,
        "n_data_quality_warnings": n_data_quality_warnings,
        "n_low_liquidity_symbols": n_low_liquidity_symbols,
        "n_zero_volume_symbols": n_zero_volume_symbols,
        "confirmation_counts": confirmation_counts,
        "sector_score_warnings": sector_score_warnings,
        "warnings": warnings,
        "generated_files": [],
    }
    
    return symbol_cf, sector_cf, watchlist_confirm, metadata
