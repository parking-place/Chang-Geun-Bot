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

## p9 — 검증·단회 후속 입력 개발 체크포인트

- 공통 초안 검증기는 registry 타입·권한·주시 허용·원문 구간·목록 선택 토큰의 root/pass/scope/revision을 검사한다. 호출 직전 최신 actor와 목록을 다시 조회하며 확인 없는 쓰기 호출을 차단한다. provider가 만든 `context` 근거는 신뢰하지 않고 요청자·서버·채널·명령·인수·값과 일치하는 서버 생성 typed 문맥만 허용한다.
- 60초 typed 후속 답변은 원래 대기 인수로만 결정적으로 변환하며 모델을 호출하지 않는다. 300초 확인은 별도의 원자적 단회 토큰이다. 새 대기 요청은 같은 채널·사용자의 이전 토큰을 폐기하며 프로세스 재시작은 모든 메모리 대기를 무효화한다. 명령 초안에서 생략한 선택 인수에만 코드 기본값이 적용된다.
- DiscordBotLXC에서 신규 안전 시험7과 기존 Jev/오케스트레이터12를 합친 관련19 PASS, parser Ruff/mypy PASS. 이 결과는 대역·격리 DB 시험이며 실제 Discord 버튼/후속 답변 처리, C01~C47 및 I01~I08 전수 parity, 역할·주시·voice 변경의 실제 인수는 **NOT_RUN**이다. 현재 활성 bot/gateway에는 연결하지 않았다.

## p10 — 별도 trace 저장소 개발 체크포인트

- 업무 DB·gateway 예산 원장과 분리된 private SQLite/WAL trace-v2 파일을 추가했다. 최초 수신 시각과 정확한 7일 만료는 UPDATE trigger로 불변이며 모든 구현 조회가 만료를 필터한다. 시작 시 만료 부모·자식을 cascade 삭제하고 알 수 없는 기존 스키마는 자동 덮어쓰지 않는다. 입력·이벤트는 secret key/value/URL query를 제한적으로 마스킹한 후 저장한다. `executed_command`는 서비스 전달을 기록할 때만 설정하고 확인 대기는 null로 둘 수 있다.
- 지정 DiscordBotLXC 격리 파일에서 경계 전/정확히 만료/삭제, TTL 불변, 호출·이벤트 요청 소속, 중복 call 거부, usage token 부분집합, 비밀 문자열 기본 마스킹, 미확인 usage, 기존 스키마 거부의 신규4시험 PASS. Ruff/mypy PASS. 이 시험에서 원격 모델 호출0·실제 지출0.
- 제한: 로거는 아직 활성 봇·gateway에 연결되지 않았다. bounded writer/매시간 정리·모든 사본/내보내기·실제 시크릿 전체 패턴·관리자 화면·trace v1 이관은 **NOT_RUN**이다. `secure_delete`와 조회 차단만으로 물리 사본 삭제를 보증하지 않으며 외부 백업 검증은 사용자 지정대로 SKIPPED다.

## p11 — 동일 후보의 소스·설치 wheel 회귀 체크포인트

- 고정 입력: p10 제품 소스 commit `8ee7006`, 공개 소스 manifest SHA256 `802cd2c6a813b3426625428accdb1b8973ebd46428fabcd493f8d217dee09c03`. DiscordBotLXC 전용 격리 경로 `/opt/changgeun-dev/p11-8ee7006/`에서 setuptools 84.0.0 격리 빌드로 새 wheel을 생성했다. bot wheel SHA256 `fd425c5aac4d6d085c0e1c0c80ccc02bc253efc7fa1bd0599b89e4e37a7c7400`, inference wheel SHA256 `99a78b56ad1ddc6acff313764183f585abe12479d37a9a755102770d8ccf44b9`.
- 지정 LXC에서 `PYTHONPATH=bot/src:inference/src` 소스 우선 `pytest tests -q` **476 PASS**, 전체 Ruff PASS, mypy `bot/src inference/src` **64파일 PASS**. 새 wheel은 기존 서비스/venv를 건드리지 않는 `site` 격리 경로에 `pip install --no-deps --no-index --target`로 설치했다. 두 패키지 import가 그 설치 경로를 가리키는 것을 확인하고 `PYTHONPATH=/opt/changgeun-dev/p11-8ee7006/site`로 같은 `pytest tests -q` **476 PASS**를 실행했다. Discord 라이브러리의 deprecation warning268건은 남았다.
- 기존 `changgeun-dev-bot`와 `changgeun-jev-api`는 시험 뒤 모두 active였다. 새 wheel 적용/봇 전환은 하지 않았다. 최초 빌드 시 기존 개발 venv에 setuptools가 없어 `--no-isolation` 시도가 실패했고, 격리 빌드로 해결했다. 신규 wheel venv에는 pytest가 없어 그 시도는 시험 결과로 세지 않았으며, 위 `--target` 검증만 PASS로 기록했다.
- **NOT_RUN:** C01~C47/I01~I08 옵션·UI 전수 대응, 신규 독립221문장과 정답잠금·실제 Jev/GPT 통합 품질·지연/비용, synthetic shadow 및 trace 이관/복귀. GPT 실호출·실제지출은 이번 단계까지0이고 사용자 지정 누적US$1 상한을 유지한다. 이전 실패·백업 검증 SKIPPED는 변경하지 않는다.

## p12 — 명시적 gateway v2 시작 옵션 준비 체크포인트

- p11의 독립 품질·이관/복귀 게이트가 아직 충족되지 않아 활성 봇/gateway와 Discord 서버 설정을 변경하지 않았다. 대신 gateway가 기본값으로 기존 API1.2만 제공하고, `--parser-v2`와 명시적 LLM 프로필을 지정한 경우에만 v2를 만들도록 했다. v2는 Jev API·영속 tombstone을 요구하고 구/신 API가 하나의 dispatch semaphore를 공유한다. `disabled`는 OpenAI 키 없이, `gpt-5-nano`는 키 누락 시 시작 전 실패하도록 했다.
- 지정 DiscordBotLXC의 mock 서버 시작/인증/health/usage 격리 시험1 PASS, 신규 전체 source·설치 wheel 각각 **477 PASS**, 전체 Ruff·mypy64파일 PASS. p12 제품 소스 manifest SHA256 `9d388044471a0370d899a0cc2d8de0d6bdaf5d6d0d47c1f11d71e931b732f899`; 테스트-only 보강 뒤 manifest `94cd52f8aafa19ca63a7b75d3faa4149f19c7a7b852ee140398a194641ef96a3`으로 변경했고 해당 보강은 source/wheel 단일 시험 각각 PASS다. bot wheel SHA256 `0e5581221d6555a4c78648b09542fbcded3c8834958328a22b403fcc14eff0e5`, gateway wheel SHA256 `7e1eb594bcc696f99c3e1f2de17994f1e0adb5262f1d3f323e74c89b62e471fd`. 두 패키지 import는 격리 설치 `/opt/changgeun-dev/p12-9734d7e/site`를 가리켰다.
- **NOT_RUN:** 실제 키·GPT 비용(실호출0/지출0), 새 bot 진입점과 CommandService/Discord 확인 UI 연결, 독립221 평가, trace 운영 worker/이관, 사용자의 실제 Discord 조작·청취, 후보 전환/복귀. p12는 개발 준비 체크포인트이며 버전 전체 DONE이나 정식 출시가 아니다. 사용자 지정 GPT 누적지출US$1·백업검증SKIPPED를 유지한다.

## p12a — 기본 비활성 bot v2 bridge 개발 체크포인트

- `commands.natural_parser_version`은 기본 `v1`, 명시 `v2`에만 새 parser bridge를 생성한다. `parser_llm_fallback`은 기본 `disabled`이며 v1+LLM이나 gateway 없는 v2 설정은 시작 전 거부한다. 샘플 설정도 v1을 유지했다. 활성 LXC 설정·서비스는 변경하지 않았다.
- 격리된 v2 bridge는 원문 body→ParserSession/Jev→공통 검증기→기존 CommandService callback 경로를 연결한다. 모델은 실행기를 선택하지 못한다. 읽기 명령 C01의 대역 실행을 확인했고, 쓰기는 300초 확인 버튼/단회 token·fresh actor/목록 재검증을 거친다. 다른 사용자 클릭이 토큰이나 버튼을 소모하지 않도록 수정했다. 접두어 실행 콜백에는 admitted request ID를 전달해 기존 업무 멱등성을 사용한다.
- 지정 DiscordBotLXC 소스 **480 PASS**, Ruff PASS, mypy **65파일 PASS**. 새 격리 설치 wheel에서 두 패키지 import 경로를 확인하고 동일 **480 PASS**. 제품 소스·시험 manifest SHA256 `665f99feafba194c7e9bda4813a8cd5c21632bc652f6bcc073d92b76a5f75db5`(시험 import 순서 정리 뒤 최종 동기화); bot wheel SHA256 `d68bd5fd1e2581609adb02a7282e395e370fec0e71b5299bc73ad31523b606d1`, gateway wheel SHA256 `2a7ca9db82010d0c510595490291a755fa41a946ccc44f627f2fa1e38f46e854`.
- **NOT_RUN:** 실제 Jev/GPT·비용, typed 60초 Discord 질문 UI, C01~C47/I01~I08 전수 옵션·confirmation parity, 전체 주시/voice 경합, 독립221 품질, trace 운영 연결·이관, 실제 Discord 조작/청취·후보 전환. 이 bridge는 기본 비활성이므로 소스/대역 통과를 활성 봇 인수로 읽지 않는다. GPT 실호출·지출0, 사용자 지정 US$1 상한 유지.

## p12b — 한 인수 typed 모달과 gateway 프로필 결합 체크포인트

- Jev 인수 묶음에서 필수값 하나만 누락되고 미래의 의존 인수가 없으면 원래 root/command/pass와 나머지 검증 가능한 인수를 보존한 부분 초안을 낸다. Discord는 60초 owner-only 모달을 제공한다. 답변은 해당 인수 타입으로만 결정적으로 해석하고 `TrustedContext`로 원 요청자·서버·채널·인수·값에 결합한다. 후속 모델 호출은 없다. 쓰기는 별도의 300초 단회 확인 뒤 fresh actor/목록 검증을 다시 거친다. 여러 필수값 누락이나 의존 인수는 자동 보완하지 않는다.
- 봇의 v2 opt-in 시작은 gateway 인증 health의 v2 readiness와 `disabled`/`gpt-5-nano` 프로필 일치 확인에 묶었다. v1 서비스에는 새 검사를 적용하지 않는다. 키 없는 disabled/프로필 불일치 시험을 LXC 대역에서 수행했다. 실제 활성 프로필·서비스는 변경하지 않았다.
- 지정 DiscordBotLXC의 같은 공개 소스 manifest SHA256 `58e43be574967f0f7eb5b56ea389208da1ec2466d31e48af2f29b822d22708a5`에서 source·새 격리 설치 wheel 각각 **483 PASS**, 전체 Ruff PASS·mypy65파일 PASS. wheel import가 격리 `site`를 가리켰다. bot wheel SHA256 `89e9e474a445e344d988f012499d6d65176f546d6e549c408234008c42b6fe1e`, gateway wheel SHA256 `a3a0af4563548ce2a0864e93e43d1e67aa33ca4beb20d993c7c45ad95313896b`.
- **NOT_RUN:** 다중/의존 인수 typed 해소·실제 목록 동명 선택 UI, 전체47명령/8후속 parity, 실제 Jev/GPT 실호출 및 비용(누적0/US$1 상한), 독립221·trace 운영/이관·실제 Discord 청취/조작·활성 전환/복귀. p12b는 개발 후보이며 버전 완료/출시가 아니다.

## p12c — opt-in trace 관측 연결 체크포인트

- v2 봇은 private 절대 경로의 독립 SQLite trace 파일을 명시해야 시작한다. symlink와 공개 디렉터리는 거부한다. 자연어 입장 후 원문은 제한적 마스킹 사본으로 저장하고 정규화·stage 생략·호출별 usage·parser/확인 대기·서비스 전달 상태를 기록한다. gateway 실패 응답의 usage도 호출 ID에 한 번 보존하고 trace 쓰기 실패는 카운트하되 모델/명령을 다시 실행하지 않는다. 시작 시 만료 정리와 주기적 배치 정리를 추가했다.
- 지정 DiscordBotLXC의 동일 소스 manifest SHA256 `f905ad6a60efb2f3ce0aa952e61144f3c166001737761c39abc7a6e0a1a917a4`에서 source·새 격리 설치 wheel 각각 **485 PASS**, 전체 Ruff PASS·mypy65파일 PASS. wheel import는 격리 `site`를 가리켰다. bot wheel SHA256 `3d1d992b7f257be3df6898949c3222f7c03b23b3f366a6235e802a32b0fc1b17`, gateway wheel SHA256 `2f7958626353ee5bc122c393e0e166590c5ef54bd3675ba150c98df4a1ad91e7`.
- **NOT_RUN:** bounded 비동기 writer·모든 실패 최종 상태·관리자 조회/export·trace v1 이관/복귀·사본의 실제 만료, 전체47명령/8후속 parity, 독립221·실제 Jev/GPT 호출/US$1 비용·실제 Discord 인수/전환. 로그 단위시험으로 운영 보관 게이트를 PASS로 표시하지 않는다. 활성서비스·GPT 실호출/지출0 유지.
