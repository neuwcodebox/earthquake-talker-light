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
from earthquake_talker_light.telegram import TelegramClient

logger = logging.getLogger(__name__)


def build_sources(settings: Settings) -> list[Source]:
    sources: list[Source] = [
        KmaMicroSource(
            interval_seconds=settings.micro_interval_seconds,
            timeout=settings.request_timeout_seconds,
        ),
        KmaPewsSource(
            output_dir=settings.output_dir,
            interval_seconds=settings.pews_interval_seconds,
            timeout=settings.request_timeout_seconds,
            simulation=settings.pews_simulation,
        ),
    ]
    if settings.kma_api_key:
        logger.info("KMA_API_KEY is set; overseas earthquake source is enabled")
        sources.append(
            KmaOverseasEarthquakeSource(
                settings.kma_api_key,
                interval_seconds=settings.overseas_interval_seconds,
                timeout=settings.request_timeout_seconds,
            )
        )
    else:
        logger.info("KMA_API_KEY is not set; overseas earthquake source is disabled")
    for source in sources:
        logger.info("Configured source: %s interval=%.3fs", source.name, source.interval_seconds)
    return sources


def send_all(client: TelegramClient, messages: Iterable[Message]) -> None:
    for message in messages:
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                client.send(message)
                logger.info(
                    "Sent message id=%s sender=%s level=%s image=%s",
                    message.id,
                    message.sender,
                    message.level.name,
                    bool(message.image_path),
                )
                break
            except Exception:
                if attempt >= attempts:
                    logger.exception("Failed to send Telegram message after retries id=%s", message.id)
                else:
                    logger.exception(
                        "Failed to send Telegram message; retrying id=%s attempt=%d",
                        message.id,
                        attempt,
                    )
                    time.sleep(1.0)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    settings.validate_for_send()
    logger.info(
        "Settings loaded dry_run=%s output_dir=%s poll_interval=%.3fs pews_simulation=%s",
        settings.dry_run,
        settings.output_dir,
        settings.poll_interval_seconds,
        bool(settings.pews_simulation),
    )

    sources = build_sources(settings)
    client = TelegramClient(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        dry_run=settings.dry_run,
        timeout=settings.request_timeout_seconds,
    )

    next_due = {source.name: 0.0 for source in sources}
    logger.info("Started earthquake talker with %d source(s)", len(sources))

    try:
        while True:
            now = time.monotonic()
            for source in sources:
                if now < next_due[source.name]:
                    continue
                next_due[source.name] = now + source.interval_seconds
                try:
                    messages = source.poll()
                    logger.debug("Source polled: %s messages=%d", source.name, len(messages))
                    if messages:
                        logger.info("Source produced messages: %s count=%d", source.name, len(messages))
                        send_all(client, messages)
                except Exception:
                    logger.exception("Source failed: %s", source.name)
            time.sleep(settings.poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Interrupted")


if __name__ == "__main__":
    main()
