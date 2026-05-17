from __future__ import annotations

from datetime import datetime, timezone

from PIL import Image

from earthquake_talker_light.message import KST, Priority
from earthquake_talker_light.sources.pews import (
    PEWS_DATA_PATH,
    MAX_EQK_INFO_LEN,
    HEAD_LENGTH,
    KmaPewsSource,
    PewsEarthquake,
    build_pews_message,
    decode_grid_values,
    mmi_to_string,
    parse_earthquake,
    parse_phase,
    parse_simulation_start_time,
    render_grid_image,
)


def _bits(value: int, width: int) -> str:
    return format(value, f"0{width}b")


def _quake_body_bits() -> str:
    unix_time = int(datetime(2026, 5, 17, 12, 34, 56, tzinfo=timezone.utc).timestamp())
    fields = "".join(
        [
            _bits(512, 10),
            _bits(303, 10),
            _bits(42, 7),
            _bits(123, 10),
            _bits(unix_time, 32),
            _bits(12345, 26),
            _bits(5, 4),
            "1" + "0" * 16,
        ]
    )
    return fields.ljust(MAX_EQK_INFO_LEN, "0") + ("0" * 480)


def _bytes_from_bits(bits: str) -> bytes:
    padded = bits + "0" * ((8 - len(bits) % 8) % 8)
    return bytes(int(padded[index : index + 8], 2) for index in range(0, len(padded), 8))


def _quake_binary(phase: int = 3) -> bytes:
    header_bits = ("01100000" if phase == 3 else "01000000") + ("0" * 24)
    body = _bytes_from_bits(_quake_body_bits())
    return _bytes_from_bits(header_bits) + body


def test_parse_phase_from_header_bits() -> None:
    assert parse_phase("00000000") == 1
    assert parse_phase("01000000") == 2
    assert parse_phase("01100000") == 3


def test_parse_earthquake_extracts_pews_fields() -> None:
    quake = parse_earthquake(2, _quake_body_bits(), "테스트 지진".encode("utf-8"))

    assert quake.latitude == 35.12
    assert quake.longitude == 127.03
    assert quake.magnitude == 4.2
    assert quake.depth_km == 12.3
    assert quake.earthquake_id == "2012345"
    assert quake.intensity == 5
    assert quake.max_areas == ["서울"]
    assert quake.occurred_at.tzinfo == KST


def test_pews_message_uses_expected_priority_and_text() -> None:
    quake = PewsEarthquake(
        phase=2,
        latitude=35.12,
        longitude=127.03,
        magnitude=4.2,
        depth_km=12.3,
        occurred_at=datetime(2026, 5, 17, 21, 34, 56, tzinfo=KST),
        earthquake_id="2012345",
        intensity=5,
        max_areas=["서울"],
        info_text="전북 익산 북쪽 5km 지역",
    )

    message = build_pews_message(quake)

    assert message.level == Priority.CRITICAL
    assert "지진 신속정보" in message.text
    assert "최대 진도 : V(5)" in message.text


def test_pews_grid_photo_message_uses_csharp_style_caption(tmp_path) -> None:
    def fetcher(url: str, _timeout: float) -> bytes:
        if url.endswith(".b"):
            return _quake_binary()
        if url.endswith(".i"):
            return bytes([0x45]) * 128
        raise AssertionError(f"unexpected URL: {url}")

    source = KmaPewsSource(
        output_dir=tmp_path,
        fetcher=fetcher,
        now_provider=lambda: datetime(2026, 5, 17, 12, 34, 56, tzinfo=timezone.utc),
    )
    messages = source.poll()

    assert len(messages) == 2
    photo_message = messages[1]
    assert photo_message.sender == "기상청 실시간 지진감시"
    assert photo_message.text == "기상청 실시간 지진감시"
    assert photo_message.image_path is not None


def test_decode_grid_values_maps_extended_i_to_one() -> None:
    assert decode_grid_values(bytes([0x2C, 0xAF])) == [2, 1, 10, 1]
    assert mmi_to_string(12) == "XII"


def test_render_grid_image_writes_png(tmp_path) -> None:
    quake = PewsEarthquake(
        phase=3,
        latitude=35.12,
        longitude=127.03,
        magnitude=4.2,
        depth_km=12.3,
        occurred_at=datetime(2026, 5, 17, 21, 34, 56, tzinfo=KST),
        earthquake_id="2012345",
        intensity=5,
        max_areas=["서울"],
        info_text="전북 익산 북쪽 5km 지역",
    )

    path = render_grid_image(bytes([0x45]) * 128, quake, tmp_path)

    assert path.exists()
    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.width > 0
        assert image.height > 0


def test_parse_simulation_start_time_uses_kst() -> None:
    parsed = parse_simulation_start_time("20260517213456")

    assert parsed.tzinfo == KST
    assert parsed.astimezone(timezone.utc) == datetime(2026, 5, 17, 12, 34, 56, tzinfo=timezone.utc)


def test_pews_source_simulation_uses_event_path_and_one_byte_header(tmp_path) -> None:
    urls: list[str] = []

    def fetcher(url: str, _timeout: float) -> bytes:
        urls.append(url)
        return b""

    source = KmaPewsSource(
        output_dir=tmp_path,
        simulation=("2017000407", "20260517213456"),
        fetcher=fetcher,
        now_provider=lambda: datetime(2026, 5, 17, 12, 34, 56, tzinfo=timezone.utc),
    )

    assert source.data_path == f"{PEWS_DATA_PATH}/2017000407"
    assert source.head_length == 1
    assert source.tide_ms == 0
    assert source.poll() == []
    assert urls == [f"{PEWS_DATA_PATH}/2017000407/20260517123456.b"]


def test_pews_source_simulation_does_not_stop_for_past_event_wall_time(tmp_path) -> None:
    urls: list[str] = []

    def fetcher(url: str, _timeout: float) -> bytes:
        urls.append(url)
        return b""

    source = KmaPewsSource(
        output_dir=tmp_path,
        simulation=("2017000407", "20171115142931"),
        fetcher=fetcher,
        now_provider=lambda: datetime(2026, 5, 17, 12, 34, 56, tzinfo=timezone.utc),
    )

    assert source.poll() == []
    assert source.data_path == f"{PEWS_DATA_PATH}/2017000407"
    assert source.head_length == 1
    assert urls == [f"{PEWS_DATA_PATH}/2017000407/20171115052931.b"]


def test_pews_source_stops_simulation_after_duration(tmp_path) -> None:
    now_values = iter(
        [
            datetime(2026, 5, 17, 12, 34, 56, tzinfo=timezone.utc),
            datetime(2026, 5, 17, 12, 40, 0, tzinfo=timezone.utc),
        ]
    )
    source = KmaPewsSource(
        output_dir=tmp_path,
        simulation=("2017000407", "20260517213456"),
        now_provider=lambda: next(now_values),
    )

    assert source.poll() == []
    assert source.data_path == PEWS_DATA_PATH
    assert source.head_length == HEAD_LENGTH
