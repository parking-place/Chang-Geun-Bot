# 0.5.0 · 1단계 — 창근이 API 1.2와 추론 프로필 계약

| 항목 | 내용 |
| --- | --- |
| 버전 / 단계 | 0.5.0 / 1 of 5 |
| 의존성 | 0.4.0 공통 실행기, 0.0.0 run별 연결·계측 타당성 |
| 시험 호스트 | DiscordBotLXC의 중계 API 계약; DiscordBotLXC 클라이언트 스키마 |
| 상태 | IN_PROGRESS — 필수 인수 전 |

## 목표

창근이가 만들 `/v1/decide`를 원본 `/v1/systemone`과 분리하고, 공급자 호출 전에 잘못된 입력·프로필·설정을 차단한다. [명세 1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) §§9,12와 [추론 프로필](../INFERENCE_PROFILES.md)을 두 서비스에 같은 계약으로 적용한다.

## 로컬 코드 작업

- `GET /health/live`, `GET /health/ready`, `POST /v1/decide`, 비공개 `GET /metrics` 경계를 작성한다.
- JSON Schema의 타입·범위·필수 필드·추가 필드 처리 정책을 명시하고 `schema_version="1.2"`만 받는다. 1.1을 조용히 추측 변환하지 않는다.
- 공통 필드를 `request_id`, `stage_index`, `task`, `request_expires_at`, `remaining_timeout_ms`, `context_snapshot_id`, `candidate_set_id`, `utterance`, `context`, `candidates`, `prompt_version`으로 정의하고 `provider`/`profile_id`/비밀값 제외 `config_hash`를 바인딩한다.
- 봇이 선택한 `profile_id`/`provider`/`config_hash`와 게이트웨이 readiness 메타데이터가 일치해야 자연어 시험을 활성화한다. 사용자 발화·키 존재 여부로 공급자를 선택하지 않으며 요청 수명 중 변경은 거절한다.
- `stage_index` 1/2/3과 task `classify_intent`/`select_action`/`resolve_context`를 정확히 대응시킨다. 질문은 1개, 각 단계 후보에 `clarify`를 포함한다.
- 입력 기본 500자·프롬프트 1,024토큰·후보 최대 12개를 정의한다. 상한 초과 입력은 뒤를 잘라 실행하지 않는다.
- 응답의 요청·단계·task·snapshot·candidate set·프로필 일치, 후보 ID, 유한한 확률과 합계 오차, `usage` 타입 검증 계약을 정의한다.
- `usage.provider_calls`는 단계별 신규 dispatch 수(0 또는 1), `usage.request_provider_calls_total`은 요청 누계(3 이하), `usage.request_stages_total`은 요청 단계 수로 게이트웨이가 생성한다. provider/profile 메타데이터와 함께 검증하며 캐시/합류는 신규 dispatch 0회다.
- hosted는 두 forward 필드를 `null`, `forward_passes_source=unavailable`로 받는다. 호출 수를 실제 forward로 변환하지 않는다.
- 오류를 400/422 입력, 401/403 인증, 409 순서·본문·예산·기한 충돌, 429 대기열, 503 미준비, 504 기한으로 분류한다.
- 등록 프롬프트 템플릿과 사용자 입력을 분리한다. Discord 사용자가 후보·단계·시간·프롬프트 버전을 직접 지정하지 못하게 한다.
- 봇·게이트웨이·운영/시험 설정을 분리하고 단계/공급자 호출 상한 3, `early_exit_enabled=true`, `automatic_provider_retries=0`, `automatic_model_retries=0`, `automatic_fallback=false`를 시작 시 검증한다.
- 3단계는 상한 3과 enabled일 때만 허용하며 정책은 `unresolved_context_only`만 지원한다. 단계 제한은 양수이고 공통 deadline 이하여야 한다.
- `JEV_API_TOKEN`은 봇→게이트웨이 인증으로 유지한다. hosted `JEV_HOSTED_API_KEY`는 별도 접근 제한 파일에서 DiscordBotLXC의 중계 게이트웨이에만 전달하며 `.private/Jev-API-key` 값을 문서·예시·로그에 복사하지 않는다.
- 예정 runner의 단일 `--profile` 선택이 의존성·분리 저장소·증거를 함께 고르고 `--dry-run`은 네트워크/모델 로딩 없이 누락/충돌만 검사하도록 설계한다. mock 기본 자동시험과 실제 모드 명시 선택을 구분한다.

## 산출물

- 봇·게이트웨이 양쪽 API 1.2 스키마와 오류 코드 목록, 단계/task·run별 usage 표, 설정 검증 표.
- 인증·TLS·프롬프트 등록 경계 및 모델 호출 전 거절을 확인할 시험 코드.
- 비밀값 없는 Jev API 실제 프로필/mock 설정 예시와 1.0/1.1 비호환 처리 설명.

## LXC 검증

- [B-01·B-02·B-04](../TEST_MATRIX.md)의 선택/dry-run·활성 설정/키 분리·API 프로필/스키마 일치를 이 단계의 필수 계약 시험으로 연결한다.
- DiscordBotLXC의 중계에서 설치·lint·타입 검사·단위/mock 시험을 실행하고 DiscordBotLXC에서 동일 스키마의 소비를 검사한다.
- N-26의 단계 0/4와 task 불일치, N-15의 입력 상한·말미 부정어, N-16의 깨진 응답·NaN을 시험한다.
- Jev API 실제 프로필에서 401/403·허용되지 않은 프롬프트·누락된 `clarify`·후보 초과·profile/hash 불일치의 공급자 dispatch 0회를 확인한다.
- 공개 live/ready·오류에 키·원문·raw prompt를 노출하지 않는다.
- hosted가 `torch`/모델 없이 설정 검사·계약 시험을 준비할 수 있는지, dry-run이 외부 요청/모델 로딩 0회인지 LXC에서 확인한다.

## 통과 기준

- 잘못된 스키마·설정·프로필은 시작 또는 호출 전에 거절되고 공급자 dispatch는 0회다.
- 명세의 API 1.2 필드·오류·단계/task·run별 usage 대응이 DiscordBotLXC의 봇·중계에서 일치한다.
- 인증서 검증을 끄지 않고 API는 허용된 봇 호출 경계만 제공한다.

## 중단·후속 처리

계약이 어긋나거나 구버전 응답·알 수 없는 hosted forward를 추측 처리하면 해당 프로필 활성화를 막는다. 명시적 버전 어댑터가 필요하면 별도 계약으로 기록하고, 서버 실행 없이 로컬에서 수정한 후 해당 LXC에서 재검증한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
