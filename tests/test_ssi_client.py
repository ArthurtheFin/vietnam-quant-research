from __future__ import annotations

import pytest

import src.data.ssi_client as ssi_client


def test_call_retries_with_exponential_backoff_on_rate_limit(monkeypatch) -> None:
    client = ssi_client.SSIDataClient.__new__(ssi_client.SSIDataClient)
    client.retry_count = 3
    client.retry_sleep = 1.5
    client.last_call_time = 0.0

    time_values = iter([10.0, 12.0, 15.0, 18.0, 21.0, 24.0, 27.0, 30.0])
    sleeps: list[float] = []
    attempts = {"count": 0}

    monkeypatch.setattr(ssi_client.time, "time", lambda: next(time_values))
    monkeypatch.setattr(ssi_client.time, "sleep", lambda delay: sleeps.append(round(delay, 2)))
    monkeypatch.setattr(ssi_client.logger, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(ssi_client.logger, "error", lambda *args, **kwargs: None)

    def fail():
        attempts["count"] += 1
        raise RuntimeError("429 API calls quota exceeded")

    with pytest.raises(ssi_client.SSIRateLimitError, match="rate limit"):
        client._call(fail)

    assert attempts["count"] == 3
    assert sleeps == [1.5, 3.0]
