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
    
    lines = [
        f"BẢN BÁO CÁO PHÂN TÍCH CHẨN ĐOÁN CHI TIẾT CỔ PHIẾU {ticker.upper()}",
        "=============================================================",
        "Phân tích chuyên sâu dựa trên các công cụ định lượng tích hợp:",
        "",
        "1. BỐI CẢNH THỊ TRƯỜNG & XU HƯỚNG (MARKET REGIME & TREND PROFILE)",
        f"  - Thị trường chung (Benchmark): Ở trạng thái '{status['market_regime']}'. Chỉ số VNINDEX đang đóng cửa ở mức {metrics['market_close']:,.1f} điểm, " + 
        ("nằm trên đường MA50 trung hạn" if metrics['market_above_ma50'] else "nằm dưới đường MA50 trung hạn") + " và " +
        ("nằm trên đường MA200 dài hạn." if metrics['market_above_ma200'] else "nằm dưới đường MA200 dài hạn."),
        f"  - Cấu trúc xu hướng cổ phiếu: Trạng thái xu hướng được phân loại là '{status['stock_trend']}'.",
        f"    + Vị thế giá so với MA20: " + ("Trên MA20" if metrics['above_ma20'] else "Dưới MA20") + f" (Khoảng cách: {metrics['distance_ma20']*100:+.2f}%)",
        f"    + Vị thế giá so với MA50: " + ("Trên MA50" if metrics['above_ma50'] else "Dưới MA50") + f" (Khoảng cách: {metrics['distance_ma50']*100:+.2f}%)",
        f"    + Cấu trúc MA Stack (20 > 50 > 200): " + ("Tích cực / Bullish Stacked" if metrics['ma_stack'] else "Chưa đồng thuận xu hướng tăng"),
        f"    + Độ dốc xu hướng (MA50 Slope): {metrics['ma50_slope']*100:+.2f}% (" + ("Xu hướng trung hạn đang hướng lên" if metrics['ma50_slope'] > 0 else "Xu hướng trung hạn đang hướng xuống") + ")",
        f"    + Tín hiệu breakout Donchian 20d: " + ("Đang kích hoạt breakout đỉnh 20 ngày" if metrics['donchian_20_breakout'] else "Không có breakout"),
        "",
        "2. ĐỘNG LƯỢNG & ĐỘC LẬP DÒNG TIỀN (MOMENTUM & FLOW VOLUME ANALYSIS)",
        f"  - Chỉ số động lượng (RSI 14): Đạt {metrics['rsi_14']:.2f}. " + 
        ("Cổ phiếu đang đi vào vùng quá mua (>70)." if metrics['rsi_14'] > 70 else "Cổ phiếu đang ở trạng thái quá bán (<30)." if metrics['rsi_14'] < 30 else "Động lượng ở mức trung bình ổn định."),
        f"  - Chỉ báo MACD Histogram: Đạt {metrics['macd_hist']:.4f} (" + ("Động lượng dương đang tăng trưởng" if metrics['macd_hist'] > 0 else "Động lượng âm đang chiếm ưu thế") + ")",
        f"  - Cường độ xu hướng (ADX): Đạt {metrics['adx']:.2f} (" + ("Xu hướng mạnh mẽ" if metrics['adx'] >= 25 else "Xu hướng đi ngang / yếu") + f"), với chỉ báo +DI đạt {metrics['plus_di']:.2f} và -DI đạt {metrics['minus_di']:.2f}.",
        f"  - Tình trạng Dòng tiền & Khối lượng (Volume / CMF / MFI):",
        f"    + Tỷ lệ khối lượng (Volume Ratio): {metrics['volume_ratio']:.2f}x so với trung bình 20 phiên.",
        f"    + Điểm chênh lệch khối lượng (Volume Z-Score): {metrics['volume_zscore']:.2f} (" + ("Cảnh báo bùng nổ khối lượng / Volume Shock" if metrics['volume_zscore'] > 1.5 else "Khối lượng giao dịch bình thường") + ")",
        f"    + Chỉ số dòng tiền (MFI 14): {metrics['mfi']:.2f} / Chỉ số Chaikin (CMF 20): {metrics['cmf']:.3f} (" + ("Dòng tiền tích lũy ròng đi vào" if metrics['cmf'] > 0 else "Dòng tiền phân phối ròng đi ra") + ")",
        "",
        "3. SỨC MẠNH TƯƠNG ĐỐI & HIỆU SUẤT ĐỊNH LƯỢNG (RELATIVE STRENGTH & ALPHA CAPM)",
        f"  - Sức mạnh so với VNINDEX (Relative Strength): Trạng thái '{status['relative_strength']}'.",
        f"    + Hiệu suất vượt trội (Excess Return) 20 ngày: {metrics['excess_return_20d']*100:+.2f}%",
        f"    + Hiệu suất vượt trội (Excess Return) 60 ngày: {metrics['excess_return_60d']*100:+.2f}%",
        f"    + Độ dốc đường RS (RS Slope): {metrics['rs_slope']*100:+.2f}%",
        f"  - Hệ số CAPM & Tương quan:",
        f"    + Hệ số Beta lăn 60 ngày: {metrics['rolling_beta']:.2f} | Hệ số tương quan (Correlation): {metrics['rolling_corr']:.2f}",
        f"    + Chỉ số Jensen's Alpha (annualized): {metrics.get('jensen_alpha', 0):.2%}",
        f"    + Chỉ số Sharpe: {metrics.get('sharpe', 0):.2f} | Chỉ số Sortino: {metrics.get('sortino', 0):.2f}",
        "",
        "4. ĐÁNH GIÁ BIẾN ĐỘNG & RỦI RO ĐUÔI (VOLATILITY & TAIL RISK)",
        f"  - Mức biến động thực tế (Realized Vol 20d): {metrics['vol_20d']*100:.2f}% (Phân vị biến động: {metrics['volatility_percentile']:.2f}%)",
        f"  - Độ rộng biến động ATR %: {metrics['atr_pct']*100:.2f}% (Biến động trung bình ngày thực tế: {metrics['atr']:,.0f} VND)",
        f"  - Rủi ro sụt giảm tối đa 1 năm qua (Max Drawdown): {metrics['max_drawdown']*100:.2f}%",
        f"  - Rủi ro đuôi (Daily CVaR 95%): {metrics['cvar_95']*100:.2f}% | Độ lệch phân phối lợi suất (Skewness): {metrics['skewness']:.3f}",
        "",
        "5. MÔ PHỎNG MONTE CARLO & CÁC VÙNG THAM CHIẾU ATR (SIMULATION & REFERENCE LEVELS)",
        f"  - Vùng tham chiếu ATR xây dựng từ giá đóng cửa hiện tại:",
        f"    + Vùng mua tham chiếu (Entry Zone): {metrics['entry_zone_low']:,.0f} - {metrics['entry_zone_high']:,.0f} VND",
        f"    + Điểm cắt lỗ tham chiếu (Stop Loss): {metrics['stop_loss']:,.0f} VND",
        f"    + Điểm chốt lời tham chiếu Target 1:  {metrics['target_1']:,.0f} VND",
        f"    + Điểm chốt lời tham chiếu Target 2:  {metrics['target_2']:,.0f} VND",
        f"    + Tỷ lệ Lợi nhuận/Rủi ro (Risk/Reward ratio): {metrics['risk_reward']:.2f}",
        f"  - Kết quả mô phỏng Monte Carlo (3000 đường chạy):",
        f"    + Xác suất đạt Target 1 trước khi chạm Stop Loss: {simulation['prob_hit_target_1_before_stop']:.1%}",
        f"    + Xác suất chạm Stop Loss trước khi đạt Target 1: {simulation['prob_hit_stop_before_target_1']:.1%}",
        f"    + Lợi nhuận mô phỏng trung vị kỳ vọng (horizon 20d): {simulation['expected_return']:.2%}",
        f"    + CVaR mô phỏng rủi ro đuôi 20d: {simulation['cvar_return']:.2%}",
    ]
    return "\n".join(lines)


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
