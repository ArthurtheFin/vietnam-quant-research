from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

from src.validation.freshness_check import load_market_holidays
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DOTNET_DATE_RE = re.compile(r"/Date\((-?\d+)\)/")
_ANCHOR_HREF_RE = re.compile(r"href=['\"]([^'\"]+)['\"]")

DISCLOSURE_EVENTS_COLUMNS = [
    "symbol",
    "event_type",
    "person_name",
    "person_name_raw",
    "person_role",
    "related_person_name",
    "related_person_role",
    "direction",
    "shares_before",
    "shares_registered_or_changed",
    "shares_after",
    "pct_after",
    "registration_window_start",
    "registration_window_end",
    "execution_date",
    "disclosure_date",
    "disclosure_date_is_estimated",
    "source",
    "source_ref",
    "holder_code",
    "transaction_note",
    "link_key",
    "is_backfilled",
    "ingested_at",
    "available_at",
    "raw_payload",
]


_ICT_OFFSET = pd.Timedelta(hours=7)


def parse_dotnet_date(value: Any) -> pd.Timestamp | None:
    """Parse ASP.NET AJAX's '/Date(1626022800000)/' epoch-ms wire format.

    The raw epoch values are Vietnam-local (ICT, UTC+7) calendar dates
    serialized as UTC midnight minus 7 hours (e.g. plan/registration/execution
    dates all land on ...17:00:00 the *previous* day when read as naive UTC).
    Confirmed against 5 independently-known 2020-2021 disclosure events during
    ROUND 4 cross-validation: without the +7h shift, every date parsed one
    calendar day earlier than the real disclosure date. Shifting first, then
    treating the result as the naive local calendar timestamp, fixes this.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return pd.to_datetime(value, unit="ms") + _ICT_OFFSET
    match = _DOTNET_DATE_RE.match(str(value))
    if not match:
        return None
    return pd.to_datetime(int(match.group(1)), unit="ms") + _ICT_OFFSET


def _normalize_person_name(raw: str) -> str:
    return unicodedata.normalize("NFC", raw).strip()


def _extract_source_url(url_field: str) -> str | None:
    if not url_field:
        return None
    match = _ANCHOR_HREF_RE.search(url_field)
    if match:
        return match.group(1)
    return None


def _direction(buy: float, sell: float) -> str | None:
    buy = buy or 0
    sell = sell or 0
    if buy and sell:
        return "buy"  # shouldn't happen in practice; buy takes precedence, flagged via raw_payload for review
    if buy:
        return "buy"
    if sell:
        return "sell"
    return None


def next_trading_day(ts: pd.Timestamp, holidays: set | None = None) -> pd.Timestamp:
    """First trading session strictly after `ts` (weekends + config/vn_market_holidays.csv),
    matching the same weekend/holiday-skip convention as
    src.validation.freshness_check.expected_latest_trading_date, just run forward
    instead of backward. Used for the ROUND 3 backfill placeholder:
    available_at = disclosure_date + 1 trading day."""
    holidays = holidays if holidays is not None else load_market_holidays()
    candidate = pd.Timestamp(ts).normalize() + pd.Timedelta(days=1)
    while candidate.weekday() >= 5 or candidate.date() in holidays:
        candidate += pd.Timedelta(days=1)
    return candidate


def _classify_and_expand(record: dict[str, Any], symbol: str, source_ref: str, fetched_at: pd.Timestamp) -> list[dict[str, Any]]:
    """One CafeF record can carry a registration phase, a result phase, both, or
    (for funds/organizations with no stated board position) neither in the
    insider sense -- emit 0-2 disclosure_events rows per record.

    v1 heuristic (flagged in docs/reports/data/docs/reports/data/DISCLOSURE_PIPELINE_DESIGN.md Round 4 as a parse
    simplification, not re-litigated here): a record counts as an "insider"
    disclosure if TransactionManPosition or RelatedManPosition is non-empty
    (a stated board/management position); otherwise it's treated as a plain
    major-shareholder disclosure (funds, holding companies) regardless of
    registration/result phase.
    """
    person_raw = str(record.get("TransactionMan") or "")
    person = _normalize_person_name(person_raw)
    person_role = str(record.get("TransactionManPosition") or "").strip()
    related_person = _normalize_person_name(str(record.get("RelatedMan") or ""))
    related_role = str(record.get("RelatedManPosition") or "").strip()
    is_insider = bool(person_role) or bool(related_role)

    shares_before = record.get("VolumeBeforeTransaction")
    shares_after = record.get("VolumeAfterTransaction")
    pct_after = record.get("TyLeSoHuu")
    holder_code = record.get("ShareHolderCode")
    note = str(record.get("TransactionNote") or "").strip()

    plan_start = parse_dotnet_date(record.get("PlanBeginDate"))
    plan_end = parse_dotnet_date(record.get("PlanEndDate"))
    exec_date = parse_dotnet_date(record.get("RealEndDate"))
    published = parse_dotnet_date(record.get("PublishedDate"))

    plan_buy = record.get("PlanBuyVolume") or 0
    plan_sell = record.get("PlanSellVolume") or 0
    real_buy = record.get("RealBuyVolume") or 0
    real_sell = record.get("RealSellVolume") or 0

    has_registration = bool(plan_buy or plan_sell or plan_start is not None)
    has_result = bool(real_buy or real_sell or exec_date is not None)

    disclosure_date = published
    disclosure_estimated = False
    if disclosure_date is None:
        disclosure_date = plan_start or exec_date
        disclosure_estimated = True

    link_key = f"{symbol}|{person}|{plan_start.date().isoformat() if plan_start is not None else 'NA'}"

    base = {
        "symbol": symbol,
        "person_name": person,
        "person_name_raw": person_raw,
        "person_role": person_role,
        "related_person_name": related_person,
        "related_person_role": related_role,
        "shares_before": shares_before,
        "shares_after": shares_after,
        "pct_after": pct_after,
        "registration_window_start": plan_start,
        "registration_window_end": plan_end,
        "execution_date": exec_date,
        "disclosure_date": disclosure_date,
        "disclosure_date_is_estimated": disclosure_estimated,
        "source": "cafef",
        "source_ref": source_ref,
        "holder_code": holder_code,
        "transaction_note": note,
        "link_key": link_key,
        "ingested_at": fetched_at,
        # v1 crawler only ever does bulk historical fetch (crawl_symbol requests
        # a symbol's full history in one go) -- there is no live/incremental
        # accumulation mode yet, so every row from this parser is backfilled by
        # definition. A future live-accumulation crawl would set this False and
        # let ingest's max(disclosure_date, ingested_at) rule apply instead.
        "is_backfilled": True,
        "raw_payload": json.dumps(record, ensure_ascii=False),
    }

    rows: list[dict[str, Any]] = []
    if has_registration:
        rows.append({
            **base,
            "event_type": "insider_registration" if is_insider else "major_shareholder_change",
            "direction": _direction(plan_buy, plan_sell),
            "shares_registered_or_changed": plan_buy or plan_sell or None,
        })
    if has_result:
        rows.append({
            **base,
            "event_type": "insider_result" if is_insider else "major_shareholder_change",
            "direction": _direction(real_buy, real_sell),
            "shares_registered_or_changed": real_buy or real_sell or None,
        })
    if not rows:
        # Defensive fallback: a record with neither phase populated shouldn't
        # occur given the source's own semantics, but don't silently drop data
        # if it does -- surface it as a low-confidence major_shareholder_change
        # row rather than losing the raw information.
        rows.append({
            **base,
            "event_type": "major_shareholder_change",
            "direction": None,
            "shares_registered_or_changed": None,
        })
    return rows


def parse_raw_page(path: Path) -> pd.DataFrame:
    """Parse one raw crawler-tier JSON file (as written by
    src.data.disclosure_crawler.crawl_symbol) into disclosure_events rows.
    Purely a function of the immutable raw file -- safe to re-run any time
    parse logic changes, never touches the raw tier."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    symbol = payload["symbol"]
    fetched_at = pd.Timestamp(payload["fetched_at"]).tz_localize(None)
    envelope = json.loads(payload["raw_response"])
    records = (envelope.get("Data") or {}).get("Data") or []

    rows: list[dict[str, Any]] = []
    for record in records:
        source_ref = _extract_source_url(str(record.get("Url") or "")) or payload["url"]
        rows.extend(_classify_and_expand(record, symbol, source_ref, fetched_at))

    if not rows:
        return pd.DataFrame(columns=DISCLOSURE_EVENTS_COLUMNS)
    df = pd.DataFrame(rows)
    for col in DISCLOSURE_EVENTS_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[DISCLOSURE_EVENTS_COLUMNS]


def parse_raw_symbol_dir(symbol_dir: Path) -> pd.DataFrame:
    """Parse every raw page file for one symbol and de-duplicate by
    (event_type, person_name, disclosure_date, link_key) -- multiple crawl
    runs of the same historical page produce identical rows; keep the most
    recently fetched copy."""
    frames = [parse_raw_page(p) for p in sorted(symbol_dir.glob("*.json"))]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=DISCLOSURE_EVENTS_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("ingested_at").drop_duplicates(
        subset=["event_type", "person_name", "disclosure_date", "link_key"], keep="last"
    )
    return combined.reset_index(drop=True)


def parse_raw_root(raw_dir: Path) -> pd.DataFrame:
    """Parse every symbol subdirectory under the raw tier root."""
    frames = [parse_raw_symbol_dir(d) for d in sorted(raw_dir.iterdir()) if d.is_dir()]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=DISCLOSURE_EVENTS_COLUMNS)
    return pd.concat(frames, ignore_index=True).reset_index(drop=True)
