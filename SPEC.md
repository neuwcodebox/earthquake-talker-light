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
   - 국내 영향 조건은 국내 최대진도(`jdLoc`)와 지역별 진도(`jdLocA`) 중 하나라도 있고, trim 후 `-`만 있는 값이 아니어야 한다.
   - 이벤트 ID는 `eqDate + tmIssue`의 숫자 문자열 조합이다.
   - 최초 실행 시 기존 항목은 상태에 저장만 하고 전송하지 않는다.
   - 3일보다 오래된 상태는 정리한다.

## 텔레그램 전송

환경변수로 설정한다.

- `TELEGRAM_BOT_TOKEN`: 필수
- `TELEGRAM_CHAT_ID`: 필수
- `KMA_API_KEY`: 국외 지진 수집에만 필요
- `OUTPUT_DIR`: 기본값 `output`
- `POLL_INTERVAL_SECONDS`: 전체 루프 기본값 `1`
- `MICRO_INTERVAL_SECONDS`: 기본값 `10`
- `PEWS_INTERVAL_SECONDS`: 기본값 `1`
- `OVERSEAS_INTERVAL_SECONDS`: 기본값 `30`
- `DRY_RUN`: `1`, `true`, `yes`이면 텔레그램 API 호출 대신 콘솔 출력
- 프로젝트 루트의 `.env` 파일을 자동으로 읽는다.
- `PEWS_SIMULATION`: PEWS 과거 자료 재생 설정. `지진ID:yyyyMMddHHmmss` 형식이며 시각은 KST 기준이다.

메시지 우선순위에 따라 텔레그램 `disable_notification`을 정한다.

- `Critical`, `High`: 알림 활성화
- `Normal`, `Low`: 알림 비활성화

이미지 메시지는 `sendPhoto`를 사용하고, 일반 텍스트는 `sendMessage`를 사용한다.

## 실행 중 상태

별도 상태 파일을 만들지 않는다. 각 수집원은 프로세스 메모리에서만 다음 값을 유지한다.

- 미소지진: 실행 후 최초로 얻은 안내를 이전 값으로 초기화하고 전송하지 않는다. 이후 텍스트가 달라질 때만 전송한다.
- PEWS: 실행 중 마지막으로 처리한 초 단위 파일명과 `지진ID + phase` 알림 ID를 기억해 중복 전송을 막는다.
- 국외 지진: 실행 후 최초 조회 결과의 이벤트 ID들을 기존 항목으로 간주하고 전송하지 않는다. 이후 새 이벤트 ID만 전송한다.

프로세스 재시작 시에는 다시 최초 조회 결과를 기준 상태로 초기화한다.

## PEWS 시뮬레이션

`PEWS_SIMULATION`을 설정하면 실시간 PEWS 경로 대신 `https://www.weather.go.kr/pews/data/{지진ID}` 경로를 사용한다.

- 값은 `지진ID:시작시각` 형식이다.
- 시뮬레이션 시작 시각은 KST 기준 `yyyyMMddHHmmss`로 해석한다.
- C# 이전 구현과 동일하게 `.b` 파일 헤더 길이는 1바이트로 처리한다.
- 현재 시각과 시뮬레이션 시작 시각의 차이를 오프셋으로 사용해 과거 초 단위 파일명을 순차 조회한다.
- 300초가 지나면 시뮬레이션을 종료하고 실시간 PEWS 모드로 돌아간다.

## 실패 처리

- HTTP 요청은 타임아웃을 둔다.
- 개별 수집원 실패는 로그로 남기고 다음 루프에서 재시도한다.
- 텔레그램 전송 실패는 제한된 횟수로 재시도한다.
- 기상청 PEWS 초 단위 파일이 없는 경우 정상 상황으로 보고 조용히 다음 tick으로 넘어간다.
- 바이너리 파일은 HTTP 200 OK 응답일 때만 처리한다.

## 비목표

- Twitter, FCM, GUI 컨트롤러, 사용자별 구독 관리, 장기 큐 서버, 지진해일/뉴스/일반 국내 지진 페이지 수집은 구현하지 않는다.
- 관측소 실시간 진도 요약 메시지는 이번 범위에서 전송하지 않는다.
- PEWS 비공식 바이너리 포맷은 참고 구현과 동일한 수준으로만 해석한다.
