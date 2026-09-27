# 0.5.0 — Jev API 공통 게이트웨이와 추론 계약

| 항목 | 내용 |
| --- | --- |
| 상태 | IN_PROGRESS — 부분 구현·LXC 시험; 전체 인수 전 |
| 이전 버전 의존성 | [0.4.0](../0.4.0/README.md) 재생 기능과 공통 명령 실행기 |
| 선행 타당성 의존성 | [0.0.0](../0.0.0/README.md) run별 연결·계측·지원 계약 타당성 조사 |
| 기준 명세 | [개발 명세 1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) §§3,8,9,12,13,16,17 및 [추론 프로필](../INFERENCE_PROFILES.md) |

이 버전은 DiscordBotLXC의 봇과 DiscordBotLXC의 중계의 Jev API 전용 게이트웨이를 API1.2로 연결한다. 실제 제공자는 Jev API 하나다. 공급자는 등록 후보만 선택하며 Discord·봇 DB·재생 실행 권한을 갖지 않는다. 모델 설치·가중치 다운로드는 필요하지 않다.

영속 원장, 원자적 단계 순서·예산 예약, 중복 재사용, 전체 deadline, 공급자 호출 계측과 취소 결과 폐기는 이 버전의 필수 기능이다. Jev API에서 최대 3단계·단계당 질문 1개/공급자 dispatch 1회를 강제한다. `usage.provider_calls`는 해당 단계의 신규 dispatch 수(0 또는 1), `usage.request_provider_calls_total`은 요청 누계(3 이하)다. 캐시 재사용·진행 합류는 추가 dispatch 0회이며 누계를 유지한다. hosted의 내부 forward는 알 수 없으므로 두 forward 필드는 `null`, `forward_passes_source=unavailable`로 기록한다. 안전 계약을 0.8.0까지 미루지 않으며 자연어 전체 연결은 0.6.0에서 진행한다.

구현한 선택 도구는 `python3 scripts/test_profile.py --profile jev-api|mock --suite ...`이며 SSH 설정 등 실제 인자는 [원격 runbook](../../../docs/REMOTE_DEVELOPMENT.md)을 따른다. 프로필 하나로 비밀값을 제외한 설정, 의존성, 분리된 봇 DB·원장·증거 위치를 선택하고 `--dry-run`은 네트워크/모델 없이 설정만 점검한다. `mock`은 자동시험 기본값이며 실제 프로필은 명시적으로 선택한다. 키 유무에 따른 선택·fallback과 실행 중 hot switch는 없다. 전환은 테스트 봇/게이트웨이 정지·drain·불명 요청 tombstone 기록 후 새 `run_id`/세션으로 시작하며 운영 설정은 별도로 보존한다. 현재 `contract`, `activate`, `status`, `transport`, 개발전용 `korean-eval`을 구현·부분 검증했다. 계획된 평가/soak와 전체 장애 인수는 완료 전이다.

로컬은 소스·문서·시험 코드 작성과 읽기 검토만 수행한다. 설치·빌드·lint·타입 검사·단위/mock 시험·실제 모델 실행·벤치마크는 모두 지정 LXC에서 수행한다.

| 단계 | 문서 | 주요 결과 |
| --- | --- | --- |
| 1 | [API 1.2 계약](01_api_contract.md) | 프로필 고정·엄격 스키마·인증·설정 검증 |
| 2 | [Jev API 공급자 어댑터](02_model_adapter.md) | 의존성 분리·single-send·run별 readiness/계측 |
| 3 | [영속 원장과 예산](03_request_ledger.md) | 원자적 순서·중복·재시작 보호 |
| 4 | [기한·취소·대기 제어](04_deadline_cancellation.md) | 12초 공통 기한·4초 단계·슬롯 보존 |
| 5 | [봇 클라이언트와 계약 인수](05_client_acceptance.md) | 요청/응답 검증·격리·API 안전 게이트 |

Jev API의 필수 시험이 미실행·실패이면 해당 단계를 완료하지 않는다. mock·개발 소규모 시험으로 실제 품질·장시간 인수를 대체하지 않는다.

[시험 매트릭스](../TEST_MATRIX.md)의 B-01–11을 단계별로 인수한다. B-08의 복원/롤백 확장은 0.8.0에서, B-12의 Jev API 프로필 품질 비교는 0.6.0에서 이어서 검증하며 이 버전의 통과로 후속 증거를 대신하지 않는다.

hosted는 `torch`/모델 설치·로딩 없이 동작해야 하며 내부 모델 revision을 확인할 수 없으면 미확인으로 보고한다. upstream 원격 클라이언트의 자동 재시도·추정 forward는 공통 계약으로 사용할 수 없다.

공통 문서: [추론 프로필](../INFERENCE_PROFILES.md), [실행 환경](../ENVIRONMENT.md), [시험 매트릭스](../TEST_MATRIX.md), [증거 양식](../EVIDENCE_TEMPLATE.md). 본 README는 실행 완료 증거가 아니며 `profile_id`·provider·비밀값 제외 설정 해시·run ID별 LXC 결과가 등록되어야 상태를 변경한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
