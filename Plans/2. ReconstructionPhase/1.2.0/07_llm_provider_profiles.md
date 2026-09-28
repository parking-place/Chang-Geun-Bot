# 07. 공급자 독립 LLM 계약과 GPT-5 nano 프로필

상태: **PLANNED**. 아래 구현·시험·실호출은 후속 작업이며 현재 완료 증거가 아니다.

[버전 개요](README.md) · [아키텍처](ARCHITECTURE.md) · [시험 추적](TEST_MATRIX.md) · [실행 상태](STATUS.md)

## 목적과 선행 조건

- [재구성 명세](../changgeun_jev_llm_fallback_command_parser_spec_v1.3.md) §8의 rewrite/full_parse를 같은 공급자 독립 인터페이스로 구현한다.
- 실제 목록을 만들 수 있는 인수는 원문에서 가상 후보를 만들지 않고 실제 목록을 전달한다는 후속 사용자 지시를 우선한다. 원본 명세는 보존한다.
- 01의 계약 기준선, 02의 typed registry, 04의 후보·원문 근거, 05의 `parser-api-v2` 공통 예약·취소 계약이 먼저 확정되어야 한다.
- 기존 API 1.2는 별도 호환 경로로 유지한다. 현재 운영 프로필·키·서비스는 이 계획으로 변경하지 않는다.
- OpenAI 외부 호출과 키 읽기는 DiscordBotLXC의 `changgeun-gateway`에 한정하고 bot 계정에는 키를 전달하지 않는다.

## 구현 작업

1. `LLMRequest`, `CallContext`, `LLMResult`, provider 프로토콜을 공급자 SDK와 분리한다. `operation`은 `rewrite/full_parse`만 허용한다.
2. 프로필 키와 실제 API model ID를 분리하고 요청 시작 시 프로필을 고정한다. 두 작업 중간의 공급자·모델 교체를 금지한다.
3. `command-rewrite-v1`과 `command-parse-v1`을 registry에서 생성한다. full_parse의 `repair_arguments/reparse`는 한 호출의 범위 선택이다.
4. 명령별 plan 분기를 사용하고 객체의 추가 필드를 금지한다. 생략 가능한 인수도 required에 넣되 null을 허용하고 공통 스키마로 재검증한다.
5. rewrite 결과에는 command·arguments·confidence를 허용하지 않는다. full_parse는 등록 명령·인수만 허용하고 모델이 실행자·권한·실제 DB ID를 만들 수 없게 한다.
6. 목록형 entity의 실행 가능한 출력은 제공한 실제 snapshot의 opaque member ID로 한정한다. query는 재조회/질문용 미해결 근거일 뿐 실행 ID가 아니다.
7. OpenAI Responses adapter는 고정 endpoint, `text.format` strict JSON Schema, `store=False`, SDK 재시도 0, 네이티브 호출 최대 1회를 적용한다.
8. 도구·웹·파일·명령 실행 기능을 모델에 제공하지 않는다. 원문과 후보는 신뢰하지 않는 데이터로, 시스템 규칙과 구조상 분리한다.
9. 비밀값 없는 preflight 뒤 공통 예산을 예약한다. 예약 후 로컬 실패는 보수적으로 소비 처리하고 실제 전송 여부는 별도로 기록한다.
10. refusal·incomplete·빈 출력·잘못된 JSON·스키마 오류·인증·제한·timeout·모델 접근 오류를 분리하고 원문 예외를 사용자에게 보내지 않는다.
11. usage는 거절·미완료·JSON 검사 전에 수집한다. input/output/total/cached/reasoning 및 reported/partial/unknown을 구분한다.
12. 종료·취소에서 SDK 자원을 닫고 요청별 남은 deadline을 적용한다. 취소가 공급자 연산·과금까지 취소했다고 추정하지 않는다.

실제 재생목록·곡·채널 등은 권한 및 사용자가 명시한 범위의 전체 목록을 제공한다. fuzzy/top-K 절단이나 원문 이름 후보로 대체하지 않는다.
목록 snapshot은 root request/pass/argument/원본 버전에 결합한다. stale이면 다시 조회하고, full_parse 뒤 재선택이 필요하면 모델을 재호출하지 않고 실제 목록 UI/질문으로 해결한다.
원문 기반 query가 반환돼도 해당 범위의 실제 목록을 다시 확인해야 한다. 임의 DB ID 생성·검색 첫 결과 자동 선택·동명 병합은 금지한다.
목록 크기가 전송 한도를 넘으면 범위 지정/목록 UI를 요청한다. 조용한 잘라내기·LLM 전환·모델별 페이지 반복으로 예산을 우회하지 않는다.
새 이름·자유 검색어·숫자 등 실제 목록으로 표현할 수 없는 값은 기존 원문 구간·결정적 파싱 정책을 유지한다.

## 설정 계약

| 항목 | 계획값 및 동작 |
|---|---|
| `LLM_FALLBACK` | 미설정은 `gpt-5-nano`, 키 누락은 초기화 오류 |
| `disabled` | rewrite/full_parse 모두 비활성, 키 불필요 |
| `gemini`, `luna` | 예약 키만 유지, 선택 시 명시적 미구현 오류 |
| 빈 문자열·미등록 키 | 설정 오류, 자동 대체 금지 |
| rewrite | timeout 5초·출력 1024토큰을 초기 튜닝값으로 사용 |
| full_parse | timeout 10초·출력 2048토큰을 초기 튜닝값으로 사용 |
| 구 설정 | `OPENAI_FALLBACK_MODEL`, `LLM_FALLBACK_TIMEOUT_SECONDS`, `LLM_FALLBACK_MAX_OUTPUT_TOKENS` 검출 시 충돌 오류 |

환경변수와 YAML은 하나의 유효 설정으로 합친다. 비밀값 없는 설정 hash와 요청 당시 프로필을 남기며 값 변경은 검증된 재배포로 반영한다.
GPT-5 nano의 Responses·Structured Outputs 지원은 [공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-5-nano)로 확인했다. 계정별 접근 가능 여부는 향후 실호출 시험 대상이다.
Responses의 `text.format` 및 스키마 제약은 [공식 Structured Outputs 문서](https://developers.openai.com/api/docs/guides/structured-outputs)를 따른다. 형식 준수와 실행 허가는 별개다.

## 산출물

- gateway의 fallback contracts/service/factory/profiles 및 OpenAI Responses adapter.
- SDK·스키마 검증기 잠금 의존성, 비밀값 없는 설정 예시, 구 설정 마이그레이션 표.
- 공통 출력 스키마 fixture, 공급자 오류·usage 정규화 표, 어댑터 교체 계약.
- adapter의 preflight/reserved/sent/response/finished 관측 훅; 10의 기록 구현과 결합하기 전 운영 적용 금지.

## 검증 계획 — DiscordBotLXC 전용

- **R120-14:** 두 스키마·모든 명령 분기·nullable 인수·잘못된 candidate/query·extra field·프로필 설정 조합을 계약 시험한다.
- **R120-14:** disabled에서 원격 0회, 미구현/오타/키 누락 시 fail-fast, 요청 중 프로필 변경 거부를 확인한다.
- **R120-08/09/12 연계:** 실제 목록 밖 ID·다른 snapshot ID·stale 목록·query 첫 결과·초과 목록을 주입해 실행 차단과 실제 목록 재확인/질문을 검증한다.
- **R120-15:** refusal/incomplete/429/401/404/timeout/취소/JSON 오류마다 실행 0회와 retry 0회를 검증한다.
- **R120-15:** 실패 응답의 usage 보존, 알 수 없는 토큰을 0으로 바꾸지 않음, trace 누락 시 비밀 출력 없음과 종료 자원 정리를 확인한다.
- 지정된 비용 한도 안에서 nano의 두 operation 실호출을 수행하고 요청 모델·반환 모델·옵션·schema·usage 증거를 남긴다.
- 공통 계약을 보장하지 못하는 프로필은 활성화하지 않는다. 키 파일 존재와 문서 예시는 실호출 PASS가 아니다.

## 종료 게이트

- [ ] R120-14/15의 mock 계약 및 제한된 실제 공급자 시험이 각각 증거에 연결된다.
- [ ] 공통 예산·취소·관측 훅·키 계정 경계가 검증되고 API 1.2 호환 시험이 유지된다.
- [ ] 사용 가능한 nano 프로필만 등록되며 다른 모델 자동 전환과 모델의 도구 실행 경로가 없다.
- [ ] 코드·mock 계약 완료로08의 통합 개발에 진입할 수 있다. 유료 시험은05/10 최소 관측 준비 후11에서 수행해07 증거에도 연결한다.07의 실호출 완료를08/10 구현 착수 조건으로 삼아 순환 의존성을 만들지 않는다.
- [ ] 상태·실패 사례·잔여 위험을 STATUS에 기록한다. 단계 전체VERIFIED는 위 실호출까지 확인한 뒤 판정하며 제품 출시PASS와 구분한다.
