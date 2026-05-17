from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; EarthquakeTalkerLight/0.1; "
    "+https://github.com/neurowhai/earthquake-talker-light)"
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
    pass


class HttpStatusError(Exception):
    def __init__(self, url: str, status: int):
        super().__init__(f"HTTP request failed with status {status}: {url}")
        self.url = url
        self.status = status


def fetch_bytes(url: str, timeout: float = 15.0) -> HttpResponse:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            if status != 200:
                if status == 404:
                    raise NotFoundError(url)
                raise HttpStatusError(url, status)
            headers = {key: value for key, value in response.headers.items()}
            return HttpResponse(body=response.read(), headers=headers, status=status)
    except HTTPError as error:
        if error.code == 404:
            raise NotFoundError(url) from error
        raise
