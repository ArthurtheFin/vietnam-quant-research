from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def decision_summary(ticker: str, metrics: dict[str, Any], decision: dict[str, Any], simulation: dict[str, float]) -> str:
    status = decision["status"]
    lines = [
        f"Ticker: {ticker.upper()}",
        f"Date: {pd.Timestamp(metrics['date']).date()}",
        "",
        f"Final Score: {decision['final_score']:.0f}/100",
        f"Decision: {decision['decision']}",
        f"Confidence: {decision['confidence']}",
        "",
        f"Entry Zone: {metrics['entry_zone_low']:,.0f} - {metrics['entry_zone_high']:,.0f}",
        f"Stop-loss: {metrics['stop_loss']:,.0f}",
        f"Target 1: {metrics['target_1']:,.0f}",
        f"Target 2: {metrics['target_2']:,.0f}",
        f"Risk/Reward: {metrics['risk_reward']:.2f}",
        "",
        f"Market Regime: {status['market_regime']}",
        f"Trend: {status['stock_trend']}",
        f"Momentum: {status['momentum']}",
        f"Relative Strength: {status['relative_strength']}",
        f"Alpha: {metrics.get('jensen_alpha', 0):.2%}",
        f"Risk: {status['risk']}",
        f"Liquidity: {status['liquidity']}",
        f"Simulation: {status['simulation']}",
        "",
        "Main Reasons:",
    ]
    top = decision["sub_scores"].sort_values("score", ascending=False).head(3)
    lines += [f"{i}. {row.component}: {row.score:.0f}/100 - {row.reason}" for i, row in enumerate(top.itertuples(index=False), 1)]
    lines += ["", "Warnings:"]
    lines += [f"{i}. {w}" for i, w in enumerate(decision["warnings"], 1)]
    lines += ["", "Vietnamese Broker Note:", vietnamese_explanation(ticker, metrics, decision, simulation)]
    return "\n".join(lines)


def vietnamese_explanation(ticker: str, metrics: dict[str, Any], decision: dict[str, Any], simulation: dict[str, float]) -> str:
    status = decision["status"]
    parts = [
        f"{ticker.upper()} hiện được hệ thống chấm {decision['final_score']:.0f}/100 với khuyến nghị {decision['decision']}.",
        f"Bối cảnh thị trường chung đang ở trạng thái {status['market_regime'].lower()}, còn xu hướng của cổ phiếu là {status['stock_trend'].lower()}.",
    ]
    if metrics["above_ma50"] and metrics["above_ma200"]:
        parts.append("Giá vẫn giữ trên MA50 và MA200, cho thấy cấu trúc trung hạn chưa bị phá vỡ.")
    else:
        parts.append("Giá chưa xác nhận nằm trên các đường MA trung hạn quan trọng, nên cần thận trọng với điểm mua mới.")
    if metrics["excess_return_20d"] > 0 or metrics["excess_return_60d"] > 0:
        parts.append("Relative Strength so với VNINDEX đang cải thiện, tức mã có dấu hiệu khỏe hơn thị trường chung.")
    else:
        parts.append("Relative Strength chưa nổi bật so với VNINDEX, vì vậy chưa nên nâng tỷ trọng quá sớm.")
    if metrics["price_extension_warning"]:
        parts.append("Tuy nhiên giá đang cách MA20 tương đối xa, phù hợp hơn với chiến lược chờ pullback hoặc chia lệnh thay vì mua đuổi.")
    if metrics["risk_reward"] >= 1.8:
        parts.append(f"Vùng mua tham chiếu quanh {metrics['entry_zone_low']:,.0f}-{metrics['entry_zone_high']:,.0f}, dừng lỗ ATR tại {metrics['stop_loss']:,.0f}, mục tiêu đầu tiên {metrics['target_1']:,.0f}.")
    else:
        parts.append("Tỷ lệ risk/reward hiện chưa đủ hấp dẫn; nên chờ giá về vùng hỗ trợ gần hơn hoặc stop-loss hẹp hơn.")
    parts.append(f"Monte Carlo ước tính xác suất chạm target 1 trước stop là {simulation['prob_hit_target_1_before_stop']:.1%}.")
    return " ".join(parts)


def save_outputs(
    output_dir: str | Path,
    ticker: str,
    metrics: dict[str, Any],
    decision: dict[str, Any],
    simulation_summary: dict[str, float],
    backtest: dict[str, Any],
) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    prefix = f"{ticker.upper()}_{pd.Timestamp(metrics['date']).date()}"
    summary_path = out / f"{prefix}_decision_summary.txt"
    score_path = out / f"{prefix}_sub_scores.csv"
    metrics_path = out / f"{prefix}_metrics.csv"
    summary_path.write_text(decision_summary(ticker, metrics, decision, simulation_summary), encoding="utf-8")
    decision["sub_scores"].to_csv(score_path, index=False)
    pd.DataFrame([{**metrics, **{f"mc_{k}": v for k, v in simulation_summary.items()}, **{f"bt_{k}": v for k, v in backtest.items()}}]).to_csv(metrics_path, index=False)
    return {"summary": summary_path, "scores": score_path, "metrics": metrics_path}
