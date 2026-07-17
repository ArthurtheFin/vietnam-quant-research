"""Nhánh C (SDE_SCORING_PREREG.md, Vòng 3, SDE_SCORING_REPORT.md): không
thành phần nào (composite hay từng sub-score riêng) đạt tiêu chí đã khóa
trước (IC Newey-West |t_NW|>3 đồng dấu 3 giai đoạn residualized/full, HOẶC
null-test percentile>60 không fold nào <10). `final_score` tổng hợp và
`decision` (BUY CANDIDATE/WATCH/WEAK SETUP/AVOID/...) đã GỠ BỎ hoàn toàn --
không phải bị comment/deprecate, không còn trong output ở bất kỳ dạng nào.

Vẫn giữ 8 nhóm "chỉ số thô có ngữ cảnh" (`_market_score`.../`_liquidity_score`
gọi là "reading" thay vì "score" ở đây) vì đây là facts đã tính sẵn từ
`metrics`/`simulation`, không phải một quyết định tổng hợp -- đúng tinh thần
`final_watchlist.py`'s Nhánh C ("không xếp hạng alpha, chỉ hiển thị"), áp
dụng cho bối cảnh một-mã-một-lúc của SDE (không cần một sort key thay thế
như final_watchlist cần cho danh sách nhiều mã).

Không xóa các hàm `_market_score`.../`_liquidity_score` -- công thức bên
trong (đếm bao nhiêu tiêu chí TA đạt, thang 0-100) không đổi, chỉ không còn
bị cộng có trọng số thành một con số quyết định. Đọc `SDE_SCORING_REPORT.md`
trước khi coi bất kỳ con số nào ở đây là một khuyến nghị mua/bán.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def build_facts_table(metrics: dict[str, Any], simulation: dict[str, float], backtest: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    readings = {
        "market_regime": _market_score(metrics),
        "trend": _trend_score(metrics),
        "momentum": _momentum_score(metrics),
        "relative_strength": _rs_score(metrics),
        "alpha": _alpha_score(metrics, backtest),
        "risk": _risk_score(metrics),
        "liquidity": _liquidity_score(metrics, cfg),
        "simulation": _simulation_score(simulation),
    }
    facts = pd.DataFrame(
        [{"component": k, "reading": round(v["score"], 1), "reason": v["reason"]} for k, v in readings.items()]
    )
    return {
        "facts": facts,
        "status": _statuses(metrics, readings, simulation),
    }


def _market_score(m: dict[str, Any]) -> dict[str, Any]:
    pts = 0
    pts += 20 if m["market_above_ma20"] else 0
    pts += 20 if m["market_above_ma50"] else 0
    pts += 20 if m["market_above_ma200"] else 0
    pts += 15 if m["market_ma50_slope"] > 0 else 0
    pts += 10 if m["market_return_20d"] > 0 else 0
    pts += 10 if m["market_return_60d"] > 0 else 0
    pts += 5 if m["market_drawdown"] > -0.08 else 0
    if m["market_volatility_percentile"] > 85:
        pts -= 15
    return _pack(pts, "Benchmark trend, slope, returns, drawdown, and volatility.")


def _trend_score(m: dict[str, Any]) -> dict[str, Any]:
    pts = 10 * sum(bool(m[k]) for k in ["above_ma20", "above_ma50", "above_ma100", "above_ma200"])
    pts += 20 if m["ma_stack"] else 0
    pts += 10 if m["ma20_slope"] > 0 else 0
    pts += 10 if m["ma50_slope"] > 0 else 0
    pts += 10 if m["adx"] >= 20 and m["plus_di"] > m["minus_di"] else 0
    pts += 5 if m["donchian_20_breakout"] else 0
    pts += 5 if m["week_52_high_distance"] > -0.12 else 0
    return _pack(pts, "MA structure, slopes, ADX/+DI, and breakout context.")


def _momentum_score(m: dict[str, Any]) -> dict[str, Any]:
    pts = 12 * sum(m[k] > 0 for k in ["return_5d", "return_20d", "return_60d", "return_120d"])
    rsi = m["rsi_14"]
    pts += 20 if 45 <= rsi <= 70 else 10 if 35 <= rsi < 45 or 70 < rsi <= 78 else 0
    pts += 15 if m["macd_hist"] > 0 and m["macd"] > m["macd_signal"] else 0
    pts += 17 if m["momentum_acceleration"] > 0 else 0
    return _pack(pts, "Multi-horizon returns, RSI, MACD, and acceleration.")


def _rs_score(m: dict[str, Any]) -> dict[str, Any]:
    pts = 25 if m["excess_return_20d"] > 0 else 0
    pts += 25 if m["excess_return_60d"] > 0 else 0
    pts += 25 if m["rs_slope"] > 0 else 0
    pts += 15 if m["rolling_beta"] <= 1.4 else 5
    pts += 10 if m["rolling_corr"] < 0.85 else 5
    return _pack(pts, "Excess return, RS slope, beta, and correlation.")


def _alpha_score(m: dict[str, Any], backtest: dict[str, Any]) -> dict[str, Any]:
    pts = 20 if m.get("jensen_alpha", 0) > 0 else 0
    pts += 15 if m.get("sharpe", 0) > 0.7 else 8 if m.get("sharpe", 0) > 0 else 0
    pts += 15 if m.get("sortino", 0) > 1.0 else 8 if m.get("sortino", 0) > 0 else 0
    pts += 15 if m.get("information_ratio", 0) > 0 else 0
    pts += 15 if m.get("calmar", 0) > 0.5 else 0
    pts += 20 if (backtest.get("profit_factor") or 0) >= 1.2 else 10 if backtest.get("available") else 0
    return _pack(pts, "CAPM alpha, Sharpe/Sortino/IR/Calmar, and optional backtest edge.")


def _risk_score(m: dict[str, Any]) -> dict[str, Any]:
    pts = 25 if m["atr_pct"] <= 0.035 else 15 if m["atr_pct"] <= 0.06 else 5
    pts += 20 if m["volatility_percentile"] <= 60 else 10 if m["volatility_percentile"] <= 85 else 0
    pts += 20 if m["max_drawdown"] > -0.25 else 10 if m["max_drawdown"] > -0.4 else 0
    pts += 15 if m["cvar_95"] > -0.04 else 5
    pts += 10 if abs(m["skewness"]) < 1.5 else 5
    pts += 10 if m["stop_distance_pct"] <= 0.12 else 0
    return _pack(pts, "ATR, volatility percentile, drawdown, CVaR, skew, and stop width.")


def _liquidity_score(m: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    min_value = float(cfg.get("min_avg_value_20d", 10_000_000_000))
    pts = 40 if m["avg_value_20d"] >= min_value else 20 if m["avg_value_20d"] >= min_value * 0.5 else 0
    pts += 20 if m["avg_volume_20d"] > 0 and m["avg_volume_60d"] > 0 else 0
    pts += 15 if 0.8 <= m["volume_ratio"] <= 3.0 else 8 if m["volume_ratio"] > 0 else 0
    pts += 15 if -2 <= m["volume_zscore"] <= 3 else 5
    pts += 10 if m["cmf"] > 0 or m["mfi"] >= 50 else 0
    return _pack(pts, "Average value, volume participation, z-score, MFI, and CMF.")


def _simulation_score(sim: dict[str, float]) -> dict[str, Any]:
    pts = 35 if sim["prob_hit_target_1_before_stop"] >= 0.45 else 20 if sim["prob_hit_target_1_before_stop"] >= 0.3 else 5
    pts += 25 if sim["prob_hit_target_1_before_stop"] > sim["prob_hit_stop_before_target_1"] else 0
    pts += 20 if sim["expected_return"] > 0 else 0
    pts += 20 if sim["cvar_return"] > -0.08 else 8
    return _pack(pts, "Bootstrap probability, expected return, and simulated tail risk.")


def _statuses(m: dict[str, Any], readings: dict[str, Any], sim: dict[str, float]) -> dict[str, str]:
    return {
        "market_regime": "Bullish" if readings["market_regime"]["score"] >= 70 else "Neutral" if readings["market_regime"]["score"] >= 45 else "Weak",
        "stock_trend": "Uptrend" if readings["trend"]["score"] >= 70 else "Mixed" if readings["trend"]["score"] >= 45 else "Downtrend",
        "momentum": "Positive" if readings["momentum"]["score"] >= 60 else "Cooling" if readings["momentum"]["score"] >= 40 else "Weak",
        "relative_strength": "Outperforming" if readings["relative_strength"]["score"] >= 60 else "Neutral/lagging",
        "risk": "Controlled" if readings["risk"]["score"] >= 60 else "Elevated",
        "liquidity": "Passed" if readings["liquidity"]["score"] >= 60 else "Thin",
        "simulation": f"{sim['prob_hit_target_1_before_stop']:.1%} target-before-stop probability",
    }


def _pack(score: float, reason: str) -> dict[str, Any]:
    return {"score": float(np.clip(score, 0, 100)), "reason": reason}
