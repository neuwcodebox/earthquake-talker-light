# earthquake-talker-light

[EarthquakeTalker](https://github.com/neuwcodebox/EarthquakeTalker)의 가벼운 Python 버전입니다. 기상청 지진 관련 정보를 수집해 텔레그램 채널로 보냅니다.

## 지원 알림

- 기상청 미소지진
- 기상청 실시간 지진감시(PEWS)
- 기상청 국외지진 정보

## 기능

- 텔레그램 메시지 전송
- PEWS 진도 격자 이미지 전송
- 국내 영향이 있는 국외지진만 필터링
- 테스트용 드라이런 모드
- PEWS 과거 사례 재생 모드

## 실행

`.env.example`을 참고해 `.env` 파일을 만든 뒤 실행합니다.

```sh
uv sync
uv run python main.py
```

텔레그램 전송 없이 확인하려면 다음 값을 설정합니다.

```env
DRY_RUN=1
```

## 테스트

```sh
uv run pytest
```
