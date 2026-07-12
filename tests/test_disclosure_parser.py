from __future__ import annotations

import json

import pandas as pd

from src.data.disclosure_parser import (
    next_trading_day,
    parse_dotnet_date,
    parse_raw_page,
    parse_raw_symbol_dir,
)


def test_parse_dotnet_date_epoch_ms() -> None:
    ts = parse_dotnet_date("/Date(1626022800000)/")
    assert ts == pd.Timestamp("2021-07-11 17:00:00")


def test_parse_dotnet_date_null_is_none() -> None:
    assert parse_dotnet_date(None) is None


def test_next_trading_day_skips_weekend() -> None:
    # 2026-07-10 is a Friday
    friday = pd.Timestamp("2026-07-10")
    assert next_trading_day(friday, holidays=set()) == pd.Timestamp("2026-07-13")  # Monday


def test_next_trading_day_skips_configured_holiday() -> None:
    thursday = pd.Timestamp("2026-07-09")
    friday = pd.Timestamp("2026-07-10").date()
    assert next_trading_day(thursday, holidays={friday}) == pd.Timestamp("2026-07-13")


def _write_raw_page(tmp_path, symbol: str, records: list[dict], fetched_at: str = "2026-07-12T03:00:00+00:00"):
    symbol_dir = tmp_path / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": symbol,
        "url": f"https://cafef.vn/fake?Symbol={symbol}",
        "fetched_at": fetched_at,
        "page_index": 1,
        "page_size": 2000,
        "status_code": 200,
        "raw_response": json.dumps({"Data": {"TotalCount": len(records), "Data": records}}),
    }
    path = symbol_dir / "page01_fake.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return symbol_dir


def test_registration_and_result_expand_to_two_rows(tmp_path) -> None:
    # Modeled on the real HPG/Trần Vũ Minh record found during the pilot.
    record = {
        "Stock": "HPG",
        "TransactionMan": "Trần Vũ Minh",
        "TransactionManPosition": "Con",
        "RelatedManPosition": "Chủ tịch HĐQT",
        "RelatedMan": "Trần Đình Long",
        "VolumeBeforeTransaction": 176391996,
        "PlanBuyVolume": 50000000,
        "PlanSellVolume": 0,
        "PlanBeginDate": "/Date(1773248400000)/",
        "PlanEndDate": "/Date(1775754000000)/",
        "RealBuyVolume": 33291904,
        "RealSellVolume": 0,
        "RealEndDate": "/Date(1775667600000)/",
        "PublishedDate": "/Date(1773853200000)/",
        "VolumeAfterTransaction": 209683900,
        "TransactionNote": "",
        "TyLeSoHuu": 2.4835340655914542,
        "ShareHolderCode": "LQ_81519",
        "OrderDate": "/Date(1773248400000)/",
        "Url": "Trần Vũ Minh",
    }
    symbol_dir = _write_raw_page(tmp_path, "HPG", [record])
    df = parse_raw_symbol_dir(symbol_dir)

    assert len(df) == 2
    assert set(df["event_type"]) == {"insider_registration", "insider_result"}

    reg = df[df["event_type"] == "insider_registration"].iloc[0]
    assert reg["person_name"] == "Trần Vũ Minh"
    assert reg["direction"] == "buy"
    assert reg["shares_registered_or_changed"] == 50000000
    assert reg["disclosure_date_is_estimated"] == False  # PublishedDate is real

    res = df[df["event_type"] == "insider_result"].iloc[0]
    assert res["shares_registered_or_changed"] == 33291904
    # Both rows share disclosure_date (only one PublishedDate per raw record)
    assert reg["disclosure_date"] == res["disclosure_date"]
    # But natural key differs by event_type, so both survive independently
    assert reg["link_key"] == res["link_key"]


def test_fund_without_position_classified_as_major_shareholder_change(tmp_path) -> None:
    # Modeled on the real "CTBC Vietnam Equity Fund" record -- no board
    # position, result-only (no pre-registration).
    record = {
        "Stock": "HPG",
        "TransactionMan": "CTBC Vietnam Equity Fund",
        "TransactionManPosition": "",
        "RelatedManPosition": "",
        "RelatedMan": "",
        "VolumeBeforeTransaction": 12085000,
        "PlanBuyVolume": 0,
        "PlanSellVolume": 0,
        "PlanBeginDate": None,
        "PlanEndDate": None,
        "RealBuyVolume": 633000,
        "RealSellVolume": 0,
        "RealEndDate": "/Date(1608829200000)/",
        "PublishedDate": "/Date(1608915600000)/",
        "VolumeAfterTransaction": 12718000,
        "TransactionNote": "",
        "TyLeSoHuu": 0.15063429403112072,
        "ShareHolderCode": "CORP_81758",
        "OrderDate": "/Date(1608829200000)/",
        "Url": "CTBC Vietnam Equity Fund",
    }
    symbol_dir = _write_raw_page(tmp_path, "HPG", [record])
    df = parse_raw_symbol_dir(symbol_dir)
    assert len(df) == 1
    assert df.iloc[0]["event_type"] == "major_shareholder_change"
    assert df.iloc[0]["direction"] == "buy"


def test_anchor_html_extracted_as_source_ref(tmp_path) -> None:
    record = {
        "Stock": "HPG",
        "TransactionMan": "Nguyễn Ngọc Quang",
        "TransactionManPosition": "Thành viên HĐQT",
        "RelatedManPosition": "",
        "RelatedMan": "",
        "VolumeBeforeTransaction": 125485714,
        "PlanBuyVolume": 0,
        "PlanSellVolume": 6600000,
        "PlanBeginDate": "/Date(1781110800000)/",
        "PlanEndDate": "/Date(1783616400000)/",
        "RealBuyVolume": 0,
        "RealSellVolume": 0,
        "RealEndDate": None,
        "PublishedDate": "/Date(1782284414940)/",
        "VolumeAfterTransaction": 0,
        "TransactionNote": "",
        "TyLeSoHuu": 0,
        "ShareHolderCode": "CEO_06749",
        "OrderDate": "/Date(1781110800000)/",
        "Url": "<a href='/du-lieu/ceo/CEO_06749/nguyen-ngoc-quang.chn'>Nguyễn Ngọc Quang</a>",
    }
    symbol_dir = _write_raw_page(tmp_path, "HPG", [record])
    df = parse_raw_symbol_dir(symbol_dir)
    assert len(df) == 1  # registration only, no result yet
    assert df.iloc[0]["source_ref"] == "/du-lieu/ceo/CEO_06749/nguyen-ngoc-quang.chn"


def test_parse_raw_symbol_dir_dedupes_across_multiple_crawl_runs(tmp_path) -> None:
    record = {
        "Stock": "HPG", "TransactionMan": "A", "TransactionManPosition": "CEO",
        "RelatedManPosition": "", "RelatedMan": "", "VolumeBeforeTransaction": 100,
        "PlanBuyVolume": 10, "PlanSellVolume": 0,
        "PlanBeginDate": "/Date(1600000000000)/", "PlanEndDate": "/Date(1600200000000)/",
        "RealBuyVolume": 0, "RealSellVolume": 0, "RealEndDate": None,
        "PublishedDate": "/Date(1600000000000)/", "VolumeAfterTransaction": 110,
        "TransactionNote": "", "TyLeSoHuu": 1.0, "ShareHolderCode": "X", "OrderDate": None, "Url": "A",
    }
    dir1 = _write_raw_page(tmp_path, "DUP", [record], fetched_at="2026-01-01T00:00:00+00:00")
    # Simulate a second crawl run of the same historical page (new fetched_at, identical content)
    payload2 = json.loads((dir1 / "page01_fake.json").read_text(encoding="utf-8"))
    payload2["fetched_at"] = "2026-02-01T00:00:00+00:00"
    (dir1 / "page01_rerun.json").write_text(json.dumps(payload2, ensure_ascii=False), encoding="utf-8")

    df = parse_raw_symbol_dir(dir1)
    assert len(df) == 1  # deduped, not doubled
    assert df.iloc[0]["ingested_at"] == pd.Timestamp("2026-02-01T00:00:00+00:00").tz_localize(None)
