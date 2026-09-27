# 0.0.0 — 개발 기준선과 기술 타당성

| 항목 | 내용 |
| --- | --- |
| 상태 | IN_PROGRESS — 부분 구현·LXC 시험; 전체 인수 전 |
| 선행 버전 | 없음 — 최초 단계 |
| 기준 | [개발 명세 1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) |
| 시험 위치 | DiscordBotLXC / DiscordBotLXC의 중계; 로컬은 작성·읽기 검토만 |

## 추론 프로필 적용

[Jev API 전용 계약](../INFERENCE_PROFILES.md)을 따른다. 실제 자연어 판단은 `jev-api`만 사용하며 봇과 TLS 중계·영속 원장은 DiscordBotLXC에서 별도 계정으로 실행한다. 현재 배치는 [환경 계약](../ENVIRONMENT.md)을 따른다. `mock`은 지정 LXC의 격리 회귀 전용이다. 구조화 명령은 추론 없이 실행하고, API 장애가 기존 재생·슬래시·버튼을 막지 않게 한다.

## 범위

명세의 범위·불변 조건·진행 상태를 고정하고 로컬 작성/LXC 실행 경계를 만든다. 기존 DiscordBotLXC의 봇·중계의 준비 상태와 음성·소스·Jev API 한국어 추론의 핵심 위험을 일찍 확인한다.

범위 제외: 제품 기능 완성, 운영 배포, 기존 LXC 재생성, 호스트 CPU pinning, 모델 성능 보장.

## 단계

| 순서 | 단계 문서 | 검증 호스트 |
| --- | --- | --- |
| 01 | [범위와 요구사항 계약](01_scope_and_contracts.md) | 해당 없음 — 로컬 문서 계약 검토 |
| 02 | [코드 구조와 원격 검증 루프](02_repository_and_remote_workflow.md) | DiscordBotLXC + DiscordBotLXC의 중계 |
| 03 | [기존 LXC 준비와 시험 격리](03_lxc_readiness_and_isolation.md) | DiscordBotLXC + DiscordBotLXC의 중계 |
| 04 | [음성·재생 소스·Jev API 추론 경로 초기 타당성](04_technical_feasibility.md) | DiscordBotLXC: 음성/소스, DiscordBotLXC의 중계: 게이트웨이와 선택 공급자 |
| 05 | [기준선 인수와 다음 버전 준비](05_baseline_gate.md) | DiscordBotLXC + DiscordBotLXC의 중계 |

순서대로 진행하며 각 단계의 필수 증거를 확보한다. 의존성이 없는 초안 작성은 병행할 수 있지만 게이트를 생략하지 않는다.

01단계는 실행 환경 구축 전 문서 계약 검토이며 REVIEWED 문서 증거로 02단계에 진입한다. 02단계에서 최소 비root 계정·분리 경로·Python을 먼저 준비한 뒤 venv/설치/runner를 검증한다. 03단계는 상세 환경·운영 격리·ID·네트워크를 검증한다. 이 순서로 초기 환경 준비의 순환 의존을 피한다. 문서 REVIEWED는 제품 VERIFIED/DONE을 대신하지 않는다.

## 버전 통과 조건

Jev API의 필수 시험이 미실행·실패이면 해당 단계를 완료하지 않는다. mock·개발 소규모 시험으로 실제 품질·장시간 인수를 대체하지 않는다.

[환경 계약](../ENVIRONMENT.md), [시험 추적표](../TEST_MATRIX.md), [증거 양식](../EVIDENCE_TEMPLATE.md), [진행 현황](../STATUS.md)을 함께 사용한다. 설치·빌드·lint/타입검사·mock/단위/통합·모델/음성 검증 등 모든 제품 실행은 지정 LXC에서 수행한다. 로컬에서는 코드·문서 작성과 읽기 검토만 한다. 현재 문서는 실행 결과가 아니다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
