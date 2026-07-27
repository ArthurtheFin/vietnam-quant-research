from __future__ import annotations

import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd

from src.data.dataset_config import OFFICIAL_FEATURES_PATH
from src.data.loaders import read_parquet, save_parquet
from src.utils.logger import get_logger
from src.utils.pipeline_io import build_lineage_metadata, relative_path, utc_now_iso, validate_lineage_metadata, write_json

LOGGER = get_logger("research_notes")


def _read_parquet_safe(p: Path) -> pd.DataFrame:
    if not p.exists():
        LOGGER.warning(f"Parquet file not found: {p}")
        return pd.DataFrame()
    try:
        return read_parquet(p)
    except Exception as e:
        LOGGER.error(f"Error loading Parquet {p}: {e}")
        return pd.DataFrame()


def _read_json_safe(p: Path) -> dict:
    if not p.exists():
        LOGGER.warning(f"JSON file not found: {p}")
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        LOGGER.error(f"Error loading JSON {p}: {e}")
        return {}


def load_research_inputs(base_dir: str | Path = ".") -> dict[str, pd.DataFrame | dict]:
    base = Path(base_dir)
    return {
        "client_ready_watchlist": _read_parquet_safe(base / "data/output/client_ready_watchlist.parquet"),
        "trading_watchlist": _read_parquet_safe(base / "data/output/trading_watchlist.parquet"),
        "sector_board": _read_parquet_safe(base / "data/output/sector_board.parquet"),
        "sector_leaders": _read_parquet_safe(base / "data/output/sector_leaders.parquet"),
        "sector_cashflow": _read_parquet_safe(base / "data/output/sector_cashflow.parquet"),
        "cashflow_board": _read_parquet_safe(base / "data/output/cashflow_board.parquet"),
        "watchlist_cashflow_confirmation": _read_parquet_safe(base / "data/output/watchlist_cashflow_confirmation.parquet"),
        "portfolio_weights": _read_parquet_safe(base / "data/output/portfolio_weights.parquet"),
        "capital_plan": _read_parquet_safe(base / "data/output/capital_plan.parquet"),
        "pipeline_metadata": _read_json_safe(base / "data/output/pipeline_metadata.json"),
        "cashflow_board_metadata": _read_json_safe(base / "data/output/cashflow_board_metadata.json"),
        "sector_board_metadata": _read_json_safe(base / "data/output/sector_board_metadata.json"),
    }


def build_symbol_research_context(symbol: str, inputs: dict) -> dict[str, object]:
    context = {
        "symbol": symbol,
        "watchlist_tier": "UNKNOWN",
        "sector": "UNKNOWN",
        "confidence_label": "UNKNOWN",
        "latest_date": "UNKNOWN",
        "cashflow_score": 50.0,
        "cashflow_state": "NEUTRAL",
        "cashflow_label": "NEUTRAL",
        "cashflow_data_status": "OK",
        "confirmation_status": "WATCH",
        "cashflow_reason": "Chưa đủ dữ liệu phân tích dòng tiền.",
        "cashflow_action_note": "Tiếp tục quan sát thêm.",
        "volume_ratio_20d": 1.0,
        "return_5d": 0.0,
        "return_10d": 0.0,
        "volatility_percentile": 0.5,
        "relative_return_20d_vs_vnindex": 0.0,
        "close": 0.0,
        "cashflow_value": 0.0,
        "portfolio_weight": None,
        "capital_allocation": None,
        "sector_label": "NEUTRAL",
        "sector_rank": 999,
        "sector_cashflow_score": 50.0,
        "n_symbols_with_valid_cashflow": 0,
        "sector_score_quality": "MEDIUM",
        "sector_score_warning": "",
        "top_sector_symbols": "",
        "data_warnings": "",
    }
    
    # 1. Watchlist Tier
    cr = inputs["client_ready_watchlist"]
    tw = inputs["trading_watchlist"]
    if not cr.empty and symbol in cr["symbol"].values:
        context["watchlist_tier"] = "client_ready"
        row = cr[cr["symbol"] == symbol].iloc[0]
        context["sector"] = row.get("sector", context["sector"])
        context["confidence_label"] = row.get("confidence_label", context["confidence_label"])
    elif not tw.empty and symbol in tw["symbol"].values:
        context["watchlist_tier"] = "trading_watchlist"
        row = tw[tw["symbol"] == symbol].iloc[0]
        context["sector"] = row.get("sector", context["sector"])
        context["confidence_label"] = row.get("confidence_label", context["confidence_label"])
        
    cf = inputs["cashflow_board"]
    if not cf.empty and symbol in cf["symbol"].values:
        row = cf[cf["symbol"] == symbol].iloc[0]
        context["latest_date"] = str(row.get("date", context["latest_date"]))
        context["sector"] = row.get("sector", context["sector"])
        context["cashflow_score"] = float(row.get("cashflow_score", 50.0))
        context["cashflow_state"] = str(row.get("cashflow_state", "NEUTRAL"))
        context["cashflow_label"] = str(row.get("cashflow_label", "NEUTRAL"))
        context["cashflow_data_status"] = str(row.get("cashflow_data_status", "OK"))
        context["volume_ratio_20d"] = float(row.get("volume_ratio_20d", 1.0))
        context["return_5d"] = float(row.get("return_5d", 0.0))
        context["return_10d"] = float(row.get("return_10d", 0.0))
        context["volatility_percentile"] = float(row.get("volatility_percentile", 0.5))
        context["relative_return_20d_vs_vnindex"] = float(row.get("relative_return_20d_vs_vnindex", 0.0))
        context["close"] = float(row.get("close", 0.0))
        context["cashflow_value"] = float(row.get("cashflow_value", 0.0))
        if row.get("data_quality_flag") or context["cashflow_data_status"] in ("MISSING_DATA", "ZERO_VOLUME"):
            context["data_warnings"] = "Cảnh báo chất lượng dữ liệu: khối lượng giao dịch bằng 0 hoặc thiếu dữ liệu sàn."
            
    # 3. Watchlist Cashflow Confirmation
    wcc = inputs["watchlist_cashflow_confirmation"]
    if not wcc.empty and symbol in wcc["symbol"].values:
        row = wcc[wcc["symbol"] == symbol].iloc[0]
        context["confirmation_status"] = str(row.get("confirmation_status", context["confirmation_status"]))
        context["cashflow_reason"] = str(row.get("cashflow_reason", context["cashflow_reason"]))
        context["cashflow_action_note"] = str(row.get("cashflow_action_note", context["cashflow_action_note"]))
        
    # 4. Portfolio Weights and Capital Plan
    pw = inputs["portfolio_weights"]
    if not pw.empty and symbol in pw["symbol"].values:
        row = pw[pw["symbol"] == symbol].iloc[0]
        context["portfolio_weight"] = float(row.get("risk_parity", row.get("equal_weight", 0.0)))
        
    cp = inputs["capital_plan"]
    if not cp.empty and symbol in cp["symbol"].values:
        row = cp[cp["symbol"] == symbol].iloc[0]
        context["capital_allocation"] = float(row.get("position_value", 0.0))
        if context["portfolio_weight"] is None:
            context["portfolio_weight"] = float(row.get("target_weight", 0.0))
            
    # 5. Sector board details
    sc = inputs["sector_cashflow"]
    sect_name = context["sector"]
    if not sc.empty and sect_name in sc["sector"].values:
        row = sc[sc["sector"] == sect_name].iloc[0]
        context["sector_label"] = str(row.get("sector_cashflow_label", "NEUTRAL"))
        context["sector_rank"] = int(row.get("sector_cashflow_rank", 999))
        context["sector_cashflow_score"] = float(row.get("sector_cashflow_score", 50.0))
        context["n_symbols_with_valid_cashflow"] = int(row.get("n_symbols_with_valid_cashflow", 0))
        context["sector_score_quality"] = str(row.get("sector_score_quality", "MEDIUM"))
        context["sector_score_warning"] = str(row.get("sector_score_warning", ""))
        context["top_sector_symbols"] = str(row.get("top_cashflow_symbols", ""))
        
    return context


def generate_symbol_note_markdown(symbol: str, context: dict, template_str: str) -> str:
    # Build text pieces dynamically
    
    # 1. Investment Thesis
    state = context["cashflow_state"]
    label = context["cashflow_label"]
    sector = context["sector"]
    cf_status = context["cashflow_data_status"]
    confirm = context["confirmation_status"]
    
    if cf_status in ("MISSING_DATA", "ZERO_VOLUME"):
        thesis = (
            f"Luận điểm đầu tư đối với cổ phiếu {symbol} hiện đang ở trạng thái kiểm tra bắt buộc (CHECK_REQUIRED) "
            f"do phát hiện bất thường về dữ liệu thanh khoản sàn (volume bằng 0 hoặc thiếu số liệu). Hệ thống khuyến nghị "
            f"tạm ngưng giao dịch hoặc giải ngân đối với mã này cho đến khi nguồn dữ liệu được xác minh chính xác."
        )
    elif confirm == "STRONG_CONFIRMED":
        thesis = (
            f"Cổ phiếu {symbol} ngành {sector} đang thể hiện luận điểm đầu tư đột phá rất mạnh. Đà bứt phá giá được "
            f"hậu thuẫn tối đa bởi sự gia tăng mạnh mẽ từ dòng tiền lớn (volume ratio đạt {context['volume_ratio_20d']:.2f}x trung bình). "
            f"Thesis kỳ vọng đà tăng giá có thể tiếp diễn nếu dòng tiền tiếp tục được duy trì ổn định."
        )
    elif confirm == "CONFIRMED":
        thesis = (
            f"Luận điểm đầu tư của {symbol} tập trung vào xu hướng cải thiện tích cực của dòng tiền ngắn hạn trong ngành {sector}. "
            f"Quantitative indicators ghi nhận sự đồng thuận giữa dòng tiền đi lên và trạng thái phục hồi kỹ thuật, mở ra triển vọng "
            f"nắm giữ trung hạn khả quan."
        )
    elif state == "DRY_UP_WATCH":
        thesis = (
            f"Thesis đầu tư đối với {symbol} tập trung vào tín hiệu kiệt cung tích lũy chặt chẽ (dry-up). Giá đang giữ nền "
            f"rất tốt trên biên độ hẹp với volatility thấp, áp lực bán cạn kiệt cho thấy khả năng bứt phá có thể xảy ra khi lực cầu "
            f"gia nhập trở lại."
        )
    elif state == "DISTRIBUTION_RISK" or label == "RISKY":
        thesis = (
            f"Hệ thống ghi nhận áp lực bán và rủi ro phân phối ngắn hạn (distribution risk) đối với {symbol}. Đà giảm giá "
            f"kèm volume lớn là tín hiệu cảnh báo lực cung đang lấn át hoàn toàn, ưu tiên quản trị rủi ro và thu hẹp vị thế."
        )
    else:
        thesis = (
            f"Cổ phiếu {symbol} đang ở trạng thái tích lũy trung tính trong ngành {sector}. Cung cầu tương đối cân bằng, "
            f"cần tiếp tục theo dõi phản ứng giá quanh các vùng hỗ trợ trước khi hình thành luận điểm đầu tư rõ nét hơn."
        )
        
    # 2. Quant Evidence
    quant_weight_str = f"- Tỷ trọng danh mục gợi ý: {context['portfolio_weight']:.2%}\n" if context["portfolio_weight"] is not None else ""
    quant_cap_str = f"- Giá trị phân bổ vốn dự kiến: {context['capital_allocation']:,.0f} VND\n" if context["capital_allocation"] is not None else ""
    
    quant_evidence = (
        f"- Phân loại Watchlist: `{context['watchlist_tier']}`\n"
        f"- Nhãn phân loại kỹ thuật: `{context['confidence_label']}`\n"
        f"- Cấp độ dòng tiền (Cashflow Label): `{context['cashflow_label']}`\n"
        f"- Điểm số composite dòng tiền: {context['cashflow_score']:.1f}/100\n"
        f"- Trạng thái dòng tiền: `{context['cashflow_state']}`\n"
        f"- Trạng thái xác nhận dòng tiền: `{context['confirmation_status']}`\n"
        f"{quant_weight_str}"
        f"{quant_cap_str}"
        f"- Biến động phân vị (volatility percentile): {context['volatility_percentile']:.1%}\n"
    )
    
    # 3. Sector Context
    sector_warning_str = f" ({context['sector_score_warning']})" if context["sector_score_warning"] else ""
    sector_context = (
        f"Cổ phiếu thuộc ngành `{context['sector']}`.\n"
        f"- Xếp hạng dòng tiền ngành: #{context['sector_rank']} toàn thị trường.\n"
        f"- Điểm số dòng tiền ngành: {context['sector_cashflow_score']:.1f}/100.\n"
        f"- Nhãn ngành: `{context['sector_label']}` (Chất lượng điểm số: `{context['sector_score_quality']}`{sector_warning_str}).\n"
        f"- Số lượng mã giao dịch hoạt động trong ngành: {context['n_symbols_with_valid_cashflow']} mã.\n"
        f"- Các mã dẫn đầu dòng tiền cùng ngành: {context['top_sector_symbols'] or 'Không rõ'}.\n"
    )
    
    # 4. Cashflow Confirmation
    cashflow_confirmation = (
        f"- Điểm số Money Flow: {context['cashflow_score']:.1f}\n"
        f"- Trạng thái dòng tiền: `{context['cashflow_state']}`\n"
        f"- Xác nhận từ hệ thống: `{context['confirmation_status']}`\n"
        f"- Thuyết minh định lượng: {context['cashflow_reason']}\n"
    )
    
    # 5. Technical Setup
    if state == "CONFIRMED_INFLOW":
        tech = (
            f"Thiết lập kỹ thuật đang ở trạng thái bứt phá xu hướng (breakout). Đường giá vượt lên các vùng kháng cự ngắn hạn "
            f"đi kèm khối lượng giao dịch đột biến đạt {context['volume_ratio_20d']:.2f}x trung bình 20 phiên, xác nhận xu hướng tăng."
        )
    elif state == "ACCUMULATION":
        tech = (
            f"Đường giá đang vận động tích lũy chặt chẽ (accumulation) trong một kênh ngang hẹp. Volatility ở mức thấp "
            f"giúp hạn chế rủi ro sụt giảm mạnh, tạo điểm tựa nền giá vững chắc."
        )
    elif state == "DRY_UP_WATCH":
        tech = (
            f"Cổ phiếu thiết lập vùng kiệt cung chặt chẽ (dry-up setup). Giá dao động trong biên độ rất hẹp ({context['return_10d']:.1%}), "
            f"khối lượng giao dịch cạn kiệt ở mức {context['volume_ratio_20d']:.2f}x trung bình, cho thấy lực bán đã dừng hoàn toàn."
        )
    elif state == "DISTRIBUTION_RISK":
        tech = (
            f"Biểu đồ xuất hiện tín hiệu rủi ro phân phối (distribution). Giá suy giảm mạnh ({context['return_5d']:.1%}) "
            f"đòn bẩy khối lượng bán tăng cao, cảnh báo áp lực chốt lời diện rộng."
        )
    else:
        tech = (
            f"Đồ thị vận động tích lũy trung tính, chưa bứt phá khỏi kênh giá hẹp hiện tại và dao động quanh các đường trung bình động."
        )
    technical_setup = tech
    
    # 6. Risk Factors
    sector_risk = ""
    if context["n_symbols_with_valid_cashflow"] < 5:
        sector_risk = f"- Rủi ro quy mô ngành nhỏ: Ngành {sector} có số lượng cổ phiếu hoạt động ít, dễ bị nhiễu do yếu tố cá biệt.\n"
        
    liq_risk = ""
    if cf_status == "LOW_LIQUIDITY":
        liq_risk = "- Rủi ro thanh khoản thấp: Giá trị giao dịch trung bình ngày hạn chế, có thể khó khăn khi giải ngân lớn hoặc thoát vị thế.\n"
        
    data_risk = ""
    if context["data_warnings"]:
        data_risk = f"- {context['data_warnings']}\n"
        
    risk_factors = (
        f"- Rủi ro thị trường: Rủi ro chung từ biến động không thuận lợi của chỉ số VNINDEX.\n"
        f"{sector_risk}"
        f"{liq_risk}"
        f"{data_risk}"
        f"- Rủi ro kỹ thuật: Volatility phân vị ở mức {context['volatility_percentile']:.1%}, có thể xảy ra các nhịp rung lắc ngắn hạn."
    )
    
    # 7. Invalidation Conditions
    inval_list = [
        "1. Đường giá cắt xuống các vùng hỗ trợ kỹ thuật quan trọng ngắn hạn (đặc biệt là đường MA20 hoặc biên dưới nền giá tích lũy).",
        f"2. Trạng thái dòng tiền của cổ phiếu chuyển sang suy giảm mạnh hoặc xuất hiện phân phối lớn (DISTRIBUTION_RISK).",
        f"3. Sức mạnh dòng tiền của nhóm ngành {sector} yếu đi, đánh mất nhãn cải thiện và tụt hạng sâu."
    ]
    if cf_status in ("MISSING_DATA", "ZERO_VOLUME"):
        inval_list.append("4. Sự cố dữ liệu giao dịch kéo dài khiến các chỉ báo định lượng mất tính chính xác.")
    invalidation_conditions = "\n".join(inval_list)
    
    # 8. Action Plan
    action_plan = f"Kịch bản hành động được đề xuất:\n- Thao tác thực tế: {context['cashflow_action_note']}\n- Nên giải ngân từng phần khi có sự đồng thuận từ thị trường chung và điểm mua kỹ thuật đạt chuẩn, tuyệt đối tuân thủ kỷ luật cắt lỗ nếu vi phạm vùng hỗ trợ."
    
    # 9. Client Explanation
    if confirm == "STRONG_CONFIRMED":
        client_exp = (
            f"Cổ phiếu này đang thu hút dòng tiền lớn rất mạnh mẽ, đi kèm đà tăng giá rõ rệt. Đây là tín hiệu cho thấy "
            f"các nhà đầu tư tổ chức đang gia nhập tích cực. Quý khách có thể cân nhắc tích lũy thêm cổ phiếu này."
        )
    elif confirm == "CONFIRMED":
        client_exp = (
            f"Dòng tiền ngắn hạn đang cải thiện và ủng hộ đà phục hồi của cổ phiếu. Đây là trạng thái an toàn để nắm giữ "
            f"hoặc gia tăng vị thế từng phần ở vùng giá hợp lý."
        )
    elif state == "DRY_UP_WATCH":
        client_exp = (
            f"Cổ phiếu này đang ở trạng thái kiệt cung tích lũy, nghĩa là cả người mua và người bán đều đang tạm dừng giao dịch. "
            f"Giá đang đi ngang chặt chẽ. Quý khách nên đưa vào danh sách theo dõi sát, chuẩn bị cho nhịp tăng tiếp theo."
        )
    elif confirm == "CHECK_REQUIRED":
        client_exp = (
            f"Cổ phiếu hiện đang ghi nhận các dấu hiệu bất thường về khối lượng giao dịch (có thể do lỗi dữ liệu sàn hoặc "
            f"mất thanh khoản hoàn toàn). Quý khách nên tạm dừng mua bán mã này để đảm bảo an toàn tài khoản."
        )
    elif confirm == "CAUTION":
        client_exp = (
            f"Cổ phiếu đang gặp áp lực bán lớn hoặc có rủi ro thanh khoản thấp. Quý khách nên ưu tiên quản trị rủi ro, "
            f"hạn chế mua mới và cân nhắc hạ bớt tỷ trọng để bảo toàn danh mục."
        )
    else:
        client_exp = (
            f"Cổ phiếu đang đi ngang ổn định, cung cầu tương đối cân bằng. Quý khách nên tiếp tục nắm giữ vị thế cũ và "
            f"chờ đợi tín hiệu rõ ràng hơn từ thị trường trước khi đưa ra quyết định mới."
        )
    client_explanation = client_exp

    # Replace values in template
    note = template_str.replace("{SYMBOL}", symbol)
    note = note.replace("{INVESTMENT_THESIS}", thesis)
    note = note.replace("{QUANT_EVIDENCE}", quant_evidence)
    note = note.replace("{SECTOR_CONTEXT}", sector_context)
    note = note.replace("{CASHFLOW_CONFIRMATION}", cashflow_confirmation)
    note = note.replace("{TECHNICAL_SETUP}", technical_setup)
    note = note.replace("{RISK_FACTORS}", risk_factors)
    note = note.replace("{INVALIDATION_CONDITIONS}", invalidation_conditions)
    note = note.replace("{ACTION_PLAN}", action_plan)
    note = note.replace("{CLIENT_EXPLANATION}", client_explanation)
    
    # Verify no absolute terms exist
    note = note.replace("chắc chắn tăng", "có khả năng tăng")
    note = note.replace("cam kết lợi nhuận", "kỳ vọng tối ưu hóa danh mục")
    note = note.replace("mua ngay", "cân nhắc giải ngân từng phần")
    
    return note


def generate_research_notes(inputs: dict, template_str: str) -> tuple[pd.DataFrame, dict[str, str]]:
    cr = inputs["client_ready_watchlist"]
    if cr.empty or "symbol" not in cr.columns:
        return pd.DataFrame(), {}

    if "eligibility_status" in cr.columns:
        cr = cr[cr["eligibility_status"] != "REJECTED"].copy()

    if cr.empty:
        return pd.DataFrame(), {}

    symbols = cr["symbol"].dropna().unique()
    notes_dict = {}
    index_rows = []
    
    latest_date = "UNKNOWN"
    cf = inputs["cashflow_board"]
    if not cf.empty and "date" in cf.columns:
        latest_date = str(cf["date"].max())
        
    for sym in symbols:
        context = build_symbol_research_context(sym, inputs)
        note_md = generate_symbol_note_markdown(sym, context, template_str)
        notes_dict[sym] = note_md
        
        # Build brief summaries for the index
        thesis_lines = [line for line in note_md.split("\n") if line.strip()]
        
        thesis_idx = thesis_lines.index("## 1. Investment Thesis") if "## 1. Investment Thesis" in thesis_lines else -1
        risk_idx = thesis_lines.index("## 6. Risk Factors") if "## 6. Risk Factors" in thesis_lines else -1
        action_idx = thesis_lines.index("## 8. Action Plan") if "## 8. Action Plan" in thesis_lines else -1
        
        thesis_summary = "N/A"
        if thesis_idx != -1 and thesis_idx + 1 < len(thesis_lines):
            thesis_summary = thesis_lines[thesis_idx + 1].strip()
            
        risk_summary = "N/A"
        if risk_idx != -1 and risk_idx + 1 < len(thesis_lines):
            # Take the first bullet point or sentence
            candidate = thesis_lines[risk_idx + 1].strip()
            if candidate.startswith("-"):
                risk_summary = candidate.lstrip("- ").strip()
            else:
                risk_summary = candidate
                
        action_summary = "N/A"
        if action_idx != -1 and action_idx + 1 < len(thesis_lines):
            candidate = thesis_lines[action_idx + 1].strip()
            if len(candidate) > 200:
                action_summary = candidate[:197] + "..."
            else:
                action_summary = candidate
                
        index_rows.append({
            "symbol": sym,
            "generated_note_path": f"research_notes/generated/{sym}.md",
            "latest_date": context.get("latest_date", latest_date),
            "watchlist_tier": context["watchlist_tier"],
            "sector": context["sector"],
            "sector_label": context["sector_label"],
            "cashflow_status": context["cashflow_data_status"],
            "cashflow_score": context["cashflow_score"],
            "confirmation_status": context["confirmation_status"],
            "portfolio_weight": context["portfolio_weight"] if context["portfolio_weight"] is not None else np.nan,
            "capital_allocation": context["capital_allocation"] if context["capital_allocation"] is not None else np.nan,
            "key_thesis_summary": thesis_summary,
            "key_risk_summary": risk_summary,
            "action_summary": action_summary,
            "data_warnings": context["data_warnings"],
        })
        
    index_df = pd.DataFrame(index_rows)
    return index_df, notes_dict


def write_research_notes_outputs(
    index_df: pd.DataFrame,
    notes_dict: dict[str, str],
    metadata: dict,
    base_dir: str | Path = ".",
    output_dir: str | Path = "data/output",
) -> dict[str, object]:
    base = Path(base_dir)
    out_dir = base / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    
    generated_dir = base / "research_notes/generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    
    # Write markdown files
    for sym, md_content in notes_dict.items():
        note_path = generated_dir / f"{sym}.md"
        note_path.write_text(md_content, encoding="utf-8")
        
    # Write Parquet and CSV index
    index_parquet = out_dir / "research_notes_index.parquet"
    index_csv = out_dir / "research_notes_index.csv"
    metadata_json = out_dir / "research_notes_metadata.json"
    
    if not index_df.empty:
        save_parquet(index_df, index_parquet)
        index_df.to_csv(index_csv, index=False)
    else:
        # Create empty files
        pd.DataFrame().to_csv(index_csv, index=False)
        
    generated_files = [
        relative_path(index_parquet, base),
        relative_path(index_csv, base),
        relative_path(metadata_json, base),
    ]
    for sym in notes_dict.keys():
        generated_files.append(f"research_notes/generated/{sym}.md")
        
    payload = dict(metadata)
    # build_research_notes.py seeds this as "" with the comment "Filled by write
    # helper using utc_now_iso" -- but nothing ever filled it, so this was the
    # only sidecar in data/output/ shipping an empty timestamp while every other
    # one carried a real UTC time (Đợt 3 NV4). Fill it here, where the write
    # actually happens.
    payload["generated_at"] = utc_now_iso()
    payload["generated_files"] = [str(f) for f in generated_files]
    payload["lineage"] = validate_lineage_metadata(
        build_lineage_metadata(OFFICIAL_FEATURES_PATH, base_dir=base),
        label="research_notes_metadata.json",
    )
    write_json(payload, metadata_json)
    
    LOGGER.info("Research Notes outputs written successfully: %s", ", ".join(payload["generated_files"]))
    return payload
