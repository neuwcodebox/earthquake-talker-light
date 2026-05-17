# earthquake-talker-light

기상청 지진 관련 정보를 수집해 텔레그램 채널로 보내는 경량 Python 봇입니다.

## 실행

먼저 예제 파일을 복사해 값을 채웁니다.

```bash
cp .env.example .env
```

```bash
TELEGRAM_BOT_TOKEN=... \
TELEGRAM_CHAT_ID=... \
KMA_API_KEY=... \
uv run python main.py
```

프로젝트 루트의 `.env` 파일도 자동으로 읽습니다.

텔레그램 전송 없이 동작을 확인하려면 `DRY_RUN=1`을 사용합니다.

```bash
DRY_RUN=1 uv run python main.py
```

PEWS 과거 자료를 재생하려면 `.env`에 아래처럼 설정합니다. `PEWS_SIMULATION`은 `지진ID:시작시각` 형식이고, 시작시각은 KST 기준 `yyyyMMddHHmmss`입니다.

```dotenv
DRY_RUN=1
PEWS_SIMULATION=2017000407:20171115142931
```

## 환경변수

- `TELEGRAM_BOT_TOKEN`: 텔레그램 봇 토큰. `DRY_RUN=1`이 아니면 필수입니다.
- `TELEGRAM_CHAT_ID`: 메시지를 보낼 채팅 또는 채널 ID. `DRY_RUN=1`이 아니면 필수입니다.
- `KMA_API_KEY`: 기상청 APIHub 국외 지진 조회 키. 없으면 국외 지진 수집원이 비활성화됩니다.
- `OUTPUT_DIR`: 진도 그리드 이미지 저장 경로. 기본값은 `output`입니다.
- `MICRO_INTERVAL_SECONDS`: 미소지진 조회 주기. 기본값은 `10`입니다.
- `PEWS_INTERVAL_SECONDS`: 국내 지진 속보 조회 주기. 기본값은 `1`입니다.
- `OVERSEAS_INTERVAL_SECONDS`: 국외 지진 조회 주기. 기본값은 `30`입니다.
- `POLL_INTERVAL_SECONDS`: 메인 루프 sleep 주기. 기본값은 `1`입니다.
- `PEWS_SIMULATION`: PEWS 시뮬레이션 설정입니다. `지진ID:yyyyMMddHHmmss` 형식입니다.

상세 사양은 [SPEC.md](SPEC.md), 진행 계획은 [PLAN.md](PLAN.md)를 참고하세요.
