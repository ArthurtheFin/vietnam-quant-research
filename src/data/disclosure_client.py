from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Discovered via ordinary browser network inspection of the exact page used in
# the ROUND 3 manual pilot (cafef.vn/du-lieu/lich-su-giao-dich/{exchange}/
# {symbol}-6.chn) -- this is the AJAX endpoint that page's own JS calls when its
# date-filter form is submitted. Not a hidden/undocumented system: same origin,
# same public feature, no auth, no reverse-engineering beyond reading the
# browser's own network panel for a page a human is already allowed to use.
BASE_URL = "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDCoDong.ashx"

USER_AGENT = (
    "VietnamQuantResearchBot/1.0 (+non-commercial research; "
    "single-threaded, >=2.5s between requests, backs off on 429/403; "
    "see docs/reports/data/docs/reports/data/DISCLOSURE_PIPELINE_DESIGN.md)"
)

DEFAULT_MIN_DELAY_SECONDS = 2.5


class DisclosureFetchError(RuntimeError):
    """Raised when a disclosure page cannot be fetched after retries."""


class DisclosureRateLimitedError(DisclosureFetchError):
    """Raised on repeated 429/403 -- caller should stop the whole crawl, not just this symbol."""


@dataclass
class DisclosureResponse:
    symbol: str
    url: str
    status_code: int
    text: str
    fetched_at: str  # ISO 8601 UTC


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DisclosurePoliteClient:
    """Polite client for CafeF's disclosure-history AJAX endpoint.

    Politeness is a hard constraint, not a config knob: a minimum delay
    between any two requests, single-threaded use only (no concurrency
    helper is provided), a clear identifying User-Agent, and backing off
    -- then giving up, never hammering -- on 429/403.
    """

    def __init__(
        self,
        min_delay_seconds: float = DEFAULT_MIN_DELAY_SECONDS,
        retry_count: int = 3,
        timeout_seconds: float = 15.0,
        session: requests.Session | None = None,
    ) -> None:
        if min_delay_seconds < 2.0:
            raise ValueError("min_delay_seconds must stay >= 2.0s -- politeness is a hard constraint")
        self.min_delay_seconds = min_delay_seconds
        self.retry_count = retry_count
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/plain, */*"})
        self._last_request_time: float = 0.0

    def _wait_for_pace(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_delay_seconds:
            time.sleep(self.min_delay_seconds - elapsed)

    def fetch(
        self,
        symbol: str,
        start_date: str = "",
        end_date: str = "",
        page_index: int = 1,
        page_size: int = 2000,
    ) -> DisclosureResponse:
        params = {
            "Symbol": symbol.upper(),
            "StartDate": start_date,
            "EndDate": end_date,
            "PageIndex": page_index,
            "PageSize": page_size,
        }
        last_exc: Exception | None = None
        for attempt in range(1, self.retry_count + 1):
            self._wait_for_pace()
            try:
                resp = self.session.get(BASE_URL, params=params, timeout=self.timeout_seconds)
                self._last_request_time = time.time()
            except requests.RequestException as exc:
                self._last_request_time = time.time()
                last_exc = exc
                if attempt < self.retry_count:
                    delay = self.min_delay_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        "Disclosure fetch %s failed (attempt %s/%s): %s; retrying in %.1fs",
                        symbol, attempt, self.retry_count, exc, delay,
                    )
                    time.sleep(delay)
                    continue
                logger.error("Disclosure fetch %s failed after %s attempts: %s", symbol, self.retry_count, exc)
                raise DisclosureFetchError(f"{symbol}: network failure after {self.retry_count} attempts") from exc

            if resp.status_code in (429, 403):
                delay = self.min_delay_seconds * (2 ** attempt)
                logger.warning(
                    "Disclosure fetch %s got HTTP %s (attempt %s/%s); backing off %.1fs",
                    symbol, resp.status_code, attempt, self.retry_count, delay,
                )
                if attempt >= self.retry_count:
                    raise DisclosureRateLimitedError(
                        f"{symbol}: repeated HTTP {resp.status_code} -- stopping rather than hammering the server"
                    )
                time.sleep(delay)
                continue

            resp.raise_for_status()
            return DisclosureResponse(
                symbol=symbol.upper(),
                url=resp.url,
                status_code=resp.status_code,
                text=resp.text,
                fetched_at=_utc_now_iso(),
            )

        raise DisclosureFetchError(f"{symbol}: failed after {self.retry_count} attempts") from last_exc
