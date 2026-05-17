from __future__ import annotations

from typing import Protocol

from earthquake_talker_light.message import Message


class Source(Protocol):
    name: str
    interval_seconds: float

    def poll(self) -> list[Message]:
        ...
