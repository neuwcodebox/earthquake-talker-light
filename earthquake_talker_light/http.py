from __future__ import annotations

from dataclasses import dataclass
from http.client import IncompleteRead
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class HttpResponse:
    body: bytes
    headers: dict[str, str]
    status: int

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class NotFoundError(Exception):
    def __init__(
        self,
        url: str | None = None,
        *,
        headers: dict[str, str] | None = None,
        status: int = 404,
    ) -> None:
        super().__init__(url or "HTTP request failed with status 404")
        self.url = url
        self.headers = headers or {}
        self.status = status


class HttpStatusError(Exception):
    def __init__(self, url: str, status: int):
        super().__init__(f"HTTP request failed with status {status}: {url}")
        self.url = url
        self.status = status


class TransientHttpError(Exception):
    def __init__(self, url: str, reason: str):
        super().__init__(f"Transient HTTP request failure: {reason}: {url}")
        self.url = url
        self.reason = reason


def fetch_bytes(url: str, timeout: float = 15.0) -> HttpResponse:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            if status != 200:
                if status == 404:
                    headers = {key: value for key, value in response.headers.items()}
                    raise NotFoundError(url, headers=headers, status=status)
                raise HttpStatusError(url, status)
            headers = {key: value for key, value in response.headers.items()}
            return HttpResponse(body=response.read(), headers=headers, status=status)
    except HTTPError as error:
        if error.code == 404:
            headers = {key: value for key, value in error.headers.items()}
            raise NotFoundError(url, headers=headers, status=error.code) from error
        raise
    except (TimeoutError, socket.timeout, IncompleteRead, URLError) as error:
        raise TransientHttpError(url, str(error)) from error
