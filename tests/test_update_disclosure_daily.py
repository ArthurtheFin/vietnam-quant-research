from __future__ import annotations

import json

import pandas as pd

from scripts.update_disclosure_daily import run_daily_update
from src.data.disclosure_client import DisclosureFetchError, DisclosureRateLimitedError
from src.data.disclosure_ingest import read_events


class _FakeClient:
    """Stands in for DisclosurePoliteClient -- returns canned JSON per symbol,
    no network calls, matching this repo's fake-client testing convention."""

    def __init__(self, responses: dict[str, str], raise_on: dict[str, Exception] | None = None):
        self._responses = responses
        self._raise_on = raise_on or {}
        self.calls: list[str] = []

    def fetch(self, symbol, start_date="", end_date="", page_index=1, page_size=2000):
        self.calls.append(symbol)
        if symbol in self._raise_on:
            raise self._raise_on[symbol]
        from src.data.disclosure_client import DisclosureResponse
        return DisclosureResponse(
            symbol=symbol, url=f"https://cafef.vn/fake?Symbol={symbol}", status_code=200,
            text=self._responses.get(symbol, '{"Data":{"TotalCount":0,"Data":[]}}'),
            fetched_at="2026-07-13T02:00:00+00:00",
        )


def _record(person="A", plan_buy=10, published_ms=1600000000000):
    return {
        "Stock": "X", "TransactionMan": person, "TransactionManPosition": "CEO",
        "RelatedManPosition": "", "RelatedMan": "", "VolumeBeforeTransaction": 100,
        "PlanBuyVolume": plan_buy, "PlanSellVolume": 0,
        "PlanBeginDate": f"/Date({published_ms})/", "PlanEndDate": f"/Date({published_ms + 2000000000})/",
        "RealBuyVolume": 0, "RealSellVolume": 0, "RealEndDate": None,
        "PublishedDate": f"/Date({published_ms})/", "VolumeAfterTransaction": 110,
        "TransactionNote": "", "TyLeSoHuu": 1.0, "ShareHolderCode": "X", "OrderDate": None, "Url": person,
    }


def _envelope(records):
    return json.dumps({"Data": {"TotalCount": len(records), "Data": records}})


def _universe_dir(tmp_path, symbols):
    d = tmp_path / "universe"
    d.mkdir()
    for sym in symbols:
        pd.DataFrame({"a": [1]}).to_parquet(d / f"{sym}.parquet")
    return d


def test_daily_update_ingests_new_rows_as_live(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    log_path = tmp_path / "log.jsonl"
    universe_dir = _universe_dir(tmp_path, ["HPG"])
    client = _FakeClient({"HPG": _envelope([_record("A")])})
    summary = run_daily_update(
        ["HPG"], client=client, raw_dir=raw_dir, events_path=events_path, errors_path=errors_path,
        universe_dir=universe_dir, log_path=log_path,
    )

    assert summary["n_new_valid"] == 1
    assert summary["n_fetch_errors"] == 0
    events = read_events(events_path)
    assert len(events) == 1
    assert events.iloc[0]["is_backfilled"] == False

    # log file has exactly one JSON line matching the summary
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    logged = json.loads(lines[0])
    assert logged["n_new_valid"] == 1


def test_daily_update_second_run_finds_no_new_rows(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    log_path = tmp_path / "log.jsonl"
    universe_dir = _universe_dir(tmp_path, ["HPG"])
    client = _FakeClient({"HPG": _envelope([_record("A")])})
    run_daily_update(["HPG"], client=client, raw_dir=raw_dir, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir, log_path=log_path)
    summary2 = run_daily_update(["HPG"], client=client, raw_dir=raw_dir, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir, log_path=log_path)

    assert summary2["n_new_valid"] == 0
    assert len(read_events(events_path)) == 1  # not duplicated
    assert len(log_path.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_daily_update_new_disclosure_appears_on_third_run(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    log_path = tmp_path / "log.jsonl"
    universe_dir = _universe_dir(tmp_path, ["HPG"])
    client = _FakeClient({"HPG": _envelope([_record("A")])})
    run_daily_update(["HPG"], client=client, raw_dir=raw_dir, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir, log_path=log_path)

    # A new person discloses today -- CafeF's feed now has 2 records
    client._responses["HPG"] = _envelope([_record("A"), _record("B", published_ms=1700000000000)])
    summary = run_daily_update(["HPG"], client=client, raw_dir=raw_dir, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir, log_path=log_path)

    assert summary["n_new_valid"] == 1
    events = read_events(events_path)
    assert len(events) == 2
    assert set(events["person_name"]) == {"A", "B"}
    new_row = events[events["person_name"] == "B"].iloc[0]
    assert new_row["is_backfilled"] == False


def test_daily_update_fetch_error_is_logged_and_skipped(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    log_path = tmp_path / "log.jsonl"
    universe_dir = _universe_dir(tmp_path, ["HPG", "MWG"])
    client = _FakeClient(
        {"MWG": _envelope([_record("C")])},
        raise_on={"HPG": DisclosureFetchError("HPG: network failure after 3 attempts")},
    )
    summary = run_daily_update(
        ["HPG", "MWG"], client=client, raw_dir=raw_dir, events_path=events_path, errors_path=errors_path,
        universe_dir=universe_dir, log_path=log_path,
    )

    assert summary["n_fetch_errors"] == 1
    assert summary["fetch_error_symbols"] == ["HPG"]
    assert summary["n_new_valid"] == 1  # MWG still went through
    events = read_events(events_path)
    assert list(events["symbol"]) == ["MWG"]


def test_daily_update_stops_on_rate_limit(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    log_path = tmp_path / "log.jsonl"
    universe_dir = _universe_dir(tmp_path, ["HPG", "MWG", "TCB"])
    client = _FakeClient(
        {"TCB": _envelope([_record("D")])},
        raise_on={"HPG": DisclosureRateLimitedError("HPG: repeated 429")},
    )
    summary = run_daily_update(
        ["HPG", "MWG", "TCB"], client=client, raw_dir=raw_dir, events_path=events_path, errors_path=errors_path,
        universe_dir=universe_dir, log_path=log_path,
    )

    assert summary["n_symbols_attempted"] == 3
    assert summary["fetch_error_symbols"] == ["HPG"]
    # stopped at HPG -- MWG/TCB never attempted
    assert "MWG" not in client.calls
    assert "TCB" not in client.calls
