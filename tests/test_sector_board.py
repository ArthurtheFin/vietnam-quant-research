from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.analytics.sector_board import (
    attach_sector,
    audit_sector_mapping,
    build_sector_board,
    load_sector_map,
    normalize_sector_map,
    write_sector_outputs,
)
from src.utils.pipeline_io import validate_sector_board_metadata


def _sample_features() -> pd.DataFrame:
    rows = []
    for date, aaa_close, bbb_close, ccc_close in [
        ("2026-06-26", 10.0, 20.0, 30.0),
        ("2026-06-27", 10.2, 20.1, 30.1),
        ("2026-06-28", 10.5, 20.3, 29.8),
        ("2026-06-29", 10.8, 20.5, 29.7),
        ("2026-06-30", 11.0, 20.8, 29.5),
    ]:
        rows.extend(
            [
                {"symbol": "AAA", "date": date, "close": aaa_close, "volume": 1000, "value": aaa_close * 1000, "return_5d": 0.10, "return_10d": 0.12, "return_20d": 0.20, "above_ma20": True, "above_ma50": True, "realized_vol_20d": 0.18, "volatility_percentile": 0.20, "volume_zscore_20d": 1.2},
                {"symbol": "BBB", "date": date, "close": bbb_close, "volume": 800, "value": bbb_close * 800, "return_5d": 0.06, "return_10d": 0.08, "return_20d": 0.12, "above_ma20": True, "above_ma50": False, "realized_vol_20d": 0.22, "volatility_percentile": 0.45, "volume_zscore_20d": 0.7},
                {"symbol": "CCC", "date": date, "close": ccc_close, "volume": 500, "value": ccc_close * 500, "return_5d": -0.03, "return_10d": -0.01, "return_20d": -0.05, "above_ma20": False, "above_ma50": False, "realized_vol_20d": 0.35, "volatility_percentile": 0.80, "volume_zscore_20d": -0.4},
            ]
        )
    return pd.DataFrame(rows)


def _sample_benchmark() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"symbol": "VNINDEX", "date": "2026-06-29", "close": 1000.0, "return_20d": 0.03, "return_10d": 0.02, "return_5d": 0.01},
            {"symbol": "VNINDEX", "date": "2026-06-30", "close": 1005.0, "return_20d": 0.04, "return_10d": 0.03, "return_5d": 0.015},
        ]
    )


def test_attach_sector_uses_mapping_and_unknown_fallback() -> None:
    features = _sample_features()
    sector_map = pd.DataFrame(
        [
            {"symbol": "AAA", "sector": "Banking", "industry": "Commercial Banks", "exchange": "HOSE", "source": "test", "updated_at": "2026-06-30"},
            {"symbol": "BBB", "sector": "Technology", "industry": "Software", "exchange": "HOSE", "source": "test", "updated_at": "2026-06-30"},
        ]
    )

    attached, meta = attach_sector(features, sector_map=sector_map)

    latest = attached.sort_values(["symbol", "date"]).groupby("symbol", as_index=False).tail(1)
    sectors = dict(zip(latest["symbol"], latest["sector"]))
    assert sectors["AAA"] == "Banking"
    assert sectors["BBB"] == "Technology"
    assert sectors["CCC"] == "UNKNOWN"
    assert meta["unknown_ratio"] > 0


def test_build_sector_board_handles_missing_map_with_warning() -> None:
    features = _sample_features()
    benchmark = _sample_benchmark()
    client_ready = pd.DataFrame([{"symbol": "AAA", "date": "2026-06-30", "final_score": 90.0, "reason": "Strong momentum"}])
    trading = pd.DataFrame([{"symbol": "BBB", "date": "2026-06-30", "final_score": 70.0, "reason": "Improving setup"}])

    board, leaders, metadata = build_sector_board(
        stock_features=features,
        benchmark_vnindex=benchmark,
        client_ready=client_ready,
        trading_watchlist=trading,
        research_candidates=pd.DataFrame(),
        sector_map=pd.DataFrame(),
        sector_map_metadata={"warnings": ["No sector map"], "rows": 0, "source_path": None, "template_path": "config/sector_map_template.csv"},
    )

    assert not board.empty
    assert not leaders.empty
    assert metadata["status"] == "WARNING"
    assert any("UNKNOWN" in str(item) or "No sector map" in str(item) for item in metadata["warnings"])
    assert "sector_total_score" in board.columns
    assert "leader_reason" in leaders.columns


def test_write_sector_outputs_and_metadata_validation(tmp_path: Path) -> None:
    board = pd.DataFrame([{"sector": "Banking", "latest_date": "2026-06-30", "n_sectors": 1, "sector_total_score": 80.0}])
    leaders = pd.DataFrame([{"sector": "Banking", "symbol": "AAA", "latest_date": "2026-06-30", "leader_rank_in_sector": 1, "leader_reason": "20D return 20.0%"}])
    metadata = {
        "generated_at": "2026-06-30T00:00:00+00:00",
        "status": "OK",
        "latest_date": "2026-06-30",
        "n_sectors": 1,
        "sector_map_source": "config/sector_map.csv",
        "sector_map_rows": 3,
        "sector_map_template": "config/sector_map_template.csv",
        "mapping_coverage": 1.0,
        "unknown_ratio": 0.0,
        "total_symbols": 3,
        "mapped_symbols": 3,
        "missing_symbols": 0,
        "warnings": [],
        "generated_files": [],
    }

    # write_sector_outputs now embeds reproducibility lineage (audit gate
    # #12 convention), which needs a real features file on disk to hash.
    features_path = tmp_path / "data/processed/stock_features.parquet"
    features_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"symbol": ["AAA"], "date": [pd.Timestamp("2026-06-30")]}).to_parquet(features_path)

    payload = write_sector_outputs(board, leaders, metadata, base_dir=tmp_path)
    assert payload["generated_files"]
    assert validate_sector_board_metadata(payload) == payload
    loaded = json.loads((tmp_path / "data/output/sector_board_metadata.json").read_text(encoding="utf-8"))
    assert loaded["status"] == "OK"


def test_load_sector_map_uses_fallback_symbol_map_and_template(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "config/screens"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "stealth_accumulation.yaml").write_text(
        "sector:\n  symbol_map:\n    AAA: Banking\n    BBB: Technology\n",
        encoding="utf-8",
    )

    sector_map, meta = load_sector_map(base_dir=tmp_path)

    assert set(sector_map["symbol"]) == {"AAA", "BBB"}
    assert meta["rows"] == 2
    assert Path(tmp_path / "config/sector_map_template.csv").exists()


def test_normalize_sector_map_applies_defaults_and_deduplicates() -> None:
    raw = pd.DataFrame(
        [
            {"symbol": "aaa", "sector": "Banking", "industry": None, "exchange": "hose", "source": None, "updated_at": None},
            {"symbol": "AAA", "sector": "Banking 2", "industry": "Banks", "exchange": "HOSE", "source": "manual", "updated_at": "2026-06-30"},
            {"symbol": None, "sector": "Unknown", "industry": None, "exchange": None, "source": None, "updated_at": None},
        ]
    )
    normalized, stats = normalize_sector_map(raw, default_source="provided_sector_map", default_updated_at="2026-07-01")

    assert list(normalized["symbol"]) == ["AAA"]
    assert normalized.iloc[0]["source"] == "manual"
    assert normalized.iloc[0]["updated_at"] == "2026-06-30"
    assert stats["duplicate_symbols"] == 1
    assert stats["blank_symbols"] == 1


def test_audit_sector_mapping_counts_unknown_as_missing() -> None:
    features = _sample_features()
    sector_map = pd.DataFrame(
        [
            {"symbol": "AAA", "sector": "Banking", "industry": "Commercial Banks", "exchange": "HOSE", "source": "test", "updated_at": "2026-06-30"},
            {"symbol": "BBB", "sector": "UNKNOWN", "industry": None, "exchange": "HOSE", "source": "test", "updated_at": "2026-06-30"},
        ]
    )

    summary, missing = audit_sector_mapping(features, sector_map=sector_map, sector_map_source="config/sector_map.csv")

    assert summary["total_symbols"] == 3
    assert summary["mapped_symbols"] == 1
    assert summary["missing_symbols"] == 2
    assert round(float(summary["mapping_coverage"]), 4) == round(1 / 3, 4)
    assert set(missing["symbol"]) == {"BBB", "CCC"}


def test_sector_map_large_caps_classified_correctly() -> None:
    """I2: Vingroup family must not be misclassified as Financial Services."""
    import csv
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "config/sector_map.csv"
    with open(path, encoding="utf-8") as f:
        rows = {r["symbol"]: r for r in csv.DictReader(f)}

    for sym in ("VIC", "VHM", "VRE"):
        assert rows[sym]["sector"] == "Real Estate", f"{sym} sector={rows[sym]['sector']}"

    core_30 = [
        "ACB", "BID", "CTG", "DGC", "FPT", "GAS", "GVR", "HDB", "HPG", "LPB",
        "MBB", "MSN", "MWG", "PLX", "SAB", "SHB", "SSB", "SSI", "STB", "TCB",
        "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE", "VPL",
    ]
    unknown = [s for s in core_30 if rows.get(s, {}).get("sector") in (None, "", "UNKNOWN")]
    assert not unknown, f"Core watchlist symbols with UNKNOWN sector: {unknown}"
