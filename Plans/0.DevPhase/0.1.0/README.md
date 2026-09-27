# 0.1.0 — 도메인·저장 기반

| 항목 | 내용 |
| --- | --- |
| 상태 | IN_PROGRESS — 부분 구현·LXC 시험; 전체 인수 전 |
| 선행 버전 | [0.0.0](../0.0.0/README.md) 기준선·환경·위험 확인 |
| 검증 호스트 | DiscordBotLXC |
| 명세 | [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) §4·5·9.5·10·18 |

이 버전은 Discord와 모델 없이 데이터·권한·확인·실행 계약을 만든다. 로컬은 코드·문서 작성과 정적 읽기 검토만 수행한다. 의존성 설치, lint, 타입검사, 단위·mock·통합시험과 build는 모두 지정 LXC에서 수행한다.

## 공통 기준

- [환경과 실행 경계](../ENVIRONMENT.md)
- [시험 추적표](../TEST_MATRIX.md)
- [검증 증거 템플릿](../EVIDENCE_TEMPLATE.md)

## 5단계 순서

1. [01 도메인 경계와 명령 계약](01_domain_contracts.md)
1. [02 SQLite 마이그레이션과 서버별 저장](02_sqlite_storage.md)
1. [03 권한·확인 정책과 실행 계획 검증](03_permission_confirmation.md)
1. [04 공통 실행기·중복 방지·버전 경쟁](04_transaction_executor.md)
1. [05 도메인·저장 기반 인수와 다음 버전 계약](05_domain_acceptance.md)

## 추론 프로필 적용

[Jev API 전용 계약](../INFERENCE_PROFILES.md)을 따른다. 실제 자연어 판단은 `jev-api`만 사용하며 봇과 TLS 중계·영속 원장은 DiscordBotLXC에서 별도 계정으로 실행한다. 현재 배치는 [환경 계약](../ENVIRONMENT.md)을 따른다. `mock`은 지정 LXC의 격리 회귀 전용이다. 구조화 명령은 추론 없이 실행하고, API 장애가 기존 재생·슬래시·버튼을 막지 않게 한다.

## 범위

- 도메인 엔티티·ActionPlan·동작 allowlist·오류 계약.
- SQLite 마이그레이션·guild 격리·순서/버전·변경 감사·요청 결과 원자성.
- 실제 권한정보를 입력받는 정책과 요청자 결합 일회성 확인.
- 요청 중복 방지·버전 경쟁·재시작 보존의 도메인 선행 시험.

## 범위 밖과 후속

- 실제 Discord 슬래시·버튼·설정 조회는 0.2.0에서 연결한다.
- 외부 메타데이터·소스 적합성·DAVE 음성은 0.3.0, 실제 대기열/재생 상태기계는 0.4.0이다.
- Jev API의 API schema 1.2·공통 게이트웨이 원장·자연어 단계는 0.5.0~0.6.0에서 음악봇 DB와 분리한다. Jev API 추론 원장은 DiscordBotLXC의 중계에 유지한다.
- 가져오기·내보내기·되돌리기·복원 편의는 0.7.0, 운영 백업·장시간 장애 검증은 0.8.0이다.

## 버전 종료 게이트

5단계의 DiscordBotLXC 시험 증거가 모두 있고 저장/정책/중복/격리 실패가 없을 때만 기반 완료로 표시한다. T/N 번호는 해당 계층의 선행 시험이며 실제 Discord·재생·자연어 최종 통과를 대신하지 않는다. 실제 실행 전까지 상태는 계획 / 미구현 / 미검증이다.


## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
