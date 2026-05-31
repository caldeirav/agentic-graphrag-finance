"""Unit tests for EDGAR HTTP retry helpers."""

import httpx
import pytest

from ingestion.edgar_http import with_edgar_retry


def test_with_edgar_retry_recovers_from_remote_protocol_error(monkeypatch):
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        return "ok"

    monkeypatch.setattr("ingestion.edgar_http.time.sleep", lambda _: None)
    assert with_edgar_retry(flaky, max_attempts=5) == "ok"
    assert calls["n"] == 3


def test_with_edgar_retry_does_not_retry_client_errors(monkeypatch):
    def bad_request() -> None:
        request = httpx.Request("GET", "https://www.sec.gov/example")
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("not found", request=request, response=response)

    monkeypatch.setattr("ingestion.edgar_http.time.sleep", lambda _: None)
    with pytest.raises(httpx.HTTPStatusError):
        with_edgar_retry(bad_request, max_attempts=5)
