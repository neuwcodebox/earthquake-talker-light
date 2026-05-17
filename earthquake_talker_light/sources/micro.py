from __future__ import annotations

from html.parser import HTMLParser
import html
import re
from typing import Callable

from earthquake_talker_light.http import fetch_bytes
from earthquake_talker_light.message import Message, Priority

MICRO_ENDPOINT = "https://www.weather.go.kr/w/wnuri-eqk-vol/eqk/eqk-micro.do"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data)


def html_to_text(source: str) -> str:
    parser = _TextExtractor()
    parser.feed(source)
    text = html.unescape(" ".join(parser.parts))
    return re.sub(r"\s+", " ", text).strip()


class KmaMicroSource:
    name = "micro"

    def __init__(
        self,
        *,
        interval_seconds: float = 10.0,
        timeout: float = 15.0,
        fetcher: Callable[[str, float], str] | None = None,
    ) -> None:
        self.latest_text: str | None = None
        self.initialized = False
        self.interval_seconds = interval_seconds
        self.timeout = timeout
        self.fetcher = fetcher or self._fetch

    def poll(self) -> list[Message]:
        raw_html = self.fetcher(MICRO_ENDPOINT, self.timeout)
        text = html_to_text(raw_html)
        if "지진" not in text and "여진" not in text:
            return []

        if self.latest_text == text:
            return []

        self.latest_text = text
        if not self.initialized:
            self.initialized = True
            return []

        return [
            Message(
                sender="기상청 미소지진 안내",
                text=text,
                level=Priority.NORMAL,
            )
        ]

    @staticmethod
    def _fetch(url: str, timeout: float) -> str:
        return fetch_bytes(url, timeout=timeout).text
