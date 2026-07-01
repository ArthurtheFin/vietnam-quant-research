from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import numpy as np

from src.reporting.research_notes import (
    build_symbol_research_context,
    generate_symbol_note_markdown,
    generate_research_notes,
    load_research_inputs,
    write_research_notes_outputs,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _sample_inputs() -> dict:
    cr = pd.DataFrame([
        {"symbol": "CTS", "sector": "Securities", "confidence_label": "STRONG"},
        {"symbol": "ABB", "sector": "Banking", "confidence_label": "NEUTRAL"},
    ])
    tw = pd.DataFrame()
    sb = pd.DataFrame([
        {
            "sector": "Securities", "sector_cashflow_label": "STRONG_INFLOW", "sector_cashflow_rank": 1,
            "sector_cashflow_score": 75.0, "n_symbols_with_valid_cashflow": 15,
            "sector_score_quality": "HIGH", "sector_score_warning": "", "top_cashflow_symbols": "CTS"
        },
        {
            "sector": "Banking", "sector_cashflow_label": "WEAK", "sector_cashflow_rank": 20,
            "sector_cashflow_score": 25.0, "n_symbols_with_valid_cashflow": 20,
            "sector_score_quality": "HIGH", "sector_score_warning": "", "top_cashflow_symbols": "MSB"
        }
    ])
    sl = pd.DataFrame()
    cf = pd.DataFrame([
        {
            "symbol": "CTS", "date": "2026-06-30", "cashflow_score": 88.0, "cashflow_state": "CONFIRMED_INFLOW",
            "cashflow_label": "STRONG", "cashflow_data_status": "OK", "volume_ratio_20d": 1.5, "return_5d": 0.05,
            "return_10d": 0.08, "volatility_percentile": 0.35, "relative_return_20d_vs_vnindex": 0.03,
            "close": 15000.0, "cashflow_value": 500000000.0, "data_quality_flag": False
        },
        {
            "symbol": "ABB", "date": "2026-06-30", "cashflow_score": 45.0, "cashflow_state": "CHECK_REQUIRED",
            "cashflow_label": "NEUTRAL", "cashflow_data_status": "ZERO_VOLUME", "volume_ratio_20d": 0.0, "return_5d": 0.0,
            "return_10d": 0.0, "volatility_percentile": 0.20, "relative_return_20d_vs_vnindex": -0.05,
            "close": 8000.0, "cashflow_value": 0.0, "data_quality_flag": True
        }
    ])
    wcc = pd.DataFrame([
        {
            "symbol": "CTS", "confirmation_status": "STRONG_CONFIRMED",
            "cashflow_reason": "Xác nhận mạnh: volume tăng mạnh 1.5x, giá tăng 5%.",
            "cashflow_action_note": "Khuyến nghị MUA/GIA TĂNG tỷ trọng."
        },
        {
            "symbol": "ABB", "confirmation_status": "CHECK_REQUIRED",
            "cashflow_reason": "Cần kiểm tra: volume bằng 0.",
            "cashflow_action_note": "Tạm ngưng giao dịch."
        }
    ])
    pw = pd.DataFrame([
        {"symbol": "CTS", "risk_parity": 0.12, "equal_weight": 0.10}
    ])
    cp = pd.DataFrame([
        {"symbol": "CTS", "position_value": 120000000.0, "target_weight": 0.12}
    ])
    
    return {
        "client_ready_watchlist": cr,
        "trading_watchlist": tw,
        "sector_board": sb,
        "sector_leaders": sl,
        "sector_cashflow": sb,
        "cashflow_board": cf,
        "watchlist_cashflow_confirmation": wcc,
        "portfolio_weights": pw,
        "capital_plan": cp,
        "pipeline_metadata": {},
        "cashflow_board_metadata": {},
        "sector_board_metadata": {},
    }


def test_research_notes_generator() -> None:
    inputs = _sample_inputs()
    template_path = PROJECT_ROOT / "research_notes/templates/stock_research_note_template.md"
    assert template_path.exists()
    template_str = template_path.read_text(encoding="utf-8")
    
    index_df, notes_dict = generate_research_notes(inputs, template_str)
    
    # 1. Assert markdown is generated and not empty
    assert len(notes_dict) == 2
    assert "CTS" in notes_dict
    assert "ABB" in notes_dict
    
    cts_note = notes_dict["CTS"]
    assert cts_note
    
    # 2. Note contains all the main sections
    required_sections = [
        "# CTS Research Note",
        "## 1. Investment Thesis",
        "## 2. Quant Evidence",
        "## 3. Sector Context",
        "## 4. Cashflow Confirmation",
        "## 5. Technical Setup",
        "## 6. Risk Factors",
        "## 7. Invalidation Conditions",
        "## 8. Action Plan",
        "## 9. Client Explanation",
        "## 10. Disclaimer",
    ]
    for section in required_sections:
        assert section in cts_note
        
    # 3. Does not use absolute/certain keywords
    forbidden_words = ["cam kết lợi nhuận", "chắc chắn tăng", "mua ngay"]
    for word in forbidden_words:
        assert word not in cts_note.lower()
        
    # 4. If cashflow data status is CHECK_REQUIRED/ZERO_VOLUME, warning is present
    abb_note = notes_dict["ABB"]
    assert "Cảnh báo chất lượng dữ liệu: khối lượng giao dịch bằng 0" in abb_note
    assert "CHECK_REQUIRED" in abb_note
    
    # 5. If missing portfolio weight, it does not invent the weight
    # ABB has no entry in pw or cp
    abb_context = build_symbol_research_context("ABB", inputs)
    assert abb_context["portfolio_weight"] is None
    assert abb_context["capital_allocation"] is None
    assert "Tỷ trọng danh mục gợi ý" not in generate_symbol_note_markdown("ABB", abb_context, template_str)
    
    # 6. Index has all the required columns
    required_cols = {
        "symbol", "generated_note_path", "latest_date", "watchlist_tier",
        "sector", "sector_label", "cashflow_status", "cashflow_score",
        "confirmation_status", "portfolio_weight", "capital_allocation",
        "key_thesis_summary", "key_risk_summary", "action_summary", "data_warnings"
    }
    assert required_cols.issubset(index_df.columns)
    
    # 7. Write output and verify metadata keys
    metadata = {
        "status": "OK",
        "latest_date": "2026-06-30",
        "n_notes_generated": len(notes_dict),
        "warnings": [],
    }
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        payload = write_research_notes_outputs(
            index_df=index_df,
            notes_dict=notes_dict,
            metadata=metadata,
            base_dir=tmp_dir
        )
        
        assert payload["status"] == "OK"
        assert payload["n_notes_generated"] == 2
        assert "generated_files" in payload
        
        meta_json_path = Path(tmp_dir) / "data/output/research_notes_metadata.json"
        assert meta_json_path.exists()
        loaded_meta = json.loads(meta_json_path.read_text(encoding="utf-8"))
        assert loaded_meta["n_notes_generated"] == 2
        assert loaded_meta["latest_date"] == "2026-06-30"
