from __future__ import annotations

from datetime import datetime

from earthquake_talker_light.message import KST, Priority
from earthquake_talker_light.sources.overseas import (
    KmaOverseasEarthquakeSource,
    has_domestic_impact,
    parse_intensity,
    parse_overseas_items,
)


def _xml(*infos: str) -> str:
    return f"<response><body><items>{''.join(infos)}</items></body></response>"


def _info(
    eq_date: str,
    tm_issue: str,
    *,
    jd_loc: str = "Ⅴ",
    jd_loc_a: str = "부산 Ⅱ, 울산 Ⅱ",
    refer: str = "국내 일부 지역에서 진동을 느낄 수 있음",
) -> str:
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
      <jdLocA>{jd_loc_a}</jdLocA>
      <ReFer>{refer}</ReFer>
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


def test_has_domestic_impact_rejects_dash_placeholders() -> None:
    items = parse_overseas_items(
        _xml(
            _info(
                "202605201146",
                "20260520115325",
                jd_loc="-",
                jd_loc_a="-",
            )
        )
    )

    assert len(items) == 1
    assert not has_domestic_impact(items[0])


def test_has_domestic_impact_accepts_either_intensity_field() -> None:
    items = parse_overseas_items(
        _xml(
            _info("202605201146", "20260520115325", jd_loc="Ⅱ", jd_loc_a="-"),
            _info("202605201147", "20260520115425", jd_loc="-", jd_loc_a="부산 Ⅱ"),
        )
    )

    assert len(items) == 2
    assert has_domestic_impact(items[0])
    assert has_domestic_impact(items[1])


def test_parse_actual_overseas_list_shape_and_domestic_impact_values() -> None:
    xml = """
    <alert>
      <earthqueakNoti>
        <info>
          <msgCode>지진정보</msgCode>
          <cntDiv>N</cntDiv>
          <arDiv>S</arDiv>
          <eqArCdNm>기타해역</eqArCdNm>
          <eqPt>일본 나가사키현 대마도 북북동쪽 96km 해역</eqPt>
          <nkDiv>N</nkDiv>
          <tmIssue>20240419233321</tmIssue>
          <eqDate>20240419232754</eqDate>
          <magMl>3.9</magMl>
          <magDiff>0.25</magDiff>
          <eqDt>19</eqDt>
          <eqLt>35.01</eqLt>
          <eqLn>129.64</eqLn>
          <majorAxis>1.48</majorAxis>
          <minorAxis>0.96</minorAxis>
          <depthDiff>1.13</depthDiff>
          <jdLoc>Ⅱ</jdLoc>
          <jdLocA>Ⅱ(경남,경북,대구,부산,울산)</jdLocA>
          <ReFer>지진피해 없을 것으로 예상됨</ReFer>
        </info>
        <info>
          <msgCode>지진정보</msgCode>
          <cntDiv>N</cntDiv>
          <arDiv>S</arDiv>
          <eqArCdNm>기타해역</eqArCdNm>
          <eqPt>전남 신안군 흑산도 서쪽 103km 해역</eqPt>
          <nkDiv>N</nkDiv>
          <tmIssue>20220822133414</tmIssue>
          <eqDate>20220822132926</eqDate>
          <magMl>2.4</magMl>
          <magDiff>0.21</magDiff>
          <eqDt>-</eqDt>
          <eqLt>34.75</eqLt>
          <eqLn>124.30</eqLn>
          <majorAxis>4.24</majorAxis>
          <minorAxis>2.76</minorAxis>
          <depthDiff>4.19</depthDiff>
          <jdLoc>Ⅰ</jdLoc>
          <jdLocA>-</jdLocA>
          <ReFer>지진피해 없을 것으로 예상됨</ReFer>
        </info>
      </earthqueakNoti>
    </alert>
    """

    items = parse_overseas_items(xml)

    assert len(items) == 2
    assert items[0].max_intensity == "Ⅱ"
    assert items[0].intensity_areas == "Ⅱ(경남,경북,대구,부산,울산)"
    assert has_domestic_impact(items[0])
    assert items[1].max_intensity == "Ⅰ"
    assert items[1].intensity_areas == "-"
    assert items[1].depth_km is None
    assert has_domestic_impact(items[1])


def test_overseas_source_skips_initial_and_emits_new_event() -> None:
    now_label = datetime.now(KST).strftime("%Y%m%d%H%M")
    first_xml = _xml(_info(now_label, now_label))
    second_xml = _xml(_info(now_label, now_label), _info(now_label, now_label + "01"))
    responses = iter([first_xml, second_xml])
    source = KmaOverseasEarthquakeSource(
        "dummy-key",
        fetcher=lambda _url, _timeout: next(responses),
    )

    assert source.poll() == []
    messages = source.poll()

    assert len(messages) == 1
    assert messages[0].sender == "기상청 국외지진 정보"
    assert messages[0].level == Priority.HIGH
    assert "국내 최대진도: Ⅴ" in messages[0].text
