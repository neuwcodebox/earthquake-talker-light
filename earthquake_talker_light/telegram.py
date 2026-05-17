from __future__ import annotations

import json
import logging
import mimetypes
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .message import Message

logger = logging.getLogger(__name__)


class TelegramClient:
    def __init__(
        self,
        bot_token: str | None,
        chat_id: str | None,
        *,
        dry_run: bool = False,
        timeout: float = 15.0,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.dry_run = dry_run
        self.timeout = timeout

    def send(self, message: Message) -> None:
        if self.dry_run:
            logger.info("Dry-run Telegram message id=%s image=%s", message.id, bool(message.image_path))
            print(_telegram_body(message))
            if message.image_path:
                print(f"[photo] {message.image_path}")
            return

        if not self.bot_token or not self.chat_id:
            raise ValueError("Telegram token and chat id are required")

        if message.image_path:
            self._send_photo(message)
        else:
            self._send_text(message)

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def _send_text(self, message: Message) -> None:
        payload = {
            "chat_id": self.chat_id,
            "text": message.render_text(),
            "disable_web_page_preview": json.dumps(not message.preview),
            "disable_notification": json.dumps(message.disable_notification),
        }
        body = urlencode(payload).encode("utf-8")
        request = Request(
            self._api_url("sendMessage"),
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            response.read()

    def _send_photo(self, message: Message) -> None:
        assert message.image_path is not None
        fields = {
            "chat_id": self.chat_id or "",
            "caption": _telegram_body(message),
            "disable_notification": json.dumps(message.disable_notification),
        }
        body, content_type = _encode_multipart(fields, "photo", message.image_path)
        request = Request(
            self._api_url("sendPhoto"),
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            response.read()


def _encode_multipart(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = "----EarthquakeTalkerLightBoundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("ascii"),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _telegram_body(message: Message) -> str:
    if message.image_path:
        return message.text
    return message.render_text()
