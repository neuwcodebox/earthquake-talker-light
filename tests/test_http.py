from __future__ import annotations

from http.client import IncompleteRead

import pytest

from earthquake_talker_light import http
from earthquake_talker_light.http import HttpStatusError, TransientHttpError, fetch_bytes


class _FakeResponse:
    def __init__(self, status: int, body: bytes = b"payload") -> None:
        self.status = status
        self.headers = {"Content-Type": "application/octet-stream"}
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return self._body


class _IncompleteReadResponse(_FakeResponse):
    def read(self) -> bytes:
        raise IncompleteRead(b"", 138)


def test_fetch_bytes_accepts_http_200_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http, "urlopen", lambda _request, timeout: _FakeResponse(200))

    response = fetch_bytes("https://example.test/binary", timeout=1)

    assert response.status == 200
    assert response.body == b"payload"


def test_fetch_bytes_rejects_non_ok_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http, "urlopen", lambda _request, timeout: _FakeResponse(204, b""))

    with pytest.raises(HttpStatusError):
        fetch_bytes("https://example.test/binary", timeout=1)


def test_fetch_bytes_wraps_timeout_as_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_timeout(_request: object, timeout: float) -> None:
        raise TimeoutError("read operation timed out")

    monkeypatch.setattr(http, "urlopen", raise_timeout)

    with pytest.raises(TransientHttpError):
        fetch_bytes("https://example.test/binary", timeout=1)


def test_fetch_bytes_wraps_incomplete_read_as_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http, "urlopen", lambda _request, timeout: _IncompleteReadResponse(200))

    with pytest.raises(TransientHttpError):
        fetch_bytes("https://example.test/binary", timeout=1)
