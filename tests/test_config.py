from __future__ import annotations

import pytest

from earthquake_talker_light.config import Settings, parse_pews_simulation


def test_settings_loads_dotenv_and_interval_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for name in [
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "KMA_API_KEY",
        "PEWS_INTERVAL_SECONDS",
        "OVERSEAS_INTERVAL_SECONDS",
        "DRY_RUN",
        "PEWS_SIMULATION",
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
    assert settings.pews_simulation is None


def test_settings_loads_pews_simulation_from_single_env(monkeypatch) -> None:
    monkeypatch.setenv("DRY_RUN", "1")
    monkeypatch.setenv("PEWS_SIMULATION", "2017000407:20171115142931")

    settings = Settings.from_env()

    assert settings.pews_simulation == ("2017000407", "20171115142931")


def test_parse_pews_simulation_rejects_bad_format() -> None:
    with pytest.raises(ValueError, match="PEWS_SIMULATION"):
        parse_pews_simulation("2017000407")
