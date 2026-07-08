from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import numpy as np

from src.analytics.cashflow_board import (
    compute_symbol_cashflow_metrics,
    compute_sector_cashflow_metrics,
    build_cashflow_watchlist_confirmation,
    build_cashflow_board,
    write_cashflow_outputs,
)


def _sample_features() -> pd.DataFrame:
    rows = []
    # Create history for 20 days so rolling averages are valid
    for i in range(25):
        date = f"2026-06-{i+1:02d}"
        # AAA is stable price but high volume (ACCUMULATION)
        # BBB is breakout price and high volume (CONFIRMED_INFLOW)
        # CCC is dropping price and high volume (DISTRIBUTION_RISK)
        # DDD is dropping price and low volume (WEAK_FLOW)
        rows.extend([
            {
                "symbol": "AAA",
                "date": date,
                "close": 10.0 + (0.01 * i),
                "volume": 2000 if i == 24 else 1500,
                "value": 2000000000.0 if i == 24 else 1500000000.0,
                "realized_vol_20d": 0.15,
                "volatility_percentile": 0.20,
            },
            {
                "symbol": "BBB",
                "date": date,
                "close": 20.0 + (5.0 if i == 24 else 0.05 * i),
                "volume": 2500 if i == 24 else 1000,
                "value": 5000000000.0 if i == 24 else 2000000000.0,
                "realized_vol_20d": 0.25,
                "volatility_percentile": 0.40,
            },
            {
                "symbol": "CCC",
                "date": date,
                "close": 30.0 - (1.0 if i == 24 else 0.02 * i),
                "volume": 3000 if i == 24 else 1000,
                "value": 9000000000.0 if i == 24 else 3000000000.0,
                "realized_vol_20d": 0.35,
                "volatility_percentile": 0.75,
            },
            {
                "symbol": "DDD",
                "date": date,
                "close": 15.0 - (0.05 * i),
                "volume": 500 if i == 24 else 1000,
                "value": 750000000.0 if i == 24 else 1500000000.0,
                "realized_vol_20d": 0.20,
                "volatility_percentile": 0.35,
            }
        ])
    return pd.DataFrame(rows)


def _sample_benchmark() -> pd.DataFrame:
    rows = []
    for i in range(25):
        date = f"2026-06-{i+1:02d}"
        rows.append({
            "symbol": "VNINDEX",
            "date": date,
            "close": 1000.0 + (2.0 * i),
            "return_20d": 0.04
        })
    return pd.DataFrame(rows)


def test_proxy_used_when_value_missing() -> None:
    features = _sample_features().copy()
    # Drop value column to force proxy calculation
    features = features.drop(columns=["value"])
    
    symbol_cf, proxy_used = compute_symbol_cashflow_metrics(features, benchmark_df=None)
    
    assert proxy_used is True
    assert "cashflow_value" in symbol_cf.columns
    # Check that cashflow_value = close * volume
    row_aaa = symbol_cf[symbol_cf["symbol"] == "AAA"].iloc[0]
    expected_val = row_aaa["close"] * row_aaa["volume"]
    assert np.isclose(row_aaa["cashflow_value"], expected_val)


def test_volume_metrics_calculation() -> None:
    features = _sample_features()
    symbol_cf, _ = compute_symbol_cashflow_metrics(features, benchmark_df=None)
    
    assert "volume_ratio_5d" in symbol_cf.columns
    assert "volume_ratio_20d" in symbol_cf.columns
    assert "volume_zscore_20d" in symbol_cf.columns
    assert "cashflow_value_20d" in symbol_cf.columns
    assert "cashflow_value_ratio_20d" in symbol_cf.columns


def test_state_classification() -> None:
    features = _sample_features()
    benchmark = _sample_benchmark()
    
    # Add sector column
    features["sector"] = "IT"
    
    symbol_cf, _ = compute_symbol_cashflow_metrics(features, benchmark_df=benchmark)
    
    # Extract states
    states = dict(zip(symbol_cf["symbol"], symbol_cf["cashflow_state"]))
    labels = dict(zip(symbol_cf["symbol"], symbol_cf["cashflow_label"]))
    
    # BBB has return_5d > 3% and volume_zscore > 1.5 -> breakout/confirmed inflow
    assert states["BBB"] == "CONFIRMED_INFLOW"
    assert labels["BBB"] == "STRONG"
    
    # CCC has price drop (return_5d < -2%) and high volume ratio/zscore -> distribution risk
    assert states["CCC"] == "DISTRIBUTION_RISK"
    assert labels["CCC"] == "RISKY"
    
    # AAA is consolidative price with building volume -> accumulation
    assert states["AAA"] == "ACCUMULATION"
    assert labels["AAA"] == "IMPROVING"

    # DDD has dropping price and low volume ratio (< 0.8) -> weak flow
    assert states["DDD"] == "WEAK_FLOW"
    assert labels["DDD"] == "WEAK"


def test_sector_cashflow_aggregation() -> None:
    features = _sample_features()
    # Assign sectors
    sector_map = {
        "AAA": "Banking",
        "BBB": "Banking",
        "CCC": "IT",
        "DDD": "IT"
    }
    features["sector"] = features["symbol"].map(sector_map)
    
    symbol_cf, _ = compute_symbol_cashflow_metrics(features, benchmark_df=None)
    sector_cf = compute_sector_cashflow_metrics(symbol_cf, latest_date="2026-06-25")
    
    assert not sector_cf.empty
    assert "sector_cashflow_score" in sector_cf.columns
    assert "sector_cashflow_label" in sector_cf.columns
    assert "top_cashflow_symbols" in sector_cf.columns
    
    # Check that sector labels exist
    assert set(sector_cf["sector"]) == {"Banking", "IT"}
    
    # Banking contains AAA (accumulation/improving) and BBB (confirmed inflow/strong) -> should rank high
    # IT contains CCC (dist risk) and DDD (weak) -> should rank lower
    banking_score = sector_cf[sector_cf["sector"] == "Banking"].iloc[0]["sector_cashflow_score"]
    it_score = sector_cf[sector_cf["sector"] == "IT"].iloc[0]["sector_cashflow_score"]
    assert banking_score > it_score


def test_watchlist_confirmation() -> None:
    features = _sample_features()
    features["sector"] = "IT"
    symbol_cf, _ = compute_symbol_cashflow_metrics(features, benchmark_df=None)
    
    client_ready = pd.DataFrame([{"symbol": "BBB"}])  # BBB is STRONG / CONFIRMED_INFLOW
    trading = pd.DataFrame([{"symbol": "AAA"}])       # AAA is IMPROVING / ACCUMULATION
    research = pd.DataFrame([{"symbol": "CCC"}, {"symbol": "DDD"}])  # CCC is RISKY, DDD is WEAK
    
    confirm = build_cashflow_watchlist_confirmation(
        symbol_cf,
        client_ready=client_ready,
        trading_watchlist=trading,
        research_candidates=research
    )
    
    assert not confirm.empty
    confirm_map = dict(zip(confirm["symbol"], confirm["confirmation_status"]))
    
    assert confirm_map["BBB"] == "STRONG_CONFIRMED"
    assert confirm_map["AAA"] == "CONFIRMED"
    assert confirm_map["CCC"] == "REJECT" or confirm_map["CCC"] == "CAUTION"
    assert confirm_map["DDD"] == "WATCH"


def test_write_outputs_and_metadata_validation(tmp_path: Path) -> None:
    symbol_cf = pd.DataFrame([{
        "symbol": "AAA", "sector": "Banking", "date": "2026-06-25",
        "close": 10.0, "volume": 100, "cashflow_value": 1000.0,
        "cashflow_intensity_score": 80.0, "cashflow_score": 75.0,
        "cashflow_state": "ACCUMULATION", "cashflow_label": "IMPROVING", "volume_ratio_20d": 1.2
    }])
    sector_cf = pd.DataFrame([{
        "sector": "Banking", "latest_date": "2026-06-25", "n_symbols": 1,
        "sector_cashflow_score": 80.0, "sector_cashflow_rank": 1, "sector_cashflow_label": "STRONG_INFLOW"
    }])
    watchlist_confirm = pd.DataFrame([{
        "symbol": "AAA", "sector": "Banking", "watchlist_tier": "client_ready",
        "cashflow_score": 75.0, "cashflow_state": "ACCUMULATION", "cashflow_label": "IMPROVING",
        "confirmation_status": "CONFIRMED", "cashflow_reason": "Good accumulation"
    }])
    
    metadata = {
        "generated_at": "2026-06-25T15:00:00Z",
        "status": "OK",
        "latest_date": "2026-06-25",
        "n_symbols": 1,
        "n_sectors": 1,
        "value_proxy_used": False,
        "warnings": [],
        "generated_files": [],
    }
    
    payload = write_cashflow_outputs(
        symbol_cf, sector_cf, watchlist_confirm, metadata,
        base_dir=tmp_path
    )
    
    assert payload["generated_files"]
    metadata_file = tmp_path / "data/output/cashflow_board_metadata.json"
    assert metadata_file.exists()
    
    loaded = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert loaded["status"] == "OK"
    assert loaded["latest_date"] == "2026-06-25"


def test_cashflow_board_calibration_v1_1() -> None:
    # 1. Test symbol-level zero/missing volume and DRY_UP_WATCH
    rows = []
    for i in range(25):
        date = f"2026-06-{i+1:02d}"
        rows.extend([
            {
                # ZERO_VOLUME test symbol
                "symbol": "ZERO_VOL",
                "date": date,
                "close": 10.0,
                "volume": 0.0 if i >= 20 else 100.0,
                "value": 0.0 if i >= 20 else 1000.0,
                "realized_vol_20d": 0.1,
                "volatility_percentile": 0.1,
            },
            {
                # MISSING_VOLUME test symbol
                "symbol": "MISSING_VOL",
                "date": date,
                "close": 10.0,
                "volume": np.nan if i == 24 else 100.0,
                "value": np.nan if i == 24 else 1000.0,
                "realized_vol_20d": 0.1,
                "volatility_percentile": 0.1,
            },
            {
                # DRY_UP_WATCH test symbol
                "symbol": "DRY_UP",
                "date": date,
                "close": 10.0 + (0.001 * i),
                "volume": 20.0 if i == 24 else 100.0,
                "value": 200.0 if i == 24 else 1000.0,
                "realized_vol_20d": 0.05,
                "volatility_percentile": 0.15,
            },
            {
                # LOW_LIQUIDITY symbol
                "symbol": "LOW_LIQ",
                "date": date,
                "close": 10.0,
                "volume": 10.0,
                "value": 100.0,
                "realized_vol_20d": 0.1,
                "volatility_percentile": 0.3,
            }
        ])
        
    features = pd.DataFrame(rows)
    symbol_cf, _ = compute_symbol_cashflow_metrics(features, benchmark_df=None)
    
    assert not symbol_cf.empty
    states = dict(zip(symbol_cf["symbol"], symbol_cf["cashflow_state"]))
    status = dict(zip(symbol_cf["symbol"], symbol_cf["cashflow_data_status"]))
    
    assert status["ZERO_VOL"] == "ZERO_VOLUME"
    assert states["ZERO_VOL"] == "CHECK_REQUIRED"
    
    assert status["MISSING_VOL"] == "MISSING_DATA"
    assert states["MISSING_VOL"] == "CHECK_REQUIRED"
    
    assert states["DRY_UP"] == "DRY_UP_WATCH"
    assert status["LOW_LIQ"] == "LOW_LIQUIDITY"
    
    # 2. Test Sector Sample Size Adjustment and Demotion
    symbol_cf_mock = pd.DataFrame([
        {
            "symbol": "S1", "sector": "SmallSector", "date": "2026-06-30",
            "close": 10.0, "volume": 100, "cashflow_value": 1000.0, "cashflow_value_20d": 1000.0,
            "cashflow_intensity_score": 90.0, "cashflow_score": 90.0, "volume_ratio_20d": 1.5, "return_5d": 0.05,
            "cashflow_state": "CONFIRMED_INFLOW", "cashflow_label": "STRONG", "cashflow_data_status": "OK"
        },
        {
            "symbol": "N1", "sector": "NormalSector", "date": "2026-06-30",
            "close": 10.0, "volume": 100, "cashflow_value": 1000.0, "cashflow_value_20d": 1000.0,
            "cashflow_intensity_score": 70.0, "cashflow_score": 70.0, "volume_ratio_20d": 1.1, "return_5d": 0.02,
            "cashflow_state": "CONFIRMED_INFLOW", "cashflow_label": "STRONG", "cashflow_data_status": "OK"
        },
        {
            "symbol": "N2", "sector": "NormalSector", "date": "2026-06-30",
            "close": 10.0, "volume": 100, "cashflow_value": 1000.0, "cashflow_value_20d": 1000.0,
            "cashflow_intensity_score": 70.0, "cashflow_score": 70.0, "volume_ratio_20d": 1.1, "return_5d": 0.02,
            "cashflow_state": "CONFIRMED_INFLOW", "cashflow_label": "STRONG", "cashflow_data_status": "OK"
        },
        {
            "symbol": "N3", "sector": "NormalSector", "date": "2026-06-30",
            "close": 10.0, "volume": 100, "cashflow_value": 1000.0, "cashflow_value_20d": 1000.0,
            "cashflow_intensity_score": 70.0, "cashflow_score": 70.0, "volume_ratio_20d": 1.1, "return_5d": 0.02,
            "cashflow_state": "CONFIRMED_INFLOW", "cashflow_label": "STRONG", "cashflow_data_status": "OK"
        },
        {
            "symbol": "N4", "sector": "NormalSector", "date": "2026-06-30",
            "close": 10.0, "volume": 100, "cashflow_value": 1000.0, "cashflow_value_20d": 1000.0,
            "cashflow_intensity_score": 70.0, "cashflow_score": 70.0, "volume_ratio_20d": 1.1, "return_5d": 0.02,
            "cashflow_state": "CONFIRMED_INFLOW", "cashflow_label": "STRONG", "cashflow_data_status": "OK"
        },
        {
            "symbol": "N5", "sector": "NormalSector", "date": "2026-06-30",
            "close": 10.0, "volume": 100, "cashflow_value": 1000.0, "cashflow_value_20d": 1000.0,
            "cashflow_intensity_score": 70.0, "cashflow_score": 70.0, "volume_ratio_20d": 1.1, "return_5d": 0.02,
            "cashflow_state": "CONFIRMED_INFLOW", "cashflow_label": "STRONG", "cashflow_data_status": "OK"
        },
        {
            "symbol": "N6", "sector": "NormalSector", "date": "2026-06-30",
            "close": 10.0, "volume": 100, "cashflow_value": 1000.0, "cashflow_value_20d": 1000.0,
            "cashflow_intensity_score": 70.0, "cashflow_score": 70.0, "volume_ratio_20d": 1.1, "return_5d": 0.02,
            "cashflow_state": "CONFIRMED_INFLOW", "cashflow_label": "STRONG", "cashflow_data_status": "OK"
        }
    ])
    
    sector_cf = compute_sector_cashflow_metrics(symbol_cf_mock, latest_date="2026-06-30")
    
    sec_sizes = dict(zip(sector_cf["sector"], sector_cf["sector_sample_size_label"]))
    sec_labels = dict(zip(sector_cf["sector"], sector_cf["sector_cashflow_label"]))
    
    assert sec_sizes["SmallSector"] == "SMALL"
    assert sec_sizes["NormalSector"] == "NORMAL"
    assert sec_labels["SmallSector"] != "STRONG_INFLOW"
    
    # 3. Test Watchlist Confirmation and Commentary
    client_ready = pd.DataFrame([
        {"symbol": "S1"},
        {"symbol": "N1"},
    ])
    
    confirm = build_cashflow_watchlist_confirmation(
        symbol_cf_mock,
        client_ready=client_ready
    )
    
    assert "cashflow_reason" in confirm.columns
    assert "cashflow_action_note" in confirm.columns
    assert not confirm["cashflow_reason"].isna().any()
    assert not confirm["cashflow_action_note"].isna().any()
    
    # Check new metadata keys
    _, _, _, meta = build_cashflow_board(
        stock_features=symbol_cf_mock,
        client_ready=client_ready
    )
    
    assert "n_data_quality_warnings" in meta
    assert "n_low_liquidity_symbols" in meta
    assert "n_zero_volume_symbols" in meta
    assert "confirmation_counts" in meta
    assert "sector_score_warnings" in meta


def test_confirmation_guard_downgrades_contradictory_improving() -> None:
    """I1: label IMPROVING + state WEAK_FLOW + volume 0.10x must NOT be CONFIRMED."""
    symbol_cf = pd.DataFrame(
        [
            {
                "symbol": "VVV", "sector": "Real Estate", "cashflow_score": 60.9,
                "cashflow_state": "WEAK_FLOW", "cashflow_label": "IMPROVING",
                "volume_ratio_20d": 0.10, "return_5d": 0.01, "cashflow_data_status": "OK",
            },
            {
                "symbol": "GGG", "sector": "Banking", "cashflow_score": 75.0,
                "cashflow_state": "CONFIRMED_INFLOW", "cashflow_label": "IMPROVING",
                "volume_ratio_20d": 1.20, "return_5d": 0.03, "cashflow_data_status": "OK",
            },
        ]
    )
    confirm = build_cashflow_watchlist_confirmation(
        symbol_cf,
        client_ready=pd.DataFrame([{"symbol": "VVV"}, {"symbol": "GGG"}]),
        trading_watchlist=pd.DataFrame(),
        research_candidates=pd.DataFrame(),
    )
    confirm_map = dict(zip(confirm["symbol"], confirm["confirmation_status"]))
    assert confirm_map["VVV"] == "WATCH", "contradictory IMPROVING must downgrade to WATCH"
    assert confirm_map["GGG"] == "CONFIRMED", "consistent IMPROVING must stay CONFIRMED"
    vvv_reason = confirm.set_index("symbol").loc["VVV", "cashflow_reason"]
    assert "Mâu thuẫn" in vvv_reason


def test_confirmation_guard_keeps_stealth_accumulation_exempt() -> None:
    """I1: low-volume ACCUMULATION on trading tier is legit stealth — not downgraded."""
    symbol_cf = pd.DataFrame(
        [
            {
                "symbol": "SSS", "sector": "IT", "cashflow_score": 62.0,
                "cashflow_state": "ACCUMULATION", "cashflow_label": "IMPROVING",
                "volume_ratio_20d": 0.50, "return_5d": 0.01, "cashflow_data_status": "OK",
            },
        ]
    )
    confirm = build_cashflow_watchlist_confirmation(
        symbol_cf,
        client_ready=pd.DataFrame(),
        trading_watchlist=pd.DataFrame([{"symbol": "SSS"}]),
        research_candidates=pd.DataFrame(),
    )
    assert confirm.set_index("symbol").loc["SSS", "confirmation_status"] == "CONFIRMED"
