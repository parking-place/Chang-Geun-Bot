# 1.2.0 재구성 단계 실행 기록

사용자 요청으로12단계를 구현하며 각 단계 체크포인트를 `v1.2.0-p1`부터 GitHub에 올린다. 태그는 개발 단계 산출물 식별자이며 제품 전체/정식출시 PASS가 아니다. 기존1.1.x 실패·미완료·백업검증SKIPPED는 보존한다.

## p1 — 기준선과 신규 계약

- 시작 소스:474dad904466f0cce0817f7ac2527e4b86d9264c. 기존 계획 변경을 `pre-reconstruction-1.2.0-plans-20260928` stash로 보존하고 `codex/reconstruction-1.2`에 복원했다.
- DiscordBotLXC 실제 확인:bot patch117b / 실행 gateway patch116g. runtime metadata의 gateway 경로는 과거dev20260928l로 남아 있어 실행 unit 기준으로 구분했다. metadata만 보고 새시험 Python을 고르지 않는다.
- 기존 내부TLS readiness PASS, 실제 provider dispatch0. 고정epoch의 Jev 예약640/3000. 업무command_requests와 message_requests 등 기존DB 보존, 모델/API 실호출 없음.
- 새 parser-api-v2 root/call/question/usage 계약과 공급자 독립 봇 초안/결과/포트, 요청/응답 JSON Schema 추가. API1.2·기존서비스 활성값은 그대로 유지한다.
- LXC source 계약시험3 PASS:구버전 분리·35초/finite기한·pass/stage/operation 제약·묶음질문·255한도·usage null/부분집합. 신규파일 Ruff PASS.
- 원본 재구성명세SHA256은70bc3e9b63fbbd3b6b52589289852a7aac123baa139e57487e0d58be071f3a2c로 보존했다.
- 판정: p1 계약 코드/문서 검토·제한LXC 검증. 전체명령 전수/실제파서/과금API/Discord 인수는 후속단계다.

실제 실행: `scripts/remote.py`로 공개소스를 전송한 뒤 지정LXC에서 source PYTHONPATH의 `tests/safety/test_parser_v2_contracts.py`를 실행했다. 제품시험은 로컬에서 실행하지 않았다.

## p2 — 실제 slash 정의 기반 등록부와 공통 호출

- 실제47개 slash 말단 정의의 모든 인수/기본값/타입을 typed registry로 가져오고 재생목록·곡·채널·entry의 실제목록 resolver를 선언했다. 별도 모델용 인수명/개수를 수작업으로 복제하지 않는다.
- 닫힌 CommandService는 등록된 같은callback만 호출하며 C39재귀/권한/타입/범위/재생·import양자택일을 검증한다. 신규파서 연결은p9에 수행한다.
- DiscordBotLXC 신규등록부+기존어댑터/자연어 회귀45 PASS, 신규파일Ruff·mypy PASS. 실제Discord 인수/전체옵션 의미정확도는 아직아니다.
- 사용자 지정 GPT 실호출 검증 누적 지출상한 **US$1**. 예약/실패/unknown을 포함한 영속금액원장을 적용하며 추가승인없이 증액하지 않는다.

## p3 — 보수적 정규화와 원문 위치 보존

- 2026-09-28 사용자 재개 지시 후 p1/p2 작업 트리와 지정 DiscordBotLXC readiness를 재확인했다. 제품 API 실호출 없이 health 점검만 수행했다.
- `InputNormalizer`는 확인된 시작 접두사만 제거하고 원문을 별도 보관한다. 정확한 기존 이름, 따옴표/닫히지 않은 인용, URL, Discord 멘션을 보호한다. 나머지 공백과 NFC에만 보수적 변환을 적용하며 각 해석 문자에 원문 code point 구간을 붙인다. 원문 인용 검증은 실패 시 닫힌다. `code.normalize` 이벤트에는 원문 없이 규칙/시간/보호 수만 보낸다.
- 지정 LXC의 source에서 한글·복수 공백·scheme 없는 YouTube URL·멘션·조합형 한글·이모지·반복값·500회 무작위 Unicode 범위 시험 등 신규10 PASS, mypy PASS. 실제 Discord 연결과 원문값의 의미 검증은 p4/p9에서 계속한다. 모델 호출0.

## p4 — 실제 목록 스냅샷과 새 값의 원문 근거

- 지정 DiscordBotLXC 격리 DB에서 서버별 재생목록·곡·목록entry·대기열·제안·변경 목록을 조회한다. Discord 채널은 현재 guild/member 권한과 음성채널 정책으로 거른다. 선택 토큰은 내부 ID를 노출하지 않고 root/pass/argument/scope/revision에 묶는다. 동일 곡의 서로 다른 entry와 실제 번호를 별도로 보존한다.
- 전체 목록을 포함할 수 없으면 `collection_overflow`로 종료한다. 실제 252항목+예약3개=255 경계, 253항목 거부, byte 한도, 빈 목록, 타 서버/타 패스 토큰·권한거부·revision 변경을 격리 시험했다. 기존 값을 문장 구간 유사도 top-k로 추려 보내지 않는다.
- 신규값은 인용·URL·멘션·숫자·연속 텍스트 구간에서 원문 위치와 함께 만든다. 값 추출과 실제 목록 선택은 다른 경로다. 모델/Jev 호출0, 신규 LXC 시험6 PASS, 신규 모듈 mypy/Ruff PASS.
- 제한: 등록부가 선언한 `attachments`와 일부 command별 정책 범위, 실제 Discord 명령 연결 및 실행 직전 객체·권한 재확인은 아직 끝나지 않았다. 스냅샷/값 모듈 통과를 전체 p4 또는 제품 PASS로 표시하지 않는다.

## p5 — 별도 gateway API와 영속8회 원장

- API1.2의 `(request_id,stage)` 표·기존3회/공유 Jev run_budget를 변경하지 않고 `v2_roots`, `v2_calls`, `v2_spend`, 독립 owner tombstone을 추가했다. 최초/재해석 각3회, rewrite/full_parse 각1회, 전체8회가 하나의 root에 묶인다. 전송 후 불명/취소는 슬롯을 환불하거나 자동 재전송하지 않는다.
- GPT-5 nano 검증 금액은 원장에 `micro USD`로 원자 예약하며 전체 상한 **US$1**을 재시작/요청별로 초기화하지 않는다. 이 단계의 LLM 원격 사용은 비활성(`llm_reservation` 미구성)이다. 실제 가격·토큰 상한과 과금 확정은 p7/p10 검증 후에만 연결한다. GPT 실호출0·실제지출0.
- `/v2/parse`, `/v2/cancel`, `/v2/usage`는 선택형 ParserService를 주입할 때만 생성한다. 현재 운영 `main()`에는 주입하지 않았고 기존 API1.2는 그대로다. 한 root의 동일 호출 합류/캐시, 권한 없는 HTTP 거부, 취소 뒤 늦은 결과 거부를 기록형 LXC 대역에서 검증했다.
- 지정 LXC에서 신규 예산5·서비스3·신규계약4·기존 예산13 = 관련25 PASS, 신규 모듈 Ruff/mypy PASS. 재시작 tombstone/병렬 중복/8회/US$1 경계는 mock 예약 증거이며 실제 외부 과금 검증이 아니다. 활성 서비스 배포·실제 Jev/GPT 호출은 아직 없다.
