from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

from data import project_root


def facts_summary(ticker: str, metrics: dict[str, Any], facts: dict[str, Any], simulation: dict[str, float]) -> str:
    """Nhánh C (SDE_SCORING_REPORT.md): bảng dữ kiện, KHÔNG có final_score
    hay decision label. Mọi con số dưới đây là facts thô có ngữ cảnh, không
    phải một khuyến nghị mua/bán -- xem SDE_SCORING_REPORT.md."""
    status = facts["status"]
    lines = [
        f"Ticker: {ticker.upper()}",
        f"Date: {pd.Timestamp(metrics['date']).date()}",
        "",
        "*** BẢNG DỮ KIỆN THAM KHẢO -- KHÔNG PHẢI KHUYẾN NGHỊ MUA/BÁN ***",
        "Không có điểm tổng hợp hay xếp loại quyết định nào ở đây. Vòng 3",
        "(SDE_SCORING_REPORT.md) xác nhận final_score/decision cũ không có",
        "bằng chứng dự báo (IC Newey-West và null-test đều không đạt tiêu",
        "chí đã khóa trước) -- công thức đã gỡ bỏ hoàn toàn, không chỉ ẩn.",
        "",
        f"ATR-based reference levels (không phải điểm vào lệnh khuyến nghị):",
        f"  Entry zone: {metrics['entry_zone_low']:,.0f} - {metrics['entry_zone_high']:,.0f}",
        f"  Stop-loss:  {metrics['stop_loss']:,.0f}",
        f"  Target 1:   {metrics['target_1']:,.0f}",
        f"  Target 2:   {metrics['target_2']:,.0f}",
        f"  Risk/Reward: {metrics['risk_reward']:.2f}",
        "",
        f"Market Regime: {status['market_regime']}",
        f"Trend: {status['stock_trend']}",
        f"Momentum: {status['momentum']}",
        f"Relative Strength: {status['relative_strength']}",
        f"Alpha (CAPM): {metrics.get('jensen_alpha', 0):.2%}",
        f"Risk: {status['risk']}",
        f"Liquidity: {status['liquidity']}",
        f"Simulation: {status['simulation']}",
        "",
        "Chi tiết theo nhóm (reading 0-100 = số tiêu chí TA nội bộ đạt,",
        "KHÔNG phải xác suất/điểm dự báo -- không có nhóm nào ở đây đã qua",
        "kiểm định IC/null-test):",
    ]
    for row in facts["facts"].itertuples(index=False):
        lines.append(f"  - {row.component}: {row.reading:.0f}/100 - {row.reason}")
    lines += ["", "Ghi chú (không phải khuyến nghị):", vietnamese_facts_note(ticker, metrics, facts, simulation)]
    return "\n".join(lines)


def vietnamese_facts_note(ticker: str, metrics: dict[str, Any], facts: dict[str, Any], simulation: dict[str, float]) -> str:
    status = facts["status"]
    parts = [
        f"{ticker.upper()}: đây là bảng dữ kiện tham khảo, KHÔNG phải khuyến nghị mua/bán "
        f"(SDE_SCORING_REPORT.md, Nhánh C -- final_score/decision cũ không có bằng chứng dự báo, đã gỡ bỏ).",
        f"Bối cảnh thị trường chung đang ở trạng thái {status['market_regime'].lower()}, còn xu hướng của cổ phiếu là {status['stock_trend'].lower()}.",
    ]
    if metrics["above_ma50"] and metrics["above_ma200"]:
        parts.append("Giá vẫn giữ trên MA50 và MA200.")
    else:
        parts.append("Giá chưa xác nhận nằm trên các đường MA trung hạn quan trọng.")
    if metrics["excess_return_20d"] > 0 or metrics["excess_return_60d"] > 0:
        parts.append("Relative Strength so với VNINDEX đang cải thiện.")
    else:
        parts.append("Relative Strength chưa nổi bật so với VNINDEX.")
    if metrics["price_extension_warning"]:
        parts.append("Giá đang cách MA20 tương đối xa.")
    parts.append(f"Vùng tham chiếu ATR quanh {metrics['entry_zone_low']:,.0f}-{metrics['entry_zone_high']:,.0f}, stop-loss tham chiếu {metrics['stop_loss']:,.0f}, target 1 tham chiếu {metrics['target_1']:,.0f}.")
    parts.append(f"Monte Carlo (chưa kiểm định calibration) ước tính xác suất chạm target 1 trước stop là {simulation['prob_hit_target_1_before_stop']:.1%}.")
    return " ".join(parts)


def save_outputs(
    output_dir: str | Path,
    ticker: str,
    metrics: dict[str, Any],
    facts: dict[str, Any],
    simulation_summary: dict[str, float],
    backtest: dict[str, Any],
    root: Path | None = None,
) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    lineage = _lineage_metadata(root or project_root())
    prefix = f"{ticker.upper()}_{pd.Timestamp(metrics['date']).date()}"
    summary_path = out / f"{prefix}_facts_summary.txt"
    facts_path = out / f"{prefix}_facts.csv"
    metrics_path = out / f"{prefix}_metrics.csv"
    summary_path.write_text(facts_summary(ticker, metrics, facts, simulation_summary), encoding="utf-8")
    facts["facts"].to_csv(facts_path, index=False)
    pd.DataFrame(
        [
            {
                **metrics,
                **{f"mc_{k}": v for k, v in simulation_summary.items()},
                **{f"bt_{k}": v for k, v in backtest.items()},
                **{f"lineage_{k}": v for k, v in lineage.items()},
            }
        ]
    ).to_csv(metrics_path, index=False)
    return {"summary": summary_path, "facts": facts_path, "metrics": metrics_path}


def _lineage_metadata(root: Path) -> dict[str, Any]:
    """Reproducibility lineage (audit gate #12 / CLAUDE.md rule 6): which
    dataset version and code commit produced this artifact, so a stale or
    since-regenerated input is detectable after the fact. Reuses the main
    project's own builder (src/utils/pipeline_io.py) instead of a
    stock-decision-engine-local re-implementation."""
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    from src.data.dataset_config import OFFICIAL_CLEAN_OHLCV_PATH
    from src.utils.pipeline_io import build_lineage_metadata

    return build_lineage_metadata(
        features_path=OFFICIAL_CLEAN_OHLCV_PATH,
        config_path="stock-decision-engine/config.yaml",
        dataset_version="full_history_v2",
        base_dir=root_str,
    )
