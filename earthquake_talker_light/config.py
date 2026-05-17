from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    kma_api_key: str | None
    output_dir: Path
    poll_interval_seconds: float
    micro_interval_seconds: float
    pews_interval_seconds: float
    overseas_interval_seconds: float
    dry_run: bool
    request_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(dotenv_path=Path(".env"))
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            kma_api_key=os.getenv("KMA_API_KEY"),
            output_dir=Path(os.getenv("OUTPUT_DIR", "output")),
            poll_interval_seconds=_float_env("POLL_INTERVAL_SECONDS", 1.0),
            micro_interval_seconds=_float_env("MICRO_INTERVAL_SECONDS", 10.0),
            pews_interval_seconds=_float_env("PEWS_INTERVAL_SECONDS", 1.0),
            overseas_interval_seconds=_float_env("OVERSEAS_INTERVAL_SECONDS", 30.0),
            dry_run=_bool_env("DRY_RUN"),
            request_timeout_seconds=_float_env("REQUEST_TIMEOUT_SECONDS", 15.0),
        )

    def validate_for_send(self) -> None:
        if self.dry_run:
            return
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required unless DRY_RUN=1")
        if not self.telegram_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is required unless DRY_RUN=1")
