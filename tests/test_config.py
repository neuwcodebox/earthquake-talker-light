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
        "PEWS_SIM_EARTHQUAKE_ID",
        "PEWS_SIM_START_TIME",
        "PEWS_SIM_DURATION_SECONDS",
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
    assert settings.pews_sim_earthquake_id is None
    assert settings.pews_sim_start_time is None
    assert settings.pews_sim_duration_seconds == 300.0


def test_settings_rejects_partial_pews_simulation(monkeypatch) -> None:
    monkeypatch.setenv("DRY_RUN", "1")
    monkeypatch.setenv("PEWS_SIM_EARTHQUAKE_ID", "2017000407")
    monkeypatch.delenv("PEWS_SIM_START_TIME", raising=False)

    settings = Settings.from_env()

    try:
        settings.validate_for_send()
    except ValueError as error:
        assert "PEWS_SIM_EARTHQUAKE_ID" in str(error)
    else:
        raise AssertionError("expected partial PEWS simulation config to fail")
