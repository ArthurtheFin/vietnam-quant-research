from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterator, Tuple, Union

DateLike = Union[str, date, datetime]


def to_datetime(value: DateLike) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        value = value.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass
    raise ValueError(f"Unsupported date value: {value!r}")


def to_ssi_date(value: DateLike) -> str:
    """Convert date to DD/MM/YYYY format required by FCData examples/spec."""
    return to_datetime(value).strftime("%d/%m/%Y")


def to_iso_date(value: DateLike) -> str:
    return to_datetime(value).strftime("%Y-%m-%d")


def chunk_date_range(start: DateLike, end: DateLike, chunk_days: int = 30) -> Iterator[Tuple[str, str]]:
    """Yield inclusive date chunks as DD/MM/YYYY strings.

    FCData DailyOhlc is documented with a 30-day max range, so this helper
    is used by the client wrapper to fetch long histories safely.
    """
    current = to_datetime(start)
    end_dt = to_datetime(end)
    if current > end_dt:
        raise ValueError("start must be <= end")
    while current <= end_dt:
        chunk_end = min(current + timedelta(days=chunk_days - 1), end_dt)
        yield to_ssi_date(current), to_ssi_date(chunk_end)
        current = chunk_end + timedelta(days=1)
