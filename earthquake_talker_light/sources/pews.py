from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

from PIL import Image, ImageDraw

from earthquake_talker_light.http import NotFoundError, fetch_bytes
from earthquake_talker_light.message import KST, Message, Priority

PEWS_DATA_PATH = "https://www.weather.go.kr/pews/data"
HEAD_LENGTH = 4
MAX_EQK_STR_LEN = 60
MAX_EQK_INFO_LEN = 120
AREA_NAMES = [
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
]
MMI_COLORS = [
    "#FFFFFF",
    "#FFFFFF",
    "#A0E6FF",
    "#92D050",
    "#FFFF00",
    "#FFC000",
    "#FF0000",
    "#A32777",
    "#632523",
    "#4C2600",
    "#000000",
]


@dataclass(frozen=True)
class PewsEarthquake:
    phase: int
    latitude: float
    longitude: float
    magnitude: float
    depth_km: float
    occurred_at: datetime
    earthquake_id: str
    intensity: int
    max_areas: list[str]
    info_text: str

    @property
    def alarm_id(self) -> str:
        return f"{self.earthquake_id}{self.phase}"

    @property
    def epicenter_xy(self) -> tuple[float, float]:
        return ((self.longitude - 124.5) * 113 - 4, (38.9 - self.latitude) * 138.4 - 7)


class KmaPewsSource:
    name = "pews"

    def __init__(
        self,
        state: dict[str, Any],
        *,
        output_dir: Path,
        interval_seconds: float = 0.5,
        timeout: float = 15.0,
        data_path: str = PEWS_DATA_PATH,
        fetcher: Callable[[str, float], bytes] | None = None,
    ) -> None:
        self.state = state
        self.output_dir = output_dir
        self.interval_seconds = interval_seconds
        self.timeout = timeout
        self.data_path = data_path.rstrip("/")
        self.fetcher = fetcher or self._fetch
        self.tide_ms = float(self.state.get("tide_ms", 1000.0))

    def poll(self) -> list[Message]:
        bin_time = datetime.fromtimestamp(
            (datetime.now(timezone.utc).timestamp() * 1000 - self.tide_ms) / 1000,
            tz=timezone.utc,
        )
        bin_time_str = bin_time.strftime("%Y%m%d%H%M%S")
        if self.state.get("previous_bin_time") == bin_time_str:
            return []
        self.state["previous_bin_time"] = bin_time_str

        try:
            bytes_b = self.fetcher(f"{self.data_path}/{bin_time_str}.b", self.timeout)
        except NotFoundError:
            return []

        if len(bytes_b) <= MAX_EQK_STR_LEN:
            return []

        header_bits = bytes_to_bits(bytes_b[:HEAD_LENGTH])
        body_bits = bytes_to_bits(bytes_b[HEAD_LENGTH:])
        phase = parse_phase(header_bits)
        if phase <= 1:
            return []

        quake = parse_earthquake(phase, body_bits, bytes_b[-MAX_EQK_STR_LEN:])
        if quake.alarm_id == self.state.get("previous_alarm_id"):
            return []

        info_text = self._request_location_text(quake.earthquake_id, phase) or quake.info_text
        quake = PewsEarthquake(
            phase=quake.phase,
            latitude=quake.latitude,
            longitude=quake.longitude,
            magnitude=quake.magnitude,
            depth_km=quake.depth_km,
            occurred_at=quake.occurred_at,
            earthquake_id=quake.earthquake_id,
            intensity=quake.intensity,
            max_areas=quake.max_areas,
            info_text=info_text,
        )
        self.state["previous_alarm_id"] = quake.alarm_id

        messages = [build_pews_message(quake)]
        image_path = self._request_grid_image(quake)
        if image_path:
            messages.append(
                Message(
                    sender="기상청 실시간 지진감시",
                    text=f"진도 그리드 이미지\n지진 ID: {quake.earthquake_id}",
                    level=Priority.NORMAL,
                    image_path=image_path,
                )
            )
        return messages

    def _request_location_text(self, earthquake_id: str, phase: int) -> str | None:
        suffix = "le" if phase == 2 else "li" if phase == 3 else None
        if not suffix:
            return None
        try:
            raw = self.fetcher(f"{self.data_path}/{earthquake_id}.{suffix}", self.timeout)
        except Exception:
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        value = payload.get("info_ko") if isinstance(payload, dict) else None
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _request_grid_image(self, quake: PewsEarthquake) -> Path | None:
        suffix = "e" if quake.phase == 2 else "i"
        try:
            raw = self.fetcher(f"{self.data_path}/{quake.earthquake_id}.{suffix}", self.timeout)
        except Exception:
            return None
        return render_grid_image(raw, quake, self.output_dir)

    @staticmethod
    def _fetch(url: str, timeout: float) -> bytes:
        return fetch_bytes(url, timeout=timeout).body


def parse_phase(header_bits: str) -> int:
    if len(header_bits) < 3:
        return 1
    if header_bits[1] == "0":
        return 1
    if header_bits[1] == "1" and header_bits[2] == "0":
        return 2
    if header_bits[2] == "1":
        return 3
    return 1


def parse_earthquake(phase: int, body_bits: str, info_bytes: bytes) -> PewsEarthquake:
    data_len = MAX_EQK_STR_LEN * 8 + MAX_EQK_INFO_LEN
    data = body_bits[-data_len:]
    if len(data) < data_len:
        raise ValueError("PEWS body is too short")

    latitude = 30 + int(data[0:10], 2) / 100
    longitude = 124 + int(data[10:20], 2) / 100
    magnitude = int(data[20:27], 2) / 10
    depth_km = int(data[27:37], 2) / 10
    unix_time = int(data[37:69], 2)
    occurred_at = datetime.fromtimestamp(unix_time, tz=timezone.utc).astimezone(KST)
    earthquake_id = "20" + str(int(data[69:95], 2))
    intensity = int(data[95:99], 2)
    max_area_bits = data[99:116]
    max_areas = [
        AREA_NAMES[index]
        for index, bit in enumerate(max_area_bits)
        if bit == "1" and index < len(AREA_NAMES)
    ]
    if max_area_bits == "1" * len(max_area_bits):
        max_areas = []

    info_text = unquote(info_bytes.decode("utf-8", errors="replace")).strip()
    return PewsEarthquake(
        phase=phase,
        latitude=latitude,
        longitude=longitude,
        magnitude=magnitude,
        depth_km=depth_km,
        occurred_at=occurred_at,
        earthquake_id=earthquake_id,
        intensity=intensity,
        max_areas=max_areas,
        info_text=info_text,
    )


def build_pews_message(quake: PewsEarthquake) -> Message:
    if quake.phase == 2:
        lines = [
            "⚠️ 지진 신속정보가 발표되었습니다.",
            f"정보 : {quake.info_text}",
            f"발생 시각 : {quake.occurred_at:%Y-%m-%d %H:%M:%S}",
            f"추정 규모 : {quake.magnitude:.1f}",
            f"최대 진도 : {mmi_to_string(quake.intensity)}({quake.intensity})",
            "대피 요령 : https://www.weather.go.kr/pews/man/m.html",
            "수동으로 분석한 정보는 추후 발표될 예정입니다.",
            "",
            know_how_from_mmi(quake.intensity),
        ]
        return Message(
            sender="기상청 실시간 지진감시",
            text="\n".join(lines).rstrip(),
            level=Priority.CRITICAL,
        )

    areas = ", ".join(quake.max_areas) if quake.max_areas else "-"
    depth = "-" if quake.depth_km == 0 else f"{quake.depth_km:.1f} km"
    lines = [
        "지진 상세정보가 발표되었습니다.",
        f"정보 : {quake.info_text}",
        f"발생 시각 : {quake.occurred_at:%Y-%m-%d %H:%M:%S}",
        f"규모 : {quake.magnitude:.1f}",
        f"깊이 : {depth}",
        f"최대 진도 : {mmi_to_string(quake.intensity)}({quake.intensity})",
        f"영향 지역 : {areas}",
    ]
    return Message(
        sender="기상청 실시간 지진감시",
        text="\n".join(lines),
        level=Priority.HIGH,
    )


def render_grid_image(grid_bytes: bytes, quake: PewsEarthquake, output_dir: Path) -> Path:
    grid_dir = output_dir / "grids"
    grid_dir.mkdir(parents=True, exist_ok=True)
    map_path = Path("references/EarthquakeTalker/Resources/map.png")
    if map_path.exists():
        base_map = Image.open(map_path).convert("RGBA")
        canvas = Image.new("RGBA", base_map.size, (211, 211, 211, 255))
    else:
        base_map = None
        canvas = Image.new("RGBA", (860, 820), (211, 211, 211, 255))
    draw = ImageDraw.Draw(canvas)

    grid_data = decode_grid_values(grid_bytes)
    iterator = iter(grid_data)
    stop = False
    for lat_index in range(int(round((38.85 - 33.0) / 0.05))):
        lat = 38.85 - lat_index * 0.05
        for lon_index in range(int(round((132.05 - 124.5) / 0.05))):
            lon = 124.5 + lon_index * 0.05
            try:
                mmi = next(iterator)
            except StopIteration:
                stop = True
                break
            if 0 <= mmi < len(MMI_COLORS):
                x = (lon - 124.5) * 113 - 4
                y = (38.9 - lat) * 138.4 - 7
                draw.rectangle((x, y, x + 8, y + 8), fill=MMI_COLORS[mmi])
        if stop:
            break

    if base_map is not None:
        canvas.alpha_composite(base_map)

    x, y = quake.epicenter_xy
    if -32 < x < canvas.width + 32 and -32 < y < canvas.height + 32:
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill="#0059FF", outline="#0059FF")
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), outline="#0059FF", width=2)
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), outline="#0059FF", width=2)

    file_path = grid_dir / f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{quake.earthquake_id}.png"
    canvas.convert("RGB").save(file_path)
    return file_path


def decode_grid_values(grid_bytes: bytes) -> list[int]:
    values: list[int] = []
    for byte in grid_bytes:
        for shift in (4, 0):
            value = (byte >> shift) & 0x0F
            values.append(1 if value > 11 else value)
    return values


def bytes_to_bits(data: bytes) -> str:
    return "".join(f"{byte:08b}" for byte in data)


def mmi_to_string(mmi: int) -> str:
    values = ["I-", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XII+"]
    if mmi < 0:
        return values[0]
    if mmi >= len(values):
        return values[-1]
    return values[mmi]


def know_how_from_mmi(mmi: int) -> str:
    lines = [f"[진도(MMI) {mmi_to_string(mmi)} 특징]"]
    if mmi <= 0:
        lines.append("무감.")
    elif mmi == 1:
        lines.append("미세한 진동. 특수한 조건에서 극히 소수 느낌.")
    elif mmi == 2:
        lines.append("실내에서 극히 소수 느낌.")
    elif mmi == 3:
        lines.append("실내에서 소수 느낌. 매달린 물체가 약하게 움직임.")
    elif mmi == 4:
        lines.extend(["실내에서 다수 느낌. 실외에서는 감지하지 못함.", "일부의 사람들이 잠에서 깸. 사물이 떨리는 소리가 들림."])
    elif mmi == 5:
        lines.extend(["건물 전체가 흔들림. 물체의 파손, 뒤집힘, 추락.", "가벼운 물체의 위치 이동. 다수의 사람들이 잠에서 깸."])
    elif mmi == 6:
        lines.extend(["똑바로 걷기 어려움. 약한 건물의 회벽이 떨어지거나 금이 감.", "무거운 물체의 이동 또는 뒤집힘."])
    elif mmi == 7:
        lines.extend(["서 있기 곤란함. 운전 중에도 지진을 느낌.", "회벽이 무너지고 느슨한 적재물과 담장이 무너짐.", "보통의 건물들에 경미한 손상."])
    elif mmi == 8:
        lines.extend(["차량운전 곤란. 일부 건물 붕괴.", "사면이나 지표의 균열.탑·굴뚝 붕괴."])
    elif mmi == 9:
        lines.extend(["견고한 건물의 피해가 심하거나 붕괴.", "지표의 균열이 발생하고 지하 파이프관 파손."])
    elif mmi == 10:
        lines.extend(["대다수 견고한 건물과 구조물 파괴.", "지표균열, 대규모 사태, 아스팔트 균열."])
    elif mmi == 11:
        lines.append("철로가 심하게 휨. 구조물 거의 파괴. 지하 파이프관 작동 불가능.")
    else:
        lines.extend(["천재지변. 모든 것이 완파된다.", "지면이 파도 형태로 움직임.물체가 공중으로 튀어오름.", "큰 바위가 굴러 떨어짐.강의 경로가 바뀜."])
    return "\n".join(lines)
