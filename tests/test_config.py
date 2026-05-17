from __future__ import annotations

from earthquake_talker_light.config import Settings


def test_settings_loads_dotenv_and_interval_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "KMA_API_KEY",
        "PEWS_INTERVAL_SECONDS",
        "OVERSEAS_INTERVAL_SECONDS",
        "DRY_RUN",
    ]:
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "TELEGRAM_BOT_TOKEN=token-from-env-file",
                "TELEGRAM_CHAT_ID=chat-from-env-file",
                "DRY_RUN=1",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings.from_env()

    assert settings.telegram_bot_token == "token-from-env-file"
    assert settings.telegram_chat_id == "chat-from-env-file"
    assert settings.dry_run is True
    assert settings.pews_interval_seconds == 1.0
    assert settings.overseas_interval_seconds == 30.0
