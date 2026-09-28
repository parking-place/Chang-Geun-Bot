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

## p6 — Jev 질문 묶음과 재해석 패스

- [TypeSafe 공식 API](https://docs.typesafe.ai/api)와 [Primitives](https://docs.typesafe.ai/primitives)의 현재 문서를 확인해 동일 HTTP 요청의 named 질문·Choice `choice/probabilities/confidence`·Noul `noul`·usage 형태를 검증했다. 신규 `HostedParserProvider`는 Jev 질문만 전송하고 질문 키/선택지/분포/타입 불일치를 거부한다. 외부 API 실호출은 아직 하지 않았다.
- `JevInterpreter`는 두 패스에서 같은 코드로 입력 성격+허용 명령 전체를 묶고, 실제 목록/원문값의 인수 질문을 한 번에 묶는다. 목록 선택 후 entry가 새로 생길 때만3차를 사용한다. 재해석 패스에서 명령을 다시 고르고, 복합/비명령은 실행 초안으로 만들지 않는다. `ParserSession`은 기존 내부TLS 자격정보를 재사용해 parser-api-v2 root/응답 결합과 취소를 수행한다.
- 지정LXC 고정 DB/HTTP mock의 신규8시험 PASS, 신규 모듈 Ruff/mypy PASS. 후보 선택 뒤 실제 실행 검증은p9, 목록형 Noul 복수선택·전체47명령/옵션 정확도·실제Jev 성능과 품질은 미완료다. GPT 실호출0, Jev 실호출0.

## p7 — GPT-5 nano 교체 프로필과 구조화 출력

- [OpenAI 공식 GPT-5 nano 모델 문서](https://developers.openai.com/api/docs/models/gpt-5-nano)의 2026-09-28 조회값인 입력 $0.05/100만 토큰·출력 $0.40/100만 토큰, Responses·Structured Outputs 지원을 확인했다. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)와 [Responses 이관 문서](https://developers.openai.com/api/docs/guides/migrate-to-responses)의 `text.format` strict JSON Schema·`store=false` 계약을 사용한다. 가격 버전은 코드에 고정하며 실제 검증 전 재확인한다.
- `disabled`/`gpt-5-nano`/미구현 프로필을 명시 구분한다. bot의 등록부에서 rewrite와 full_parse 엄격 스키마를 만들고 실제 목록 opaque ID만 후보로 넣는다. gateway REST 어댑터는 도구 없이 고정 Responses endpoint에 단회 전송하며 사용량을 먼저 수집하고 거절·미완료·스키마 오류를 실행 불가 상태로 기록한다. gateway v2 원장은 예약금액과 확인된 실비를 분리하고 사용량 불명은 0원으로 바꾸지 않는다.
- 사용자 지정 US$1은 모든 요청/재시작에 걸친 **누적 예약 상한**이다. 최대 입력 byte와 출력 토큰, 캐시 할인 없는 표준 단가·입력 byte당 2토큰 보수적 계산으로 송신 전 최악 금액을 예약한다. 이 검증에는 HTTP mock만 사용했고 GPT 실호출0·실제지출0, gateway 활성값도 불변이다.
- 지정 LXC의 신규 스키마2·어댑터/프로필3·기존 v2 예산/서비스8 = 관련13 PASS, 새 파일 Ruff/mypy PASS. 실제 키 접근·모델 권한·정식 비용 정산/장애 분기·47명령 전수 스키마·p10 trace 연계는 남았다. 사용자가 지정한 `.private` GPT 정보 파일 권한은 키 값을 출력하지 않고 0600으로 제한했다.

## p8 — rewrite·재해석·full_parse 유한 전이

- 초기 Jev 성공은 바로 초안으로, 실제 누락/복합/권한·목록 오류는 질문/거부로 종료한다. 해석 실패만 rewrite 한 번, 보호 리터럴·숫자·부정/전체 범위 보존 검사 뒤 Jev 재해석으로 보낸다. 동일문장/거부된 rewrite는 재해석을 생략하고 원문 full_parse로 간다. 서로 다른 명령 선택은 확인 요청으로 멈춘다.
- Jev 가용성 장애의 원문 full fallback은 명시 설정이 켜진 경우만 허용한다. full_parse는 실제 scoped 목록을 새 opaque ID로 만들어 보내고, 후보밖 ID/원문 밖 값·query만 있는 결과는 실행 초안으로 채택하지 않는다. LLM 최종 초안은 Jev 부분 결과와 병합하지 않으며 `llm_assisted`를 보존한다.
- 지정 LXC mock의 신규 전이8·LLM 계약2·Jev 회귀4 = 관련14 PASS, Ruff/mypy PASS. 원문 의미 보존의 완전 증명·전체 실패 전이·실제8회 root 통합/후속 Discord 실행 검증은p9~p11에 남았다. 현재 활성 bot/gateway에는 연결하지 않았다.
