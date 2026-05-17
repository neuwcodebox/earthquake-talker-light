from __future__ import annotations

import logging
import time
from collections.abc import Iterable

from earthquake_talker_light.config import Settings
from earthquake_talker_light.message import Message
from earthquake_talker_light.sources import Source
from earthquake_talker_light.sources.micro import KmaMicroSource
from earthquake_talker_light.sources.overseas import KmaOverseasEarthquakeSource
from earthquake_talker_light.sources.pews import KmaPewsSource
from earthquake_talker_light.state import StateStore
from earthquake_talker_light.telegram import TelegramClient


def build_sources(settings: Settings, state_store: StateStore) -> list[Source]:
    sources: list[Source] = [
        KmaMicroSource(
            state_store.section("micro"),
            interval_seconds=settings.micro_interval_seconds,
            timeout=settings.request_timeout_seconds,
        ),
        KmaPewsSource(
            state_store.section("pews"),
            output_dir=settings.output_dir,
            interval_seconds=settings.pews_interval_seconds,
            timeout=settings.request_timeout_seconds,
        ),
    ]
    if settings.kma_api_key:
        sources.append(
            KmaOverseasEarthquakeSource(
                state_store.section("overseas"),
                settings.kma_api_key,
                interval_seconds=settings.overseas_interval_seconds,
                timeout=settings.request_timeout_seconds,
            )
        )
    else:
        logging.info("KMA_API_KEY is not set; overseas earthquake source is disabled")
    return sources


def send_all(client: TelegramClient, messages: Iterable[Message]) -> None:
    for message in messages:
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                client.send(message)
                break
            except Exception:
                if attempt >= attempts:
                    logging.exception("Failed to send Telegram message after retries")
                else:
                    logging.exception("Failed to send Telegram message; retrying")
                    time.sleep(1.0)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    settings.validate_for_send()

    state_store = StateStore(settings.state_path)
    state_store.load()
    sources = build_sources(settings, state_store)
    client = TelegramClient(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        dry_run=settings.dry_run,
        timeout=settings.request_timeout_seconds,
    )

    next_due = {source.name: 0.0 for source in sources}
    logging.info("Started earthquake talker with %d source(s)", len(sources))

    try:
        while True:
            now = time.monotonic()
            for source in sources:
                if now < next_due[source.name]:
                    continue
                next_due[source.name] = now + source.interval_seconds
                try:
                    messages = source.poll()
                    if messages:
                        send_all(client, messages)
                    state_store.save()
                except Exception:
                    logging.exception("Source failed: %s", source.name)
            time.sleep(settings.poll_interval_seconds)
    except KeyboardInterrupt:
        logging.info("Interrupted; saving state")
        state_store.save()


if __name__ == "__main__":
    main()
