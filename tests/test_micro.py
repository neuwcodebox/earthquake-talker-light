from earthquake_talker_light.sources.micro import KmaMicroSource, html_to_text


def test_html_to_text_normalizes_kma_micro_html() -> None:
    html = "<html><body><h1>미소지진</h1><p>포항 인근&nbsp; 여진 안내</p></body></html>"

    assert html_to_text(html) == "미소지진 포항 인근 여진 안내"


def test_html_to_text_preserves_br_as_newline() -> None:
    html = (
        '<p class="p_hypen"><span style="color:#0000ff; font-weight:bold;">'
        "[최근 미소지진 발생 현황(규모 2.0미만)]</span><br/> "
        "2026/05/17 05:08:57 경북 울진군 북쪽 0.7km 지역 "
        "&#40;규모:0.9 / 깊이:9km&#41;</p>"
    )

    assert html_to_text(html) == (
        "[최근 미소지진 발생 현황(규모 2.0미만)]\n"
        "2026/05/17 05:08:57 경북 울진군 북쪽 0.7km 지역 (규모:0.9 / 깊이:9km)"
    )


def test_micro_source_skips_initial_then_emits_changed_notice() -> None:
    responses = iter(
        [
            "<p>첫 지진 안내</p>",
            "<p>새 지진 안내</p>",
        ]
    )
    source = KmaMicroSource(fetcher=lambda _url, _timeout: next(responses))

    assert source.poll() == []
    messages = source.poll()

    assert len(messages) == 1
    assert messages[0].sender == "기상청 미소지진 안내"
    assert messages[0].text == "새 지진 안내"
