from __future__ import annotations

from datetime import datetime

from earthquake_talker_light.message import KST, Priority
from earthquake_talker_light.sources.overseas import (
    KmaOverseasEarthquakeSource,
    parse_intensity,
    parse_overseas_items,
)


def _xml(*infos: str) -> str:
    return f"<response><body><items>{''.join(infos)}</items></body></response>"


def _info(eq_date: str, tm_issue: str, *, jd_loc: str = "Ⅴ") -> str:
    return f"""
    <info>
      <cntDiv>N</cntDiv>
      <eqPt>일본 혼슈 동쪽 해역</eqPt>
      <eqDate>{eq_date}</eqDate>
      <tmIssue>{tm_issue}</tmIssue>
      <magMl>6.1</magMl>
      <eqDt>30</eqDt>
      <eqLt>37.1</eqLt>
      <eqLn>142.2</eqLn>
      <jdLoc>{jd_loc}</jdLoc>
      <jdLocA>부산 Ⅱ, 울산 Ⅱ</jdLocA>
      <ReFer>국내 일부 지역에서 진동을 느낄 수 있음</ReFer>
    </info>
    """


def test_parse_overseas_items_keeps_domestic_impact_fields() -> None:
    items = parse_overseas_items(_xml(_info("202605172100", "202605172110")))

    assert len(items) == 1
    assert items[0].eq_point == "일본 혼슈 동쪽 해역"
    assert items[0].magnitude == 6.1
    assert items[0].max_intensity == "Ⅴ"


def test_parse_intensity_supports_roman_and_numeric_labels() -> None:
    assert parse_intensity("Ⅴ") == 5
    assert parse_intensity("VII") == 7
    assert parse_intensity("VII 이상") == 7
    assert parse_intensity("국내 최대 4") == 4


def test_overseas_source_skips_initial_and_emits_new_event() -> None:
    state: dict[str, object] = {}
    now_label = datetime.now(KST).strftime("%Y%m%d%H%M")
    first_xml = _xml(_info(now_label, now_label))
    second_xml = _xml(_info(now_label, now_label), _info(now_label, now_label + "01"))
    responses = iter([first_xml, second_xml])
    source = KmaOverseasEarthquakeSource(
        state,
        "dummy-key",
        fetcher=lambda _url, _timeout: next(responses),
    )

    assert source.poll() == []
    messages = source.poll()

    assert len(messages) == 1
    assert messages[0].sender == "기상청 국외지진 정보"
    assert messages[0].level == Priority.HIGH
    assert "국내 최대진도: Ⅴ" in messages[0].text
