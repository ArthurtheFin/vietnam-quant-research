from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

WEIGHTS = {
    "market_regime": 10,
    "trend": 20,
    "momentum": 15,
    "relative_strength": 15,
    "alpha": 15,
    "risk": 10,
    "liquidity": 10,
    "simulation": 5,
}


def score_decision(metrics: dict[str, Any], simulation: dict[str, float], backtest: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    scores = {
        "market_regime": _market_score(metrics),
        "trend": _trend_score(metrics),
        "momentum": _momentum_score(metrics),
        "relative_strength": _rs_score(metrics),
        "alpha": _alpha_score(metrics, backtest),
        "risk": _risk_score(metrics),
        "liquidity": _liquidity_score(metrics, cfg),
        "simulation": _simulation_score(simulation),
    }
    weighted = sum(scores[k]["score"] * WEIGHTS[k] / 100 for k in WEIGHTS)
    sub_scores = pd.DataFrame(
        [{"component": k, "score": round(v["score"], 1), "weight": WEIGHTS[k], "reason": v["reason"]} for k, v in scores.items()]
    )
    hard = _hard_filters(metrics, simulation, backtest, cfg)
    warnings = _warnings(metrics, simulation, backtest)
    decision = _decision_label(weighted, scores["market_regime"]["score"], metrics, hard, cfg)
    confidence = _confidence(weighted, hard, simulation)
    return {
        "final_score": round(float(np.clip(weighted, 0, 100)), 1),
        "sub_scores": sub_scores,
        "decision": decision,
        "confidence": confidence,
        "warnings": warnings,
        "hard_filters": hard,
        "status": _statuses(metrics, scores, simulation),
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


def _hard_filters(m: dict[str, Any], sim: dict[str, float], backtest: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    min_value = float(cfg.get("min_avg_value_20d", 10_000_000_000))
    checks = [
        ("average trading value 20D below threshold", m["avg_value_20d"] < min_value),
        ("price below MA200", not m["above_ma200"]),
        ("market score below 40", _market_score(m)["score"] < 40),
        ("risk/reward below 1.5", m["risk_reward"] < 1.5),
        ("ATR stop-loss distance too wide", m["stop_distance_pct"] > 0.12),
        ("volatility percentile above 90", m["volatility_percentile"] > 90),
        ("backtest profit factor below 1", backtest.get("available") and (backtest.get("profit_factor") or 1) < 1),
        ("probability stop hit > probability target hit", sim["prob_hit_stop_before_target_1"] > sim["prob_hit_target_1_before_stop"]),
    ]
    return [{"filter": name, "passed": not bool(failed)} for name, failed in checks]


def _decision_label(score: float, market_score: float, m: dict[str, Any], hard: list[dict[str, Any]], cfg: dict[str, Any]) -> str:
    liq_pass = next(x["passed"] for x in hard if x["filter"].startswith("average trading value"))
    critical_failed = [x for x in hard if not x["passed"] and x["filter"] in {"price below MA200", "market score below 40"}]
    if score >= 65 and m["above_ma200"] and m["price_extension_warning"]:
        return "GOOD STOCK, BAD ENTRY"
    if score >= cfg["score_thresholds"]["buy"] and market_score >= 60 and m["risk_reward"] >= 1.8 and liq_pass and not critical_failed:
        return "BUY CANDIDATE"
    if score >= cfg["score_thresholds"]["watch"]:
        return "WATCH / WAIT FOR PULLBACK"
    if score >= cfg["score_thresholds"]["weak"]:
        return "WEAK SETUP"
    return "AVOID"


def _warnings(m: dict[str, Any], sim: dict[str, float], backtest: dict[str, Any]) -> list[str]:
    items = []
    if m["price_extension_warning"]:
        items.append("Price is extended versus MA20; avoid chasing a full position.")
    if m["volatility_percentile"] > 85:
        items.append("Volatility is elevated versus its own history.")
    if m["risk_reward"] < 1.8:
        items.append("Risk/reward is below the preferred buy threshold.")
    if sim["prob_hit_stop_before_target_1"] > sim["prob_hit_target_1_before_stop"]:
        items.append("Monte Carlo paths hit stop before target more often than the reverse.")
    if backtest.get("available") and (backtest.get("profit_factor") or 0) < 1:
        items.append("Available backtest evidence has profit factor below 1.")
    return items or ["No major quantitative warning."]


def _statuses(m: dict[str, Any], scores: dict[str, Any], sim: dict[str, float]) -> dict[str, str]:
    return {
        "market_regime": "Bullish" if scores["market_regime"]["score"] >= 70 else "Neutral" if scores["market_regime"]["score"] >= 45 else "Weak",
        "stock_trend": "Uptrend" if scores["trend"]["score"] >= 70 else "Mixed" if scores["trend"]["score"] >= 45 else "Downtrend",
        "momentum": "Positive" if scores["momentum"]["score"] >= 60 else "Cooling" if scores["momentum"]["score"] >= 40 else "Weak",
        "relative_strength": "Outperforming" if scores["relative_strength"]["score"] >= 60 else "Neutral/lagging",
        "risk": "Controlled" if scores["risk"]["score"] >= 60 else "Elevated",
        "liquidity": "Passed" if scores["liquidity"]["score"] >= 60 else "Thin",
        "simulation": f"{sim['prob_hit_target_1_before_stop']:.1%} target-before-stop probability",
    }


def _pack(score: float, reason: str) -> dict[str, Any]:
    return {"score": float(np.clip(score, 0, 100)), "reason": reason}


def _confidence(score: float, hard: list[dict[str, Any]], sim: dict[str, float]) -> str:
    failed = sum(not x["passed"] for x in hard)
    edge = sim["prob_hit_target_1_before_stop"] - sim["prob_hit_stop_before_target_1"]
    if score >= 75 and failed <= 1 and edge > 0:
        return "Medium-High"
    if score >= 60 and failed <= 3:
        return "Medium"
    return "Low-Medium"
