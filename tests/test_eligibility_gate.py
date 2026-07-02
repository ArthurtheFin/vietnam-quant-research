from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.screening.final_watchlist import apply_eligibility_gate, apply_post_cashflow_overlay
from src.portfolio.input_resolver import load_default_portfolio_candidates
from src.data.loaders import save_parquet


@pytest.fixture
def sample_watchlist() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "CTS",
                "date": pd.Timestamp("2026-06-30"),
                "close": 26800.0,
                "latest_volume": 2629900.0,
                "value_ma20": 10_000_000_000.0,
                "volume_ma20": 200_000.0,
                "candidate_tier": "Client Ready",
                "is_client_ready": True,
                "confidence_label": "High",
                "exclusion_reason": "",
            },
            {
                "symbol": "ABB",
                "date": pd.Timestamp("2026-06-30"),
                "close": 18100.0,
                "latest_volume": 0.0,
                "value_ma20": 8_000_000_000.0,
                "volume_ma20": 150_000.0,
                "candidate_tier": "Client Ready",
                "is_client_ready": True,
                "confidence_label": "Medium",
                "exclusion_reason": "",
            },
            {
                "symbol": "BVB",
                "date": pd.Timestamp("2026-06-30"),
                "close": 13700.0,
                "latest_volume": np.nan,
                "value_ma20": 7_000_000_000.0,
                "volume_ma20": 120_000.0,
                "candidate_tier": "Client Ready",
                "is_client_ready": True,
                "confidence_label": "Medium",
                "exclusion_reason": "",
            },
            {
                "symbol": "XYZ",
                "date": pd.Timestamp("2026-06-30"),
                "close": -50.0,
                "latest_volume": 10000.0,
                "value_ma20": 7_000_000_000.0,
                "volume_ma20": 120_000.0,
                "candidate_tier": "Client Ready",
                "is_client_ready": True,
                "confidence_label": "Medium",
                "exclusion_reason": "",
            },
        ]
    )


@pytest.fixture
def sample_cashflow_board() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "CTS",
                "volume": 2629900.0,
                "cashflow_data_status": "OK",
                "cashflow_state": "NEUTRAL",
                "value_ma20": 10_000_000_000.0,
                "volume_ma20": 200_000.0,
            },
            {
                "symbol": "ABB",
                "volume": 0.0,
                "cashflow_data_status": "ZERO_VOLUME",
                "cashflow_state": "NEUTRAL",
                "value_ma20": 8_000_000_000.0,
                "volume_ma20": 150_000.0,
            },
            {
                "symbol": "BVB",
                "volume": 0.0,
                "cashflow_data_status": "CHECK_REQUIRED",
                "cashflow_state": "NEUTRAL",
                "value_ma20": 7_000_000_000.0,
                "volume_ma20": 120_000.0,
            },
            {
                "symbol": "XYZ",
                "volume": 10000.0,
                "cashflow_data_status": "OK",
                "cashflow_state": "NEUTRAL",
                "value_ma20": 7_000_000_000.0,
                "volume_ma20": 120_000.0,
            },
        ]
    )


@pytest.fixture
def sample_watchlist_cashflow_confirmation() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"symbol": "CTS", "confirmation_status": "STRONG_CONFIRMED"},
            {"symbol": "ABB", "confirmation_status": "CHECK_REQUIRED"},
            {"symbol": "BVB", "confirmation_status": "CHECK_REQUIRED"},
            {"symbol": "XYZ", "confirmation_status": "WATCH"},
        ]
    )


def test_apply_eligibility_gate_filters_properly(
    sample_watchlist, sample_cashflow_board, sample_watchlist_cashflow_confirmation
) -> None:
    gated = apply_eligibility_gate(
        sample_watchlist, sample_cashflow_board, sample_watchlist_cashflow_confirmation
    )

    # CTS is eligible
    cts = gated[gated["symbol"] == "CTS"].iloc[0]
    assert cts["eligibility_status"] == "ELIGIBLE"
    assert cts["is_client_ready"] == True
    assert cts["candidate_tier"] == "Client Ready"

    # ABB is rejected because of zero volume and ZERO_VOLUME cashflow status
    abb = gated[gated["symbol"] == "ABB"].iloc[0]
    assert abb["eligibility_status"] == "REJECTED"
    assert "ZERO_VOLUME_OR_MISSING_DATA" in abb["eligibility_reason"]
    assert "CASHFLOW_CHECK_REQUIRED" in abb["eligibility_reason"]
    assert abb["is_client_ready"] == False
    assert abb["candidate_tier"] != "Client Ready"

    # BVB is rejected because of missing/zero volume and CHECK_REQUIRED status
    bvb = gated[gated["symbol"] == "BVB"].iloc[0]
    assert bvb["eligibility_status"] == "REJECTED"
    assert "ZERO_VOLUME_OR_MISSING_DATA" in bvb["eligibility_reason"]
    assert bvb["is_client_ready"] == False

    # XYZ is rejected because of close <= 0 (INVALID_CLOSE)
    xyz = gated[gated["symbol"] == "XYZ"].iloc[0]
    assert xyz["eligibility_status"] == "REJECTED"
    assert "INVALID_CLOSE" in xyz["eligibility_reason"]
    assert xyz["is_client_ready"] == False


def test_eligibility_gate_works_without_cashflow(sample_watchlist) -> None:
    # Runs successfully without cashflow data (only screens price/volume)
    gated = apply_eligibility_gate(sample_watchlist, None, None)
    
    cts = gated[gated["symbol"] == "CTS"].iloc[0]
    assert cts["eligibility_status"] == "ELIGIBLE"

    abb = gated[gated["symbol"] == "ABB"].iloc[0]
    assert abb["eligibility_status"] == "REJECTED"
    assert "ZERO_VOLUME_OR_MISSING_DATA" in abb["eligibility_reason"]


def test_post_cashflow_overlay_executes_successfully(
    tmp_path, sample_watchlist, sample_cashflow_board, sample_watchlist_cashflow_confirmation
) -> None:
    # Set up temp workspace structure
    (tmp_path / "data/output").mkdir(parents=True)
    (tmp_path / "data/signals").mkdir(parents=True)

    save_parquet(sample_watchlist, tmp_path / "data/output/client_ready_watchlist.parquet")
    save_parquet(sample_watchlist, tmp_path / "data/output/trading_watchlist.parquet")
    save_parquet(sample_watchlist, tmp_path / "data/output/research_candidates.parquet")
    save_parquet(sample_watchlist, tmp_path / "data/signals/final_watchlist.parquet")
    save_parquet(sample_cashflow_board, tmp_path / "data/output/cashflow_board.parquet")
    save_parquet(
        sample_watchlist_cashflow_confirmation,
        tmp_path / "data/output/watchlist_cashflow_confirmation.parquet",
    )

    # Execute overlay
    apply_post_cashflow_overlay(tmp_path)

    # Verify that updated client_ready does not contain rejected symbols (ABB, BVB, XYZ)
    cr_path = tmp_path / "data/output/client_ready_watchlist.parquet"
    assert cr_path.exists()
    cr_updated = pd.read_parquet(cr_path)
    assert len(cr_updated) == 1
    assert cr_updated.iloc[0]["symbol"] == "CTS"

    # Verify that data_review_watchlist was generated with the rejected symbols
    dr_path = tmp_path / "data/output/data_review_watchlist.parquet"
    assert dr_path.exists()
    dr_df = pd.read_parquet(dr_path)
    assert len(dr_df) == 3
    assert set(dr_df["symbol"]) == {"ABB", "BVB", "XYZ"}

    # Verify that rejected symbols were appended to research_candidates
    rc_path = tmp_path / "data/output/research_candidates.parquet"
    assert rc_path.exists()
    rc_df = pd.read_parquet(rc_path)
    assert "ABB" in rc_df["symbol"].values
    assert "BVB" in rc_df["symbol"].values
    assert "XYZ" in rc_df["symbol"].values
    assert rc_df[rc_df["symbol"] == "ABB"].iloc[0]["eligibility_status"] == "REJECTED"


def test_watchlist_exclusivity() -> None:
    # Build a simulated universe features DataFrame
    dates = pd.bdate_range("2026-06-01", periods=10)
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ", "KKK", "LLL", "MMM", "NNN", "OOO"]
    rows = []
    for s in symbols:
        for d in dates:
            rows.append({
                "symbol": s,
                "date": d,
                "close": 10.0 + np.random.randn() * 0.1,
                "volume": 100000.0,
                "value_ma20": 10_000_000_000.0,
                "volume_ma20": 100000.0,
                "above_ma50": True,
                "above_ma200": True,
                "return_20d": 0.05,
                "return_60d": 0.10,
                "atr_pct_14": 0.02,
                "distance_ma20": 0.01,
            })
    features = pd.DataFrame(rows)

    # Mock meta ranking
    meta = pd.DataFrame([
        {"symbol": s, "date": dates[-1], "meta_score": 75.0, "trade_edge_score": 70.0, "setup_quality_score": 70.0}
        for s in symbols
    ])

    # Build watchlists
    from src.screening.final_watchlist import build_watchlist_tiers
    outputs = build_watchlist_tiers(
        features=features,
        benchmark=None,
        meta_ranking=meta,
        alpha_scores=pd.DataFrame(),
        config={"watchlist_size": 5},
    )

    cr = outputs["client_ready_watchlist"]
    tw = outputs["trading_watchlist"]
    rc = outputs["research_candidates"]

    # Verify no overlaps
    cr_syms = set(cr["symbol"])
    tw_syms = set(tw["symbol"])
    rc_syms = set(rc["symbol"])

    # Client Ready symbols do not appear in trading_watchlist
    assert len(cr_syms.intersection(tw_syms)) == 0

    # Client Ready symbols do not appear in research_candidates
    assert len(cr_syms.intersection(rc_syms)) == 0

    # Trading Watchlist symbols do not appear in research_candidates
    # (except if they were rejected, but here none are rejected)
    assert len(tw_syms.intersection(rc_syms)) == 0

    # Check extra keys exist
    assert "eligible_candidates" in outputs
    assert "all_scored_candidates" in outputs
    assert len(outputs["client_ready_watchlist"]) <= 5
    assert len(outputs["trading_watchlist"]) <= 20

