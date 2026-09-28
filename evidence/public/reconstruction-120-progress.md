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

## p12d — 활성 gateway의 v2/Jev 제한 시험 체크포인트

- 지정 DiscordBotLXC에서 기존 gateway unit과 공유 Jev 원장을 보존한 채 불변 후보 `recon120p12dgw`를 준비했다. 공개 소스 manifest SHA256 `f92d9348fb3439dc4338b58230362dc3710605bf9068752b594f5b0a041d4c70`, gateway wheel SHA256 `bddc9658ff574aa4fe640e22ef8f4f9a286a27a200318e904d28cc33237f5e75`. 새 설치 wheel의 inference 관련 48시험 PASS. 기존 unit은 `/etc/systemd/system/changgeun-jev-api.service.before-recon120p12dgw`에 보존했다.
- `scripts/switch_single_lxc_gateway.py recon120p12dgw --parser-v2-disabled`로 gateway만 전환했다. 인증된 health에서 기존 v1 `ready`·Jev provider·profile/config binding과 새 `parser_v2_ready=true`, `parser_llm_profile=disabled`를 확인했다. TLS·내부 키 분리·bot/gateway active·공유 예약 640→640을 확인했다. 활성 봇은 기존 `patch117b`이며 새 v2 bot 경로는 사용하지 않는다.
- 합성 문장 2건을 `scripts/probe_parser_v2_jev.py`에서 내부 TLS `/v2/parse`로 각각 **단회** 전송했다. 모호한 “목록 보여줘”는 HTTP200/`completed`/`single`·명령 `__NONE__`, 명확한 “저장된 재생목록 보여줘”는 HTTP200/`completed`/`single`·`C01`. 두 호출 모두 `remote_attempted=true`; 공유 Jev 예약 640→641→642. 공급자 usage는 첫 입력/출력491/91, 두 번째506/91 token이며 total/cached/reasoning은 미제공 null이다. 자동 재시도·GPT 호출은 없었다.
- 이 2건은 wire 계약과 Jev 연결의 제한 smoke이며 독립 품질 점수/47명령 인수가 아니다. 모호한 사례의 `__NONE__`을 성공으로 간주하지 않는다. GPT 실제 검증·누적 지출은 여전히 0/US$1, LLM 프로필은 disabled, 독립221·실제 Discord 신규 경로·격리 이관/복귀는 **NOT_RUN**이다. LXC에서 두 스크립트 Ruff PASS; 로컬 저장소 파일 검사 PASS(제품시험 아님).

## p12e — GPT-5 nano 단회 검증과 reasoning 수정 체크포인트

- [공식 GPT-5 nano 모델 문서](https://developers.openai.com/api/docs/models/gpt-5-nano)의 입력 US$0.05/100만·출력 US$0.40/100만 token과 Responses/Structured Outputs 지원, [GPT-5 공식 가이드](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5)의 `reasoning.effort=minimal`, [reasoning 문서](https://developers.openai.com/api/docs/guides/reasoning)의 reasoning token 과금·`max_output_tokens` 불완료 규칙을 2026-09-28 재확인했다. OpenAI 키는 `.private` 제한 파일에서 SSH stdin으로 gateway 계정의 임시 EnvironmentFile에만 보냈고, 매 시험 뒤 disabled unit으로 복구하며 임시 파일을 제거했다. 키 값은 명령 인수·공개 기록에 없었다.
- 최초 합성 `rewrite`는 기본 reasoning에서 HTTP200/`incomplete`였다. 입력200·출력1024 token 중 reasoning1024, 사용량을 잃지 않고 원장에 실제 US$0.000420을 기록했다. 자동 재시도는 없었다. 이를 계기로 Responses 요청에 `reasoning: {effort: minimal}`을 고정하고 reasoning-only incomplete/단회 과금 회귀를 추가했다.
- 새 불변 gateway 후보 `recon120p12egw` wheel SHA256 `12005fdf5a2dd1e0dc4d69f809c542ae56c257b92390a72500deb841260b1de5`(준비 당시 공개 소스 manifest SHA256 `fb3c8a4f06db8de0acb2f975440d385cda04cc75a1e8e0ff1cc2f2b4e334ff65`)를 적용했다. 이전 unit `/etc/systemd/system/changgeun-jev-api.service.before-recon120p12egw`로 복귀 가능하다. 기존 bot은 계속 `patch117b`다.
- 새 후보에서 합성 `rewrite`는 HTTP200/`completed`, 결과 `needs_clarification`, 입력/출력200/141 token·reasoning0·실제 US$0.000067이었다. 합성 `full_parse`는 HTTP200/`completed`, `parsed`/`C01`, 입력/출력270/50 token·reasoning0·실제 US$0.000034였다. 세 GPT 호출의 누적 예약 **US$0.002005**, 확인된 실제 **US$0.000521**로 사용자 상한 **US$1** 아래다. 각각 별도 root의 initial Jev를 1회씩 썼고 공유 Jev 예약은 642→645/3000이다. 외부 모델 결과를 Discord 명령 실행으로 전달하지 않았다.
- 지정 DiscordBotLXC의 현재 소스 `pytest tests -q` **486 PASS**, 새 gateway 설치 wheel을 우선 import한 동일 시험 **486 PASS**, 전체 Ruff PASS·mypy65파일 PASS. `check_gateway_lifetime.py` TLS/키 분리 PASS, bot/gateway active, 인증서 잔여 약29.37일. 시험 뒤 gateway는 `parser_llm_profile=disabled`, 임시 GPT 키 파일 부재를 확인했고 Jev/GPT 원장 누계는 재시작 뒤에도645·2005/521 micro USD로 유지됐다.
- 이3건은 인증·wire·비용·합성 출력 계약의 제한 시험이다. `needs_clarification`과 `C01` 두 결과를 독립 품질 점수로 일반화하지 않는다. C01~C47/I01~I08 전수·독립221·실제 Discord 신규 경로·trace 완전 보관/이관·정식 출시 게이트는 **NOT_RUN/IN_PROGRESS**이며 백업 검증은 사용자 지정 **SKIPPED**다.

## p12f — 첨부파일 실제 목록과 링크 가져오기 경계 체크포인트

- 등록부 `attachments` 인수가 선언만 되고 resolver에는 없어 v2에서 첨부 가져오기 경로가 미지원이었다. 새 resolver는 **접수된 Discord 메시지의 첨부** ID·파일명·크기만 실제 목록으로 전달하며 URL을 모델에 넣지 않는다. 파서는 원 요청자/guild/channel에 묶인 메시지에서만 첨부를 받고, 실행 직전 동일 ID·목록 revision을 다시 확인한다. 파일이 하나라면 “이 파일” 표현을 허용하고, 여러 파일이면 파일명 언급 또는 신뢰된 선택이 필요하다. 기존 slash callback의 첨부 ID 매핑과 최종 파일 검사는 그대로 사용한다.
- 비어 있는 선택형 첨부 목록은 Jev에서 생략하고 full_parse strict schema에서는 `null`만 허용한다. 이로써 첨부가 없는 링크 가져오기 초안이 불필요하게 전체 실패하지 않으며, 존재하지 않는 첨부를 모델이 만들 수 없다. 실제 첨부를 포함한 Discord 사용자 인수는 아직 수행하지 않았다.
- 지정 DiscordBotLXC에서 새 3통합시험(단일 첨부/URL 비노출·복수 파일 언급·빈 선택형 목록)과 기존 전체를 포함한 source **489 PASS**, 전체 Ruff·mypy65파일 PASS. 새 불변 bot 후보 `recon120p12fbot` wheel SHA256 `02f56b9cabb4f3b7c940f6d4fa0acf3519702ea09daa852030adf3ad766cc5e2`, 공개 소스 manifest SHA256 `806c7dde5ea27260775c19c40ee9da2920b372ac842c4020dacd646660c90276`. YouTube 실행 의존성은 후보에 포함했고 Node/FFmpeg 지문을 후보 manifest에 고정했다. 새 bot wheel·p12e gateway wheel import 경로를 확인한 동일 회귀 **489 PASS**.
- 활성 bot은 계속 `patch117b`, gateway는 `recon120p12egw`/LLM disabled다. 신규 bot wheel은 적용하지 않았다. 이번 단계 Jev/GPT 추가 호출0, 공유 Jev 예약645/3000·GPT 예약/실제2005/521 micro USD 그대로다. 전체 명령/상호작용 parity·독립221·실제 Discord 첨부/가져오기·이관/복귀는 **NOT_RUN/IN_PROGRESS**다.

## p12g — 무관한 빈 목록이 full_parse 전체를 막지 않도록 분리

- p12f까지 `full_parse`의 여러 허용 명령 중 하나라도 필수 목록이 비었거나 scope를 구성할 수 없으면 전체 schema 생성이 중단됐다. 각 명령의 실제 목록을 독립적으로 준비하고 빈 필수 목록·초과 목록·scope 미확정인 명령만 이번 호출의 실행 가능한 분기에서 제외했다. 제외 ID/사유를 모델 상태에 표시하고, 특정 명령의 인수 보수(`repair_arguments`)에서는 해당 명령의 목록 오류를 그대로 질문/종료한다. 사용할 명령이 하나도 없으면 모델을 호출하지 않는다.
- 지정 DiscordBotLXC에서 무관한 빈 재생목록이 C25 읽기 fallback을 막지 않는지, 확인된 C03 보수는 그대로 `collection_empty`로 멈추는지 검사했다. 실제47개 slash 등록부에서 일반 사용자와 DJ/관리자 범위의 strict full_parse schema를 생성해 모양과196608-byte 상한을 검사했다. 이는 schema 생성 가능성이지 해당 명령의 의미 정확도 인수가 아니다.
- 공개 소스 manifest SHA256 `9f6a08ea39bd54e609f7421fafdc3470992ae6ee0d21e642a38fd02524beeccf`, 새 불변 bot 후보 `recon120p12gbot` wheel SHA256 `369972170dd011568fddfc37a460c7fcbefd2d8293dd0bb5055cc5d7b9e56881`. 지정 LXC source 전체 **492 PASS**, 새 bot wheel·p12e gateway wheel 우선 import 전체 **492 PASS**, Ruff PASS·mypy65파일 PASS. bot 서비스는 `patch117b` 그대로이며 이번 단계 외부 Jev/GPT 호출0·원장645/3000 및2005/521 micro USD를 유지한다.
- 여러 명령 중 제외된 명령이 사용자 의도였는지에 대한 품질은 별도 독립평가 대상이다. 전체47명령 옵션/I01~I08·221문장·실제 Discord 신규 후보/인수·trace 운영/이관은 **NOT_RUN/IN_PROGRESS**다.

## p12h — 테스트 서버 개발 봇 v2 전환 (2026-09-28 09:25 UTC)

- 사용자는 테스트 Discord 서버에서 새 후보를 바로 적용하도록 승인했다. 적용 전 활성 봇은 `patch117b`/v1, 중계는 `recon120p12egw`/v2·LLM disabled였다. guild allowlist 1곳, 기존 text/prefix 허용 채널 각2곳, 기존 bot unit SHA256 `ee3dc4d41056c91e85938f9692462c8d56367eb6b20db7cd1f556f6d5f8d94ed`, 설정 SHA256 `33e9fffacfc86bf6a55c68800cbcaaf4deba647e5b1b102bcb12dd737318f7b9`를 확인했다.
- 첫 `recon120p12gbot` 적용은 사전검사에서 **중단**됐다. 해당 불변 manifest가 `/usr/bin/node` v20.19.2를 고정했으나 전환 규칙은 Node22 이상을 요구했다. 서비스 정지/교체는 시작되지 않았다. 기존 활성 재생 설정에서 검증된 Node22.23.3 경로를 선택해 새 불변 후보 `recon120p12hbot`을 만들었다. 새 공개 소스 manifest SHA256 `5874e33864fbbcf45174b9017bc3b5cbc0a3261346a83955ea0fe895aec3074f`, wheel SHA256 `96d2f57d29df7776d7508e5f7f40ae994fe98564aeaab01214658e57d4d5f828`; Node/FFmpeg 해시는 후보 manifest에 고정했다. 설치 wheel import를 우선한 전체 **492 PASS**, source 전체 **492 PASS**, 배포 스크립트 Ruff PASS, 실등록부 공개47명령/인수57개 산출을 확인했다. 등록부 산출은 자연어 기능 인수가 아니다.
- 새 run `recon120p12h-20260928`의 설정을 `natural_parser_version=v2`, `parser_llm_fallback=disabled`, 전용 private trace DB로 고정했다. 봇 계정에서 중계 TLS·binding·v2 profile readiness를 서비스 정지 전후 확인하고, 이전 봇을 정상 정지한 다음 기존 업무 DB의 일관성 사본으로 새 run을 시작했다. 이전 unit은 `/etc/systemd/system/changgeun-dev-bot.service.before-recon120p12hbot`, 이전 DB/바이너리는 기존 run에 보존했다. 새 설정 SHA256 `3d5437a18455af174e5ba733c8a19679108a07a7382d79bf9f16e023d50b5863`이다. 새 서비스 active/MainPID 존재, 이전·새 DB와 trace의 SQLite quick_check `ok`, trace schema v2·private 파일·초기 요청0개를 확인했다. 새 DB에 사용자 변경이 생긴 뒤 구 DB로 단순 복귀하면 변경이 누락되므로, 변경분 이관을 검증하기 전에는 rollback의 데이터 연속성을 PASS로 표시하지 않는다.
- Discord REST에서 현재 봇 토큰의 bot identity와 허용 테스트 서버의 guild 명령 root 25개 등록(목록·주시·재생 포함)을 읽기 전용으로 확인했다. 서비스 활성 시점 이후 journal 오류/exception 0개였다. 사람의 `!!창근아` 입력·slash 비교·음성 청취는 아직 결과를 받지 못했으므로 **NOT_RUN/확인 대기**다. 자동 확인을 실제 사용자 인수로 세지 않는다.
- 중계는 교체하지 않았고 Jev 공유 예약은 **645/3000**, GPT 누적 예약/확인 실제는 **2005/521 micro USD**, 상한 **1,000,000 micro USD**로 전환 전과 동일했다. gateway health의 v2 ready/LLM disabled 및 임시 GPT 키 사본 부재를 확인했다. 이 전환의 추가 외부 Jev/GPT 호출은0이다. 독립221문장·47명령 모든 옵션/I01~I08·trace 운영/이관·실제 Discord 전수/청취·rollback 장애 주입·정식 출시는 **IN_PROGRESS/NOT_RUN**이며 백업 검증은 사용자 지정 **SKIPPED**다.

## p12i — 명령 선택 범위와 조회 질문 보완 (2026-09-28)

- 적용된 p12h parser를 DiscordBotLXC에서 **실행 없이** 실제 Jev로 시험했다. 활성 업무 DB의 SQLite 일관성 사본과 합성 actor를 사용했고 Discord 연결/handler 호출은 없었다. 명확한 읽기 요청 C01/C16/C38 세 건이 각각 `low_confidence`/`not_request`/`low_confidence`로 끝났다. Jev 공유 예약은 **645→648/3000**이다. 이는 품질 실패로 기록하며 봇 배포의 성공으로 덮어쓰지 않는다.
- stage1의 모든 허용 명령을 무조건 제시하던 경로에 기존의 결정적 검색 힌트를 적용했다. 힌트는 실제 허용 등록부와 교집합만 쓰고 없으면 전체 허용 명령으로 돌아가며, `__NONE__`와 `input_kind` 질문을 유지한다. 힌트가 명령을 실행하거나 ID/인수를 생성하지 않는다. 대기열 상태 질문 표현을 힌트에 보강하고, 정보 조회 질문도 단일 요청임을 `input_kind`에 명시했다. LXC 단위/통합 회귀에서 선택지 축소와 Jev 선택 필요성을 확인했다.
- 같은 세 문장을 별도 합성 root로 재시험해 C01/C16/C38을 각각 `parsed`, 실행 전 `DraftValidator` PASS로 확인했다. 예약은 **648→651/3000**이며 GPT 추가 호출0이다. 이 3/3은 개발 smoke이며 독립221문장 또는 전체 명령 정확도 성적이 아니다.
- 새 불변 `recon120p12ibot` 공개 소스 manifest SHA256 `214df611fa8b4add8473f8cc66abfd03d82794e7f9984ecea51077d58619c3ab`, wheel SHA256 `509d6b59557b96872c3d92444c5f6567d9cea1770d7e89bdb9ac24deed47d8bc`. 지정 LXC에서 source **495 PASS**, bot/gateway 설치 wheel 우선 import **495 PASS**, Ruff PASS·mypy65파일 PASS. Node22/FFmpeg 지문을 후보에 고정했다.
- 새 run `recon120p12i-20260928`로 봇을 전환했다. 이전 p12h unit은 `/etc/systemd/system/changgeun-dev-bot.service.before-recon120p12ibot`에, 이전 DB/trace는 원래 run에 보존됐다. 새 설정 SHA256 `a2860576fceec3138b69f90991f999ccd2dc24eb9cb6a980e916f4a076a704da`; bot v2/LLM disabled, 새 DB/trace와 이전 DB quick_check `ok`, 서비스 active, Discord bot identity 확인, 새 활성 시점 뒤 journal 오류0. 중계는 `recon120p12egw`/LLM disabled 유지. 실제 Discord 사람 입력·전체 옵션/버튼·음성/청취·독립품질·DB/trace 복귀 연속성은 별도 **NOT_RUN/IN_PROGRESS**다.

## p12j — 주시 중단 시 관리자 복구 경로 보존 (2026-09-28)

- 코드 검토에서 `natural_input(admin_only=True, quiet=True)`가 v2가 켜져 있으면 `admin_only`를 건너뛰는 경로를 확인했다. 주시가 꺼진 고정 허용 채널의 관리자 복구 메시지에서 일반 음악 명령을 시도할 수 있으므로, 그 진입점은 기존 관리자 전용 v1 선택기·공통 실행기로만 보내도록 수정했다. 일반 주시 자연어는 계속 v2를 사용한다. 신규 회귀는 복구의 C42만 전달되고 C31 일반 명령은 v2에 전달되지 않음을 확인했다. 이는 실제 주시 끄기/켜기 사용자 시험의 PASS가 아니다.
- 불변 bot 후보 `recon120p12jbot` 공개 소스 manifest SHA256 `ee78666791ac1c2205afa948f3208fdb268e681435c55db5610101e03adf6820`, wheel SHA256 `8ab17f7d234371e8e74a4a528c9ce60d0f6d39a7796d018bd1205f159fd676c4`. 지정 LXC source 전체 **496 PASS**, bot/gateway 설치 wheel 우선 import **496 PASS**, Ruff PASS·mypy65파일 PASS. 추가 실제 Jev/GPT 호출0이며 마지막 공유 예약 **651/3000**, GPT 예약/실제 **2005/521 micro USD**를 유지했다.
- 새 run `recon120p12j-20260928`에 bot v2/LLM disabled로 적용했다. 이전 p12i unit은 `/etc/systemd/system/changgeun-dev-bot.service.before-recon120p12jbot`, 이전 DB/trace는 원래 run에 보존했다. 새 설정 SHA256 `eacf162a2acf2f51409dc38b2bad503e70eef05859482bb4ed2618113d481e46`, 새 업무 DB/trace quick_check `ok`, 서비스 active, Discord bot identity 확인. 이번 교체 전 p12i trace 요청은0개였다. journal에는 종료 중인 이전 Python의 `CancelledError` traceback이 남아 있으나 새 서비스는 실행 중이다. 실제 Discord 사용자 명령·관리 복구·음성 청취·독립221·전체 옵션/버튼·이관/rollback은 여전히 **NOT_RUN/IN_PROGRESS**다.

## p12k — 46개 실행 대상 명령의 개발용 stage1 진단 (2026-09-28)

- C39 자연어 진입점 자체를 제외한 공개 C01~C47 중 **46개**에 각각 새로운 합성 한국어 문장1개를 지정했다. 자료 SHA256 `3a806ce4762af200a43665c5ee93f7073d77d37344aace50c13e64c7f3ef2ef1`. 목적은 명령 선택 개발 진단이며 새 독립221문장 세트가 아니다. LXC의 활성 설정·업무 DB 사본과 합성 관리자/DJ actor로 읽고, 실제 Jev `command_select`의 1단계만 호출했다. 인수 선택·검증·Discord handler 실행은 수행하지 않았다.
- `recon120p12jbot` 코드의 전체46건 중 **37/46 정답**, 9건은 모두 `low_confidence`로 종료했다. 9건을 제한 경로에서 별도 다시 측정해 8건은 선택 후보 자체는 기대 ID였으나 threshold0.85 또는 margin0.15에 못 미쳤고, C10은 `__NONE__`을 골랐다. 이 별도9건도 **0/9 통과**다. 46건의 Jev stage1 지연 p50 **223ms**, p95 **288ms**이며 전체 명령/Discord 지연이 아니다. 개발 결과는 품질 목표 미달로 기록하고 threshold를 성급히 낮춰 PASS로 재분류하지 않는다.
- 첫46건 Jev 공유 예약 **651→697/3000**, 추가9건 **697→706/3000**. GPT 추가 호출0, 누적 예약/확인 실제 **2005/521 micro USD**. 원본 문장·원시 모델 응답은 공개 증거에 넣지 않고 합성 fixture와 제한 JSON 결과만 보존했다. 후보 목록은 실패9건 중 C32를 제외하면 기대 명령 한 개와 `__NONE__`이었으므로 단순 후보 과다만의 문제로 보지 않는다. 읽기/쓰기별 보정과 LLM 복구의 실제 효과는 별도로 평가해야 하며, 현 개발 자료에 맞춰 고치면 새 독립 세트를 잠가야 한다.

## p12l — GPT 복구의 실패 기록·중첩 출력 계약·테스트 서버 후보 적용 (2026-09-28)

- GPT 실호출은 테스트 봇을 잠시 정지하고 gateway만 제한적으로 켠 합성 요청으로 수행했다. 각 시험은 누적 US$1 예약 상한을 공유했고 종료 시 gateway를 `disabled`로 되돌려 임시 키를 제거하고 봇을 다시 시작했다. 첫 C22/C31 시험은 결과 보고 스크립트의 필드명 오류로 결과 파일 생성이 실패했다. 원장상 Jev 예약 **706→708**, GPT 예약 **2005→8850**, 확인 실제 **521→1570 micro USD**였으나 명령 결과 판정에는 넣지 않았다. 스크립트의 필드명을 고치고 유료 호출 직후 제한 JSONL을 남기도록 했다.
- 수정한 자동 경로 C22/C31은 각각 `rewrite_needs_clarification`/`invalid_full_parse_output`으로 끝났다. Jev **708→710**, GPT 예약 **8850→15695**, 실제 **1570→2586 micro USD**다. 제한 gateway 원장에서 C31의 `full_parse`가 `needs_clarification`이라고 하면서 비어 있지 않은 C01 계획을 함께 보낸 모순을 확인했다. 봇 검증기가 이를 거부한 것은 안전하게 동작한 결과이지 복구 성공이 아니다.
- [OpenAI Structured Outputs 계약](https://developers.openai.com/api/docs/guides/structured-outputs)의 중첩 `anyOf`를 사용해 root를 object로 유지하면서 `parsed`일 때만 계획을, 미해결일 때는 null 계획을 허용하도록 strict schema를 분리했다. 원문의 결정적 직접 후보가 있으면 full_parse 명령 범위를 그 후보로 제한한다. gateway의 현행 스키마 검사기가 허용하지 않는 `maxItems`는 포함하지 않았다. source 전체 **496 PASS**, Ruff PASS·mypy65파일 PASS. 새 자동 C31 시험은 `rewrite_needs_clarification`으로 종료했다(Jev **710→711**, GPT 예약 **15695→16217**, 실제 **2586→2640 micro USD**). 자동 복구 성공은 아직 확인되지 않았다.
- 새 wire 계약만 실행 없이 검증하려고 합성 C31을 강제 `full_parse`로 보낸 제한 시험은 strict schema가 실제 GPT endpoint에서 수락됐고 `parsed`/`C31` 초안을 반환했다. Jev **711→712**, GPT 예약 **16217→17229**, 실제 **2640→2678 micro USD**다. 이는 자동 fallback이나 Discord 실행 인수가 아니다. GPT 누적 확인 실제는 **US$0.002678**, 예약은 **US$0.017229**로 사용자 상한 **US$1** 이내이며 비용 미확인 호출0이다.
- 불변 bot 후보 `recon120p12lbot`의 공개 소스 manifest SHA256 `0e868d3386db9ce0fabfb9cd23687d0bc084628fe5bf4ccf89859d5b6652e159`, wheel SHA256 `5f6f1244121a6bbaed9f2adda52be5776a41cfd7527891d237cd4d52611a94ba`. 지정 LXC에서 source·설치 wheel 우선 import 전체 각각 **496 PASS**를 확인했다. 새 run `recon120p12l-20260928` 설정 SHA256 `4ec1df361de02b4f371111564a835f19ca0e2b775977f52b9552e4455c8a2e6b`로 테스트 서버 봇에 적용했다. 서비스 active, Discord identity 읽기, 신규 업무/trace DB quick_check `ok`였고 이전 unit/DB는 보존했다. 중계는 `recon120p12egw`/LLM disabled, 임시 GPT 키는 제거된 상태다.
- 사용자 Discord 인수에서 `!!창근아 목록 보여줘`, `!!창근아 들어와`/`여기 들어와`/`입장해줘`, `!!창근아 지금 노래 뭐틀고있어?` 등에 동일한 “대상이나 값을 확정하지 못했어” 응답이 보고됐다. 이는 **실제 인수 FAIL**이다. p12l trace에서 실제 수신5건 모두 `parse_status=failed`, 각 최초 `command_select` 원격 호출은 완료됐으나 다음 단계는 없었다. 입력 내용/계정 ID는 공개 trace 진단에 출력하지 않았다. 사용자 표현 네 건을 서비스·Discord 실행 없는 합성 Jev 1단계로 재현했고 모두 `low_confidence`였다. 목록 C01 선택 confidence0.73·top probability0.86, “입장해줘” C21 confidence0.98이나 `input_kind=single` confidence0.75, 현재곡 C31 confidence0.55·top probability0.78이었다. “여기 들어와”는 C21 confidence0.92이나 입력 성격을 `not_request` confidence0.30으로 골랐다. 공유 Jev 예약은 사용자 호출 **712→717**, 합성 재현 **717→721/3000**이며 GPT 비용은 증가하지 않았다.
- p12k 개발 stage1은 **37/46**으로 목표 미달이다. 실제 인수 실패가 확인됐으므로 사용자 명령의 정상 동작·음성 청취는 PASS가 아니다. 독립221문장·47명령의 전체 옵션/I01~I08·자동 GPT 복구 품질·trace/DB 복귀 연속성·정식 출시는 **IN_PROGRESS/NOT_RUN**이다. 이번 후보 적용과 합성 시험을 버전 완료로 표시하지 않는다.

## p12m — 실제 인수 실패의 Jev 선택 보정과 재적용 (2026-09-28)

- 사용자 실패 표현을 Discord 실행 없는 합성 actor/격리 업무 DB 사본에서 재현했다. p12l의 `목록 보여줘`, `여기 들어와`, `입장해줘`, `지금 노래 뭐틀고있어?` 네 건은 모두 Jev 첫 단계 `low_confidence`였다. 특히 명령 후보 자체는 기대 C01/C21/C31이었지만 각 질문의 confidence 임계값0.85에 미달했다. 이 개발 재현은 Jev 예약 **717→721/3000**이며 p12l 기록에 포함했다.
- 봇 호출 뒤의 명령형·정보 질문임을 Jev `input_kind` 설명에 명시하고, 짧은 음성 입장 표현을 C21 검색 힌트에 추가했다. 실제 허용 명령에서 힌트가 **하나**이고 Jev가 바로 그 ID(입력 성격은 `single`)를 선택한 경우에만, top probability≥0.75·상위 차이≥0.50·confidence≥0.50을 모두 요구하는 개발 보정 경로를 뒀다. 다른 선택·부정/인용 단서·낮은 분포는 기존0.85/0.15 판정에 남는다. 명령이나 값을 코드가 모델 대신 선택하지 않으며 권한·원문/목록·실행 직전 검증은 그대로다. 시험은 부정/약한 선택의 우회 차단도 확인했다. 이 기준은 **개발 자료 보정값**이며 독립 품질 승인 기준이 아니다.
- 변경 소스의 네 사용자 표현은 Jev stage1 **4/4 선택**, Jev 예약 **721→725**였다. 이전 46명령 개발 fixture를 다시 실행한 stage1은 **39/46**, 예약 **725→771**로 여전히 목표 미달이다. C06/C10/C22/C31/C32/C35/C38 실패를 보존한다. 해당 p50 **228ms**, p95 **283ms**는 stage1만의 지연이다. 별도 C01/C31 두 표현은 전체 Jev 초안과 `DraftValidator`를 통과했고 예약 **771→773**이었다. 이는 사용자 Discord 화면이나 음성 입장 결과가 아니다.
- 새 불변 bot 후보 `recon120p12mbot`의 공개 소스 manifest SHA256 `6f03ab4746058cbf13719e0b29406245c4f3288088bbfce4476b8c5f1bf2ca27`, bot wheel SHA256 `bf73e7da596bd4aa87b981669bcf7db81a06401a759ae5de7948a2c0c9fba2de`. 지정 LXC source·새 bot wheel 우선 import 전체 각각 **501 PASS**, Ruff PASS·mypy65파일 PASS. wheel import가 새 후보 경로를 가리켰다. `recon120p12m-20260928` 설정 SHA256 `775371bad0813265a6db9806b58cc8dc69b1b07d1041e4764e3dd8c799e5d695`로 테스트 서버 봇을 전환했다. 이전 p12l unit은 `/etc/systemd/system/changgeun-dev-bot.service.before-recon120p12mbot`에 보존했고 이전 DB/trace도 유지했다. 새 bot/gateway active, 신규 업무/trace DB quick_check `ok`, trace schema v2, 내부 TLS·계정 키 분리 PASS다. 중계는 `recon120p12egw`/LLM disabled, 임시 GPT 키 없음, GPT 누적 예약/실제 **17229/2678 micro USD** 유지.
- p12m의 사용자 Discord 재시험에서 `목록 보여줘`는 저장 목록2건 화면, `지금 노래 뭐틀고있어?`는 현재곡 없음/연결 안 됨 화면으로 **조회2건 PASS**였다. `들어와`와 `들어와줘`는 같은 일반 실패 문구로 **음성 입장2건 FAIL**이었다. 활성 trace에는 읽기2건 `parsed`/C01·C31, 입장2건 `failed`와 각각 `command_select`/`argument_select` 완료가 남았다. 따라서 입장은 첫 명령 선택 다음의 채널 인수 선택 단계에서 막혔다. 네 사용자 요청의 공유 Jev 예약 **773→779/3000**. 독립221·전체47명령 옵션/I01~I08·음성 청취·자동 GPT 복구·trace/DB 복귀 연속성·정식 출시는 미완료다.

## p12n — 채널 미지정 입장의 현재 음성채널 기본값 복구 (2026-09-28)

- `/입장`의 `채널`은 선택 인수이며 생략하면 요청자의 현재 음성채널을 사용한다. v2는 “들어와”처럼 명시적 채널 이름이 없는 문장에도 전체 음성채널 목록을 Jev 인수 질문으로 보내서 실패했다. 짧은 `들어와`/`들어와줘`/`여기 들어와`/`입장해줘` 형태에 한해 채널 인수를 생략하도록 했다. 명시적 채널 참조는 기존 실제 목록 선택과 실행 직전 최신 권한 검증을 유지한다. `들어와줘`를 C21 검색 힌트에도 추가했다. 채널 기본값은 기존 slash 실행기가 요청자의 현재 음성채널에서 결정하며 모델이 채널 ID를 생성하지 않는다.
- 지정 LXC에서 네 표현의 모델 대역 시험은 Jev 1단계만으로 C21 초안을 만들고 채널 인수는 비워 둠을 확인했다. 활성 gateway를 쓰되 Discord handler를 실행하지 않는 별도 합성 `들어와`·`들어와줘`는 각각 C21 초안과 `DraftValidator` PASS, 공유 Jev 예약 **779→781/3000**이었다. 이는 실제 Discord 음성 연결/청취 증거가 아니다.
- 불변 bot 후보 `recon120p12nbot`의 공개 소스 manifest SHA256 `256e906f6d93e7399967e14bc0054555448fa9144888be7bc357efef3ba11784`, bot wheel SHA256 `98b67bd7a15b27588e74dc17d7d70deb85c2cd896ca29c5727a3d62fe8b5c922`. 지정 LXC source·새 bot wheel 우선 import 전체 각각 **505 PASS**, Ruff PASS·mypy65파일 PASS. `recon120p12n-20260928` 설정 SHA256 `119b28bf47e3c0565fb953e3635ded9f6423687dc0cafe75793feee9b832bf87`로 테스트 서버 봇을 전환했다. p12m 이전 unit은 `/etc/systemd/system/changgeun-dev-bot.service.before-recon120p12nbot`, 이전 DB/trace도 보존했다. 새 bot/gateway active, 업무/trace DB quick_check `ok`, trace schema v2, gateway LLM disabled·임시 GPT 키 없음이다. GPT 누적 예약/실제 **17229/2678 micro USD**는 증가하지 않았다.
- p12n 실제 Discord 재시험에서 `들어와봐`는 채널 인수 선택까지 갔다가 일반 실패 문구로 종료했다. `들어와`는 C21 해석 후 “입장 명령을 실행할까?” 확인 버튼을 보였지만, 사용자가 버튼을 누르자 “처리 결과를 확인하지 못했어”로 끝났고 봇은 잠깐도 음성채널에 들어오지 않았다. **음성 입장 FAIL**이다. p12n trace에는 해당 C21 `parsed`/`outcome_unknown`·서비스 전달 없음이 남았다. 업무 DB에서 같은 요청의 접두어 원장 상태가 `finished`인 것을 확인했다. 공유 Jev 예약은 p12n 사용자 재시험 **781→785/3000**. p12m 조회2건 PASS를 p12n 전체 품질로 확장하지 않는다. 개발 stage1 39/46·독립221 미실시, 전체 옵션/상호작용·복귀 연속성·정식 출시 게이트는 여전히 열려 있다.

## p12o — 접두어 확인/후속 입력의 durable 대기 상태 복구 (2026-09-28)

- `!!창근아` 메시지 핸들러는 v2가 확인 버튼/typed 답변을 발행한 직후에도 `finally`에서 원장 요청을 `finished`로 바꿨다. 버튼 콜백은 최신 권한과 주시 상태를 다시 검사할 때 `running|waiting|committed`만 허용하므로, 실제 C21 명령이 실행기로 전달되기 전에 거부됐다. 새 대기 요청은 원장 `waiting`으로 고정해 최초 핸들러 종료가 덮어쓰지 못하게 했고, 버튼 성공/오류/취소/만료 뒤 단회로 완료·불명·취소 상태에 옮기도록 했다. 후속 typed 답변이 다시 확인 버튼을 만들면 대기 상태를 유지한다. 모델 결과·권한 검증·멱등성 경계는 변경하지 않았다.
- 확인/typed 실패 시 민감한 입력 대신 오류 **코드와 단계만** private trace 이벤트에 남겨 후속 진단을 가능하게 했다. 대기/종료 상태와 pending 단회 보유 회귀를 추가했다. 지정 LXC source·새 bot wheel 우선 import 전체 각각 **506 PASS**, Ruff PASS·mypy65파일 PASS. 불변 bot 후보 `recon120p12obot`의 공개 소스 manifest SHA256 `8278dc93ac69445db244b26276730c315b6cc8758121fe6489ca7fce22f672cc`, bot wheel SHA256 `b50513ff4bfb58eb1d9170392a32b32578be862e663a52b77672148eea4ae6f1`.
- 새 run `recon120p12o-20260928` 설정 SHA256 `46b6f1d86b85d9ff36906cc3659542d1b31bdad826a07b47b860b3dc2187a5d0`로 테스트 서버 봇을 전환했다. 이전 p12n unit은 `/etc/systemd/system/changgeun-dev-bot.service.before-recon120p12obot`, 이전 DB/trace도 보존했다. 새 bot/gateway active, 업무/trace DB quick_check `ok`, 중계 LLM disabled·임시 GPT 키 없음. 전환 직후 공유 Jev 예약 **785/3000**, GPT 예약/실제 **17229/2678 micro USD**.
- p12o 실제 재시험에서 사용자는 본인이 음성채널에 있다고 확인했다. `들어와`/`들어와줘`는 확인 버튼까지 갔으나 봇이 입장하지 않았고 “요청 조건이 맞지 않아 실행하지 않았어” 뒤 “확인한 명령을 처리했어”라는 상충된 응답이 나왔다. **실행 인수 FAIL**이다. p12o trace 총6건 중 C21 parsed2건·C01 parsed1건·failed3건, `command_select`6회/`argument_select`1회, 업무 DB의 C21 실행 기록0건을 확인했다. 공유 Jev 예약 **785→792/3000**. 현재 콜백이 내부 `DomainError`를 사용자 응답으로 바꾼 뒤 상위 확인 UI에는 성공처럼 돌아가므로 원인 코드가 상위 trace에 남지 않는다. 실제 입장 성공은 기록하지 않는다. 독립221·전체 명령 옵션/상호작용·복귀 연속성·정식 출시는 계속 미완료다.

## p12p — 슬래시 콜백의 내부 거부를 확인 UI에 전달 (2026-09-28)

- v2 접두어에서 호출한 기존 slash 콜백이 명령 실행 거부를 내부에서 응답하고 정상 반환하면 상위 확인 UI가 “처리했어”라고 잘못 안내했다. v2에서 바인딩한 접두어 entry에만 표시를 두고, `submit_plan`과 `/입장` 콜백의 `DomainError`를 상위 확인 UI로 전달하도록 했다. 상위 UI는 실패 코드를 private trace `execution.error`에 기록하며 알려진 오류는 기존 사용자 안내를 사용한다. 기존 slash와 v1 접두어의 오류 표시 경로는 유지한다. `들어와봐`도 채널 미지정 C21 표현에 추가했다.
- 지정 LXC에서 실패 콜백이 성공 문구를 출력하지 않는 통합 회귀를 추가했다. source 전체 **508 PASS**, 새 bot wheel 우선 import 전체 **508 PASS**, Ruff PASS·mypy65파일 PASS. 불변 bot 후보 `recon120p12pbot`의 공개 소스 manifest SHA256 `73ee329feb3d49f9cf193586032a4d7306023113e70e47e306358c7ee25cb972`, bot wheel SHA256 `62da0cf9898216362b3e73aecc3535f6ef2a92f76acb1afbd1700fd875fc1ffc`.
- 새 run `recon120p12p-20260928` 설정 SHA256 `c60b932e8c6566294f4a0b578dacd18abded8c183115a8aabc3923d400da7ee6`로 테스트 서버 봇을 전환했다. p12o 이전 unit은 `/etc/systemd/system/changgeun-dev-bot.service.before-recon120p12pbot`, 이전 DB/trace도 보존했다. 새 bot/gateway active, 업무/trace DB quick_check `ok`, 중계 LLM disabled·임시 GPT 키 없음. 전환 직후 공유 Jev 예약 **792/3000**, GPT 예약/실제 **17229/2678 micro USD**.
- 실제 음성 입장 재시험은 **확인 대기**다. 이번 후보는 실패 사유의 관측과 거짓 성공 안내를 보완한 것이며 음성 입장 문제를 해결했다고 주장하지 않는다. 독립221·전체 옵션/상호작용·복귀 연속성·정식 출시 게이트는 계속 열려 있다.
