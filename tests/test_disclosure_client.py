from __future__ import annotations

import pytest

import src.data.disclosure_client as disclosure_client
from src.data.disclosure_client import (
    DisclosureFetchError,
    DisclosurePoliteClient,
    DisclosureRateLimitedError,
)


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "{}", url: str = "https://cafef.vn/fake"):
        self.status_code = status_code
        self.text = text
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code not in (429, 403):
            raise disclosure_client.requests.HTTPError(f"HTTP {self.status_code}")


class _FakeSession:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        item = next(self._responses)
        if isinstance(item, Exception):
            raise item
        return item


def _client_with(monkeypatch, responses, min_delay_seconds: float = 2.5, retry_count: int = 3):
    session = _FakeSession(responses)
    client = DisclosurePoliteClient(min_delay_seconds=min_delay_seconds, retry_count=retry_count, session=session)
    sleeps: list[float] = []
    monkeypatch.setattr(disclosure_client.time, "sleep", lambda d: sleeps.append(round(d, 2)))
    # Make _wait_for_pace a no-op cost-wise but still exercised
    monkeypatch.setattr(disclosure_client.time, "time", lambda: 0.0)
    return client, session, sleeps


def test_min_delay_seconds_enforced_floor() -> None:
    with pytest.raises(ValueError, match="politeness"):
        DisclosurePoliteClient(min_delay_seconds=0.5)


def test_fetch_success_returns_response(monkeypatch) -> None:
    client, session, sleeps = _client_with(monkeypatch, [_FakeResponse(200, text='{"Data":{"TotalCount":0,"Data":[]}}')])
    resp = client.fetch("hpg")
    assert resp.symbol == "HPG"
    assert resp.status_code == 200
    assert '"TotalCount":0' in resp.text
    # Symbol is upper-cased in the request params
    _, params, _ = session.calls[0]
    assert params["Symbol"] == "HPG"


def test_fetch_retries_then_succeeds_on_transient_network_error(monkeypatch) -> None:
    client, session, sleeps = _client_with(
        monkeypatch,
        [disclosure_client.requests.ConnectionError("boom"), _FakeResponse(200, text="{}")],
    )
    resp = client.fetch("HPG")
    assert resp.status_code == 200
    assert len(session.calls) == 2
    assert sleeps  # backed off before retrying


def test_fetch_raises_after_exhausting_retries(monkeypatch) -> None:
    client, session, sleeps = _client_with(
        monkeypatch,
        [disclosure_client.requests.ConnectionError("boom")] * 3,
        retry_count=3,
    )
    with pytest.raises(DisclosureFetchError):
        client.fetch("HPG")
    assert len(session.calls) == 3


def test_repeated_429_raises_rate_limited_and_stops(monkeypatch) -> None:
    client, session, sleeps = _client_with(
        monkeypatch,
        [_FakeResponse(429), _FakeResponse(429), _FakeResponse(429)],
        retry_count=3,
    )
    with pytest.raises(DisclosureRateLimitedError, match="429"):
        client.fetch("HPG")
    assert len(session.calls) == 3
    # sleeps interleave the constant pre-request pace (2.5s) with the growing
    # post-429 backoff; the backoff component itself should strictly increase.
    backoff_sleeps = [s for s in sleeps if s != 2.5]
    assert backoff_sleeps == sorted(backoff_sleeps)
    # no sleep after the final attempt -- it raises immediately instead
    assert len(backoff_sleeps) == 2


def test_403_also_treated_as_rate_limit_backoff(monkeypatch) -> None:
    client, session, sleeps = _client_with(monkeypatch, [_FakeResponse(403), _FakeResponse(200, text="{}")])
    resp = client.fetch("HPG")
    assert resp.status_code == 200
    assert len(session.calls) == 2
