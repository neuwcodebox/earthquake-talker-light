from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import IntEnum
from pathlib import Path
from uuid import uuid4

KST = timezone(timedelta(hours=9), "KST")


class Priority(IntEnum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass(frozen=True)
class Message:
    sender: str
    text: str
    level: Priority = Priority.NORMAL
    image_path: Path | None = None
    preview: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(KST))
    id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def disable_notification(self) -> bool:
        return self.level < Priority.HIGH

    def render_text(self) -> str:
        lines = [
            self.created_at.strftime("%H:%M:%S"),
            f"<< {self.sender} >>",
            f"## {self.level.name.title()} Level ##",
            self.text,
        ]
        return "\n".join(lines)
