# Earthquake Talker Light 사양

## 목표

`earthquake-talker-light`는 기상청 지진 관련 정보를 주기적으로 수집해 텔레그램 채널로 전송하는 Python 봇이다. 장기 실행에 필요한 상태 저장과 실패 복구는 단순한 파일 기반으로 처리한다.

## 범위

구현 대상은 다음 세 가지 수집원이다.

1. 미소지진 안내
   - URL: `https://www.weather.go.kr/w/wnuri-eqk-vol/eqk/eqk-micro.do`
   - HTML을 텍스트로 정규화한 뒤 `지진` 또는 `여진`이 포함된 최신 안내가 이전 안내와 다르면 전송한다.
   - 최초 실행 시 발견한 기존 안내는 상태에 저장만 하고 전송하지 않는다.

2. 국내 지진 신속/상세정보
   - 기본 데이터 경로: `https://www.weather.go.kr/pews/data`
   - 현재 UTC 시각에서 서버 오프셋을 뺀 `yyyyMMddHHmmss` 파일명을 사용해 `.b` 바이너리 파일을 조회한다.
   - `.b` 파일 헤더로 단계와 관측소 목록 갱신 여부를 판정한다.
   - 단계 판정:
     - phase 1: 지진 정보 없음 또는 실시간 감시 값
     - phase 2: 지진 신속정보
     - phase 3: 지진 상세정보
   - phase 2/3일 때 본문 끝의 고정 길이 비트 필드와 60바이트 안내 문자열을 파싱한다.
   - 동일 `지진ID + phase` 조합은 한 번만 전송한다.
   - phase 2 메시지는 Critical, phase 3 메시지는 High 우선순위로 전송한다.
   - 위치 보정용 `지진ID.le` 또는 `지진ID.li` JSON에 `info_ko`가 있으면 안내 문자열 대신 사용한다.
   - phase 2/3 이벤트는 진도 그리드 파일도 조회해 이미지로 생성 후 텔레그램에 함께 전송한다.
     - phase 2: `{지진ID}.e`
     - phase 3: `{지진ID}.i`
     - 4비트 단위 MMI 값을 지도 격자에 색칠하고 진앙 표시를 찍어 PNG를 만든다.
     - 기본 지도 오버레이는 패키지 내부 `earthquake_talker_light/assets/map.png`를 사용한다.
   - 관측소 실시간 진도 요약은 C# 구현상 법적 문제 주석으로 전송이 비활성화되어 있으므로 이번 Python 버전에서도 전송하지 않는다. 다만 `.s` 관측소 갱신과 PEWS phase 파싱에는 영향이 없도록 필요한 최소 상태만 유지한다.

3. 국내 영향이 있는 국외 지진
   - URL: `https://apihub.kma.go.kr/api/typ09/url/eqk/urlNewNotiEqk.do`
   - 환경변수 `KMA_API_KEY`가 있을 때만 활성화한다.
   - 요청 파라미터:
     - `orderTy=xml`
     - `frDate`: KST 기준 전날 `yyyyMMdd`
     - `laDate`: KST 기준 당일 `yyyyMMdd`
     - `cntDiv=N`
     - `authKey`: `KMA_API_KEY`
   - XML의 `info` 노드를 읽고 `cntDiv`가 `N`이 아닌 항목은 제외한다.
   - 국내 영향 조건은 국내 최대진도(`jdLoc`)와 지역별 진도(`jdLocA`)가 모두 존재하는 것이다.
   - 이벤트 ID는 `eqDate + tmIssue`의 숫자 문자열 조합이다.
   - 최초 실행 시 기존 항목은 상태에 저장만 하고 전송하지 않는다.
   - 3일보다 오래된 상태는 정리한다.

## 텔레그램 전송

환경변수로 설정한다.

- `TELEGRAM_BOT_TOKEN`: 필수
- `TELEGRAM_CHAT_ID`: 필수
- `KMA_API_KEY`: 국외 지진 수집에만 필요
- `STATE_PATH`: 기본값 `.state/earthquake_talker_state.json`
- `OUTPUT_DIR`: 기본값 `output`
- `POLL_INTERVAL_SECONDS`: 전체 루프 기본값 `1`
- `MICRO_INTERVAL_SECONDS`: 기본값 `10`
- `PEWS_INTERVAL_SECONDS`: 기본값 `0.5`
- `OVERSEAS_INTERVAL_SECONDS`: 기본값 `60`
- `DRY_RUN`: `1`, `true`, `yes`이면 텔레그램 API 호출 대신 콘솔 출력

메시지 우선순위에 따라 텔레그램 `disable_notification`을 정한다.

- `Critical`, `High`: 알림 활성화
- `Normal`, `Low`: 알림 비활성화

이미지 메시지는 `sendPhoto`를 사용하고, 일반 텍스트는 `sendMessage`를 사용한다.

## 상태 저장

파일 기반 JSON 상태를 사용한다. 종료와 재시작 사이에 최소한 다음 값을 보존한다.

- 미소지진 최신 텍스트 해시 또는 전문
- PEWS 마지막 알림 ID
- 국외 지진 seen map

쓰기 실패가 전체 루프를 중단시키지 않도록 임시 파일에 쓴 뒤 원자적 교체를 시도한다.

## 실패 처리

- HTTP 요청은 타임아웃을 둔다.
- 개별 수집원 실패는 로그로 남기고 다음 루프에서 재시도한다.
- 텔레그램 전송 실패는 제한된 횟수로 재시도한다.
- 기상청 PEWS 초 단위 파일이 없는 경우 정상 상황으로 보고 조용히 다음 tick으로 넘어간다.

## 비목표

- Twitter, FCM, GUI 컨트롤러, 사용자별 구독 관리, 장기 큐 서버, 지진해일/뉴스/일반 국내 지진 페이지 수집은 구현하지 않는다.
- 관측소 실시간 진도 요약 메시지는 이번 범위에서 전송하지 않는다.
- PEWS 비공식 바이너리 포맷은 참고 구현과 동일한 수준으로만 해석한다.
