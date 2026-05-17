from pathlib import Path

from earthquake_talker_light.message import Message
from earthquake_talker_light.telegram import _encode_multipart, _telegram_body


def test_photo_message_body_uses_plain_caption(tmp_path: Path) -> None:
    image_path = tmp_path / "grid.png"
    image_path.write_bytes(b"png")
    message = Message(
        sender="기상청 실시간 지진감시",
        text="기상청 실시간 지진감시",
        image_path=image_path,
    )

    assert _telegram_body(message) == "기상청 실시간 지진감시"
    assert "<<" not in _telegram_body(message)
    assert "##" not in _telegram_body(message)


def test_photo_multipart_caption_is_plain_text(tmp_path: Path) -> None:
    image_path = tmp_path / "grid.png"
    image_path.write_bytes(b"png")

    body, _content_type = _encode_multipart(
        {"chat_id": "chat", "caption": "기상청 실시간 지진감시"},
        "photo",
        image_path,
    )

    decoded = body.decode("utf-8", errors="ignore")
    assert "기상청 실시간 지진감시" in decoded
    assert "<<" not in decoded
    assert "##" not in decoded
