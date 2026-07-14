from __future__ import annotations

import pandas as pd
import pytest

from src.data.disclosure_ingest import (
    ingest_events,
    ingest_new_events_live,
    load_universe_symbols,
    read_errors,
    read_events,
)
from src.data.disclosure_parser import DISCLOSURE_EVENTS_COLUMNS


def _base_row(**overrides) -> dict:
    row = {col: None for col in DISCLOSURE_EVENTS_COLUMNS}
    row.update({
        "symbol": "HPG",
        "event_type": "insider_registration",
        "person_name": "Trần Vũ Minh",
        "person_name_raw": "Trần Vũ Minh",
        "person_role": "Con",
        "related_person_name": "Trần Đình Long",
        "related_person_role": "Chủ tịch HĐQT",
        "direction": "buy",
        "shares_before": 100,
        "shares_registered_or_changed": 50,
        "shares_after": None,
        "pct_after": 1.0,
        "registration_window_start": pd.Timestamp("2026-03-12"),
        "registration_window_end": pd.Timestamp("2026-04-10"),
        "execution_date": None,
        "disclosure_date": pd.Timestamp("2026-03-11"),
        "disclosure_date_is_estimated": False,
        "source": "cafef",
        "source_ref": "https://cafef.vn/fake",
        "holder_code": "LQ_1",
        "transaction_note": "",
        "link_key": "HPG|Trần Vũ Minh|2026-03-12",
        "is_backfilled": True,
        "ingested_at": pd.Timestamp("2026-07-12"),
    })
    row.update(overrides)
    return row


def _universe_dir(tmp_path, symbols):
    d = tmp_path / "universe"
    d.mkdir()
    for sym in symbols:
        pd.DataFrame({"a": [1]}).to_parquet(d / f"{sym}.parquet")
    return d


def test_valid_row_ingested_with_backfill_available_at(tmp_path) -> None:
    df = pd.DataFrame([_base_row()])
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    result = ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    assert result == {"n_valid": 1, "n_rejected": 0, "n_unknown_symbol": 0}

    events = read_events(events_path)
    assert len(events) == 1
    # is_backfilled=True -> available_at = disclosure_date + 1 trading day
    # 2026-03-11 is a Wednesday -> next trading day is Thursday 2026-03-12
    assert events.iloc[0]["available_at"] == pd.Timestamp("2026-03-12")
    assert events.iloc[0]["unknown_symbol"] == False


def test_live_row_available_at_is_max_of_disclosure_and_ingested(tmp_path) -> None:
    row = _base_row(
        is_backfilled=False,
        disclosure_date=pd.Timestamp("2026-03-11"),
        ingested_at=pd.Timestamp("2026-03-15"),  # pipeline captured it late
    )
    df = pd.DataFrame([row])
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    events = read_events(events_path)
    # max(disclosure_date, ingested_at) -- the LATER of the two, not the earlier
    assert events.iloc[0]["available_at"] == pd.Timestamp("2026-03-15")


def test_unknown_symbol_is_flagged_not_rejected(tmp_path) -> None:
    df = pd.DataFrame([_base_row(symbol="ZZZNOTREAL")])
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])  # ZZZNOTREAL not in universe

    result = ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    assert result["n_valid"] == 1
    assert result["n_rejected"] == 0
    assert result["n_unknown_symbol"] == 1
    events = read_events(events_path)
    assert events.iloc[0]["unknown_symbol"] == True


def test_negative_quantity_rejected_to_error_table(tmp_path) -> None:
    df = pd.DataFrame([_base_row(shares_registered_or_changed=-5)])
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    result = ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    assert result["n_valid"] == 0
    assert result["n_rejected"] == 1
    errors = read_errors(errors_path)
    assert "NEGATIVE_QUANTITY" in errors.iloc[0]["reject_reason"]
    assert read_events(events_path).empty


def test_inverted_registration_window_rejected(tmp_path) -> None:
    df = pd.DataFrame([_base_row(
        registration_window_start=pd.Timestamp("2026-05-01"),
        registration_window_end=pd.Timestamp("2026-04-01"),  # end before start
    )])
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    result = ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    assert result["n_rejected"] == 1
    errors = read_errors(errors_path)
    assert "INVERTED_REGISTRATION_WINDOW" in errors.iloc[0]["reject_reason"]


def test_execution_before_registration_start_rejected(tmp_path) -> None:
    df = pd.DataFrame([_base_row(
        registration_window_start=pd.Timestamp("2026-05-01"),
        registration_window_end=pd.Timestamp("2026-06-01"),
        execution_date=pd.Timestamp("2026-04-01"),  # executed before registration even opened
    )])
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    result = ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    assert result["n_rejected"] == 1
    errors = read_errors(errors_path)
    assert "EXECUTION_BEFORE_REGISTRATION_START" in errors.iloc[0]["reject_reason"]


def test_natural_key_prevents_duplicate_rows_on_reingest(tmp_path) -> None:
    df = pd.DataFrame([_base_row()])
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)  # re-ingest same row

    events = read_events(events_path)
    assert len(events) == 1  # natural key (symbol, event_type, person_name, disclosure_date) de-dupes


def test_widened_key_keeps_two_distinct_same_day_disclosures(tmp_path) -> None:
    """DISCLOSURE_BASELINE.md caveat #1: a person making two genuinely
    distinct disclosures (different direction/volume) on the same calendar
    date must not collapse into one row under the old 4-field key."""
    df = pd.DataFrame([
        _base_row(direction="buy", shares_registered_or_changed=50),
        _base_row(direction="sell", shares_registered_or_changed=200),
    ])
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)

    events = read_events(events_path)
    assert len(events) == 2
    assert set(events["direction"]) == {"buy", "sell"}


def test_dedup_seq_keeps_two_identical_looking_registrations_same_day(tmp_path) -> None:
    """The remaining collision class after widening: two distinct
    registration windows, same symbol/person/date/direction/volume (e.g.
    the real Vuong Ngoc Yen/ACE case in DISCLOSURE_BASELINE.md) -- only
    dedup_seq (row-order tiebreaker) can tell these apart."""
    df = pd.DataFrame([
        _base_row(registration_window_start=pd.Timestamp("2011-02-14"), registration_window_end=pd.Timestamp("2011-04-14")),
        _base_row(registration_window_start=pd.Timestamp("2011-04-21"), registration_window_end=pd.Timestamp("2011-06-17")),
    ])
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)

    events = read_events(events_path)
    assert len(events) == 2
    assert set(events["registration_window_start"]) == {pd.Timestamp("2011-02-14"), pd.Timestamp("2011-04-21")}
    assert sorted(events["dedup_seq"]) == [0, 1]


def test_reingest_of_identical_batch_still_dedupes_with_dedup_seq(tmp_path) -> None:
    """The natural key must still prevent duplication on exact re-ingest,
    even with dedup_seq added -- re-running the same two-row batch twice
    must not double the row count."""
    df = pd.DataFrame([
        _base_row(registration_window_start=pd.Timestamp("2011-02-14")),
        _base_row(registration_window_start=pd.Timestamp("2011-04-21")),
    ])
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    ingest_events(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)

    events = read_events(events_path)
    assert len(events) == 2


def test_empty_input_is_a_no_op(tmp_path) -> None:
    df = pd.DataFrame(columns=DISCLOSURE_EVENTS_COLUMNS)
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    result = ingest_events(df, events_path=events_path, errors_path=errors_path)
    assert result == {"n_valid": 0, "n_rejected": 0, "n_unknown_symbol": 0}
    assert not events_path.exists()


# --- ingest_new_events_live (incremental / daily-update path) -------------


def test_live_ingest_first_run_treats_everything_as_new(tmp_path) -> None:
    df = pd.DataFrame([_base_row(is_backfilled=True)])  # incoming rows may say anything -- forced to False
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    result = ingest_new_events_live(df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    assert result == {"n_new_valid": 1, "n_new_rejected": 0, "n_new_unknown_symbol": 0}

    events = read_events(events_path)
    assert len(events) == 1
    assert events.iloc[0]["is_backfilled"] == False
    # live rule: available_at = max(disclosure_date, ingested_at)
    assert events.iloc[0]["available_at"] == events.iloc[0]["ingested_at"]


def test_live_ingest_skips_already_known_rows(tmp_path) -> None:
    row = _base_row()
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    # Original bulk backfill already put this row in with is_backfilled=True.
    ingest_events(pd.DataFrame([row]), events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)

    # A daily run re-parses the symbol's full history and sees the same row again.
    result = ingest_new_events_live(
        pd.DataFrame([row]), events_path=events_path, errors_path=errors_path, universe_dir=universe_dir
    )
    assert result == {"n_new_valid": 0, "n_new_rejected": 0, "n_new_unknown_symbol": 0}

    events = read_events(events_path)
    assert len(events) == 1
    # untouched -- still backfilled, not silently flipped to live
    assert events.iloc[0]["is_backfilled"] == True


def test_live_ingest_only_new_rows_get_live_treatment(tmp_path) -> None:
    old_row = _base_row()
    new_row = _base_row(
        person_name="Ai Đó Khác",
        disclosure_date=pd.Timestamp("2026-07-11"),
        link_key="HPG|Ai Đó Khác|2026-07-10",
    )
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    ingest_events(pd.DataFrame([old_row]), events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    result = ingest_new_events_live(
        pd.DataFrame([old_row, new_row]), events_path=events_path, errors_path=errors_path, universe_dir=universe_dir
    )
    assert result["n_new_valid"] == 1

    events = read_events(events_path)
    assert len(events) == 2
    old = events[events["person_name"] == "Trần Vũ Minh"].iloc[0]
    new = events[events["person_name"] == "Ai Đó Khác"].iloc[0]
    assert old["is_backfilled"] == True
    assert new["is_backfilled"] == False


def test_live_ingest_does_not_readmit_previously_rejected_row(tmp_path) -> None:
    bad_row = _base_row(shares_registered_or_changed=-5)  # will be rejected
    events_path = tmp_path / "events.parquet"
    errors_path = tmp_path / "errors.parquet"
    universe_dir = _universe_dir(tmp_path, ["HPG"])

    ingest_events(pd.DataFrame([bad_row]), events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    assert len(read_errors(errors_path)) == 1

    # Same bad row reappears in a later daily parse -- must not be re-admitted.
    result = ingest_new_events_live(
        pd.DataFrame([bad_row]), events_path=events_path, errors_path=errors_path, universe_dir=universe_dir
    )
    assert result == {"n_new_valid": 0, "n_new_rejected": 0, "n_new_unknown_symbol": 0}
    assert len(read_errors(errors_path)) == 1  # still just the one, not duplicated


def test_live_ingest_empty_input_is_a_no_op(tmp_path) -> None:
    df = pd.DataFrame(columns=DISCLOSURE_EVENTS_COLUMNS)
    result = ingest_new_events_live(df, events_path=tmp_path / "e.parquet", errors_path=tmp_path / "r.parquet")
    assert result == {"n_new_valid": 0, "n_new_rejected": 0, "n_new_unknown_symbol": 0}
