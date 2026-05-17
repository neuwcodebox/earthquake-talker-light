# earthquake-talker-light

기상청 지진 관련 정보를 수집해 텔레그램 채널로 보내는 경량 Python 봇입니다.

## 실행

```bash
TELEGRAM_BOT_TOKEN=... \
TELEGRAM_CHAT_ID=... \
KMA_API_KEY=... \
uv run python main.py
```

텔레그램 전송 없이 동작을 확인하려면 `DRY_RUN=1`을 사용합니다.

```bash
DRY_RUN=1 uv run python main.py
```

## 환경변수

- `TELEGRAM_BOT_TOKEN`: 텔레그램 봇 토큰. `DRY_RUN=1`이 아니면 필수입니다.
- `TELEGRAM_CHAT_ID`: 메시지를 보낼 채팅 또는 채널 ID. `DRY_RUN=1`이 아니면 필수입니다.
- `KMA_API_KEY`: 기상청 APIHub 국외 지진 조회 키. 없으면 국외 지진 수집원이 비활성화됩니다.
- `STATE_PATH`: 상태 파일 경로. 기본값은 `.state/earthquake_talker_state.json`입니다.
- `OUTPUT_DIR`: 진도 그리드 이미지 저장 경로. 기본값은 `output`입니다.
- `MICRO_INTERVAL_SECONDS`: 미소지진 조회 주기. 기본값은 `10`입니다.
- `PEWS_INTERVAL_SECONDS`: 국내 지진 속보 조회 주기. 기본값은 `0.5`입니다.
- `OVERSEAS_INTERVAL_SECONDS`: 국외 지진 조회 주기. 기본값은 `60`입니다.
- `POLL_INTERVAL_SECONDS`: 메인 루프 sleep 주기. 기본값은 `1`입니다.

상세 사양은 [SPEC.md](SPEC.md), 진행 계획은 [PLAN.md](PLAN.md)를 참고하세요.
