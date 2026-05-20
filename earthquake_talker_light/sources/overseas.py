from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Callable
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from earthquake_talker_light.http import fetch_bytes
from earthquake_talker_light.message import KST, Message, Priority

OVERSEAS_ENDPOINT = "https://apihub.kma.go.kr/api/typ09/url/eqk/urlNewNotiEqk.do"
STATE_TTL_SECONDS = 60 * 60 * 24 * 3
EVENT_MAX_AGE_SECONDS = int(STATE_TTL_SECONDS * 0.9)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OverseasEarthquakeItem:
    msg_code: str | None
    cnt_div: str | None
    ar_div: str | None
    eq_area_name: str | None
    eq_point: str | None
    nk_div: str | None
    issued_raw: str | None
    occurred_raw: str | None
    magnitude: float | None
    magnitude_diff: str | None
    depth_km: float | None
    latitude: float | None
    longitude: float | None
    major_axis: str | None
    minor_axis: str | None
    depth_diff: str | None
    max_intensity: str | None
    intensity_areas: str | None
    refer: str | None


class KmaOverseasEarthquakeSource:
    name = "overseas"

    def __init__(
        self,
        auth_key: str,
        *,
        interval_seconds: float = 30.0,
        timeout: float = 15.0,
        fetcher: Callable[[str, float], str] | None = None,
    ) -> None:
        self.seen: dict[str, str] = {}
        self.initialized = False
        self.auth_key = auth_key
        self.interval_seconds = interval_seconds
        self.timeout = timeout
        self.fetcher = fetcher or self._fetch

    def poll(self) -> list[Message]:
        now = datetime.now(timezone.utc)
        url = build_request_url(self.auth_key, now)
        xml = self.fetcher(url, self.timeout)
        items = parse_overseas_items(xml)
        previous_seen = set(self.seen)
        messages: list[Message] = []
        domestic_impact_count = 0

        for item in items:
            if not has_domestic_impact(item):
                continue
            domestic_impact_count += 1
            occurred_at = parse_kst_compact_timestamp(item.occurred_raw)
            if occurred_at and now - occurred_at > timedelta(seconds=EVENT_MAX_AGE_SECONDS):
                logger.debug("Skipped old overseas earthquake occurred_raw=%s", item.occurred_raw)
                continue
            event_id = build_event_id(item.occurred_raw, item.issued_raw)
            if not event_id:
                logger.warning("Skipped overseas earthquake without event id occurred=%s issued=%s", item.occurred_raw, item.issued_raw)
                continue
            self.seen[event_id] = now.isoformat()
            if event_id in previous_seen and self.initialized:
                continue
            if self.initialized:
                logger.info("Detected overseas earthquake event_id=%s location=%s", event_id, item.eq_point or item.eq_area_name)
                messages.append(build_message(item))

        if not self.initialized:
            logger.info(
                "Initialized overseas baseline items=%d domestic_impact=%d seen=%d",
                len(items),
                domestic_impact_count,
                len(self.seen),
            )
        else:
            logger.debug(
                "Overseas poll complete items=%d domestic_impact=%d new_messages=%d seen=%d",
                len(items),
                domestic_impact_count,
                len(messages),
                len(self.seen),
            )
        self.initialized = True
        self._prune_seen(now)
        return messages

    def _prune_seen(self, now: datetime) -> None:
        expired: list[str] = []
        for key, value in self.seen.items():
            try:
                last_seen = datetime.fromisoformat(str(value))
            except ValueError:
                expired.append(key)
                continue
            if now - last_seen > timedelta(seconds=STATE_TTL_SECONDS):
                expired.append(key)
        for key in expired:
            self.seen.pop(key, None)
        if expired:
            logger.info("Pruned overseas seen events count=%d", len(expired))

    @staticmethod
    def _fetch(url: str, timeout: float) -> str:
        return fetch_bytes(url, timeout=timeout).text


def build_request_url(auth_key: str, now: datetime) -> str:
    kst_now = now.astimezone(KST)
    yesterday = kst_now - timedelta(days=1)
    params = {
        "orderTy": "xml",
        "frDate": yesterday.strftime("%Y%m%d"),
        "laDate": kst_now.strftime("%Y%m%d"),
        "cntDiv": "N",
        "authKey": auth_key,
    }
    return f"{OVERSEAS_ENDPOINT}?{urlencode(params)}"


def parse_overseas_items(xml: str) -> list[OverseasEarthquakeItem]:
    root = ET.fromstring(xml)
    items: list[OverseasEarthquakeItem] = []
    for node in root.findall(".//info"):
        cnt_div = _text(node, "cntDiv")
        if cnt_div and cnt_div != "N":
            continue
        items.append(
            OverseasEarthquakeItem(
                msg_code=_text(node, "msgCode"),
                cnt_div=cnt_div,
                ar_div=_text(node, "arDiv"),
                eq_area_name=_text(node, "eqArCdNm"),
                eq_point=_text(node, "eqPt"),
                nk_div=_text(node, "nkDiv"),
                issued_raw=_raw_text(node, "tmIssue"),
                occurred_raw=_raw_text(node, "eqDate"),
                magnitude=_number(_raw_text(node, "magMl")),
                magnitude_diff=_text(node, "magDiff"),
                depth_km=_number(_raw_text(node, "eqDt")),
                latitude=_number(_raw_text(node, "eqLt")),
                longitude=_number(_raw_text(node, "eqLn")),
                major_axis=_text(node, "majorAxis"),
                minor_axis=_text(node, "minorAxis"),
                depth_diff=_text(node, "depthDiff"),
                max_intensity=_text(node, "jdLoc"),
                intensity_areas=_text(node, "jdLocA"),
                refer=_text(node, "ReFer"),
            )
        )
    return items


def has_domestic_impact(item: OverseasEarthquakeItem) -> bool:
    return has_domestic_impact_value(item.max_intensity) or has_domestic_impact_value(item.intensity_areas)


def has_domestic_impact_value(value: str | None) -> bool:
    normalized = normalize_text(value)
    return bool(normalized and normalized != "-")


def build_message(item: OverseasEarthquakeItem) -> Message:
    location = item.eq_point or item.eq_area_name or "국외"
    title_parts = [location]
    if item.magnitude is not None:
        title_parts.append(f"규모 {item.magnitude:.1f}")
    title = f"{' '.join(title_parts)} 지진"

    lines = [title]
    occurred = format_kst_compact_timestamp(item.occurred_raw)
    if occurred:
        lines.append(f"발생 시각: {occurred}")
    if item.max_intensity:
        lines.append(f"국내 최대진도: {item.max_intensity}")
    if item.intensity_areas:
        lines.append(f"지역별 진도: {item.intensity_areas}")
    if item.depth_km is not None:
        lines.append(f"깊이: {format_depth(item.depth_km)}")
    if item.latitude is not None and item.longitude is not None:
        lines.append(f"위치: {item.latitude:.2f}, {item.longitude:.2f}")
    if item.refer:
        lines.append(f"참고: {item.refer}")
    issued = format_kst_compact_timestamp(item.issued_raw)
    if issued:
        lines.append(f"발표 시각: {issued}")

    return Message(
        sender="기상청 국외지진 정보",
        text="\n".join(lines),
        level=priority_from_intensity(item.max_intensity),
    )


def priority_from_intensity(value: str | None) -> Priority:
    intensity = parse_intensity(value)
    if intensity is None:
        return Priority.NORMAL
    if intensity >= 7:
        return Priority.CRITICAL
    if intensity >= 5:
        return Priority.HIGH
    return Priority.NORMAL


def parse_intensity(value: str | None) -> int | None:
    normalized = normalize_text(value)
    if not normalized:
        return None
    compact = normalized.replace(" ", "").upper()
    labels = {
        "Ⅰ": 1,
        "I": 1,
        "Ⅱ": 2,
        "II": 2,
        "Ⅲ": 3,
        "III": 3,
        "Ⅳ": 4,
        "IV": 4,
        "Ⅴ": 5,
        "V": 5,
        "Ⅵ": 6,
        "VI": 6,
        "Ⅶ": 7,
        "VII": 7,
        "Ⅷ": 8,
        "VIII": 8,
        "Ⅸ": 9,
        "IX": 9,
        "Ⅹ": 10,
        "X": 10,
        "Ⅺ": 11,
        "XI": 11,
        "Ⅻ": 12,
        "XII": 12,
    }
    if compact in labels:
        return labels[compact]
    numeric = re.search(r"\d+", compact)
    if numeric:
        return int(numeric.group(0))
    for label, intensity in sorted(labels.items(), key=lambda item: len(item[0]), reverse=True):
        if label in compact:
            return intensity
    return None


def build_event_id(occurred_raw: str | None, issued_raw: str | None) -> str | None:
    occurred = normalize_compact_timestamp(occurred_raw)
    issued = normalize_compact_timestamp(issued_raw)
    if not occurred or not issued:
        return None
    return f"{occurred}:{issued}"


def parse_kst_compact_timestamp(value: str | None) -> datetime | None:
    normalized = normalize_compact_timestamp(value)
    if not normalized or len(normalized) not in {12, 14}:
        return None
    second = normalized[12:14] if len(normalized) == 14 else "00"
    try:
        return datetime(
            int(normalized[0:4]),
            int(normalized[4:6]),
            int(normalized[6:8]),
            int(normalized[8:10]),
            int(normalized[10:12]),
            int(second),
            tzinfo=KST,
        ).astimezone(timezone.utc)
    except ValueError:
        return None


def format_kst_compact_timestamp(value: str | None) -> str | None:
    normalized = normalize_compact_timestamp(value)
    if not normalized or len(normalized) not in {12, 14}:
        return normalize_text(value)
    second = normalized[12:14] if len(normalized) == 14 else "00"
    return (
        f"{normalized[0:4]}-{normalized[4:6]}-{normalized[6:8]} "
        f"{normalized[8:10]}:{normalized[10:12]}:{second} KST"
    )


def normalize_compact_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) >= 12 else None


def format_depth(value: float) -> str:
    return "-" if value <= 0 else f"{value:.1f} km"


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def _raw_text(node: ET.Element, tag: str) -> str | None:
    child = node.find(tag)
    if child is None or child.text is None:
        return None
    return child.text.strip() or None


def _text(node: ET.Element, tag: str) -> str | None:
    return normalize_text(_raw_text(node, tag))


def _number(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed
