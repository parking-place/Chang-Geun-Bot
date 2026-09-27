# 0.7.0 — 창팝 편의 기능과 데이터 편집 확장

| 항목 | 내용 |
| --- | --- |
| 상태 | IN_PROGRESS — 부분 구현·LXC 시험; 전체 인수 전 |
| 선행 버전 | [0.6.0](../0.6.0/README.md) 안전한 자연어 흐름과 구조화 음악봇 |
| 기준 | [개발 명세 1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) |
| 시험 위치 | DiscordBotLXC / DiscordBotLXC의 중계; 로컬은 작성·읽기 검토만 |

## 추론 프로필 적용

[Jev API 전용 계약](../INFERENCE_PROFILES.md)을 따른다. 실제 자연어 판단은 `jev-api`만 사용하며 봇과 TLS 중계·영속 원장은 DiscordBotLXC에서 별도 계정으로 실행한다. 현재 배치는 [환경 계약](../ENVIRONMENT.md)을 따른다. `mock`은 지정 LXC의 격리 회귀 전용이다. 구조화 명령은 추론 없이 실행하고, API 장애가 기존 재생·슬래시·버튼을 막지 않게 한다.

## 범위

P1 편의와 일반 회원 제안함을 구현하고 기존 목록·대기열·권한·확인 규칙을 유지한다. 새 기능은 공통 action에 등록하며 자연어도 동일한 정책을 사용한다.

범위 제외: 모델의 곡 창작/외부 검색 자동 채움, 음악적 동일성 보장, 외부 목록 자동 동기화, YouTube OAuth/원격 수정, 오디오 되감기.

## 단계

| 순서 | 단계 문서 | 검증 호스트 |
| --- | --- | --- |
| 01 | [별칭·태그와 검색 정합성](01_aliases_tags_and_search.md) | DiscordBotLXC; 자연어 후보 회귀는 DiscordBotLXC의 중계 게이트웨이와 Jev API 프로필 |
| 02 | [등록 카탈로그의 조건부 목록 생성](02_rule_based_playlist_generation.md) | DiscordBotLXC; 조건 해석 API는 DiscordBotLXC의 중계 공통 게이트웨이의 Jev API 프로필 |
| 03 | [일반 멤버 제안과 DJ 승인](03_member_proposals.md) | DiscordBotLXC; 자연어 제안은 DiscordBotLXC의 중계 게이트웨이와 Jev API 프로필 |
| 04 | [목록 가져오기·복사·내보내기](04_import_copy_and_export.md) | DiscordBotLXC |
| 05 | [되돌리기·복원·재생 불가곡 점검 인수](05_undo_restore_and_convenience_gate.md) | DiscordBotLXC + DiscordBotLXC의 중계 |

순서대로 진행하며 각 단계의 필수 증거를 확보한다. 의존성이 없는 초안 작성은 병행할 수 있지만 게이트를 생략하지 않는다.

## 버전 통과 조건

P-01~12 전건, 새 action 권한/확인/중복 시험과 기존 T/N 회귀를 LXC에서 통과한다. 자연어 관련 필수 회귀는 Jev API에서의 증거가 필요하며 품질·성능 결과를 합산하지 않는다. 제안함은 권한 있는 DJ의 승인 전에 실제 목록/큐를 바꾸지 않는다.

[환경 계약](../ENVIRONMENT.md), [시험 추적표](../TEST_MATRIX.md), [증거 양식](../EVIDENCE_TEMPLATE.md), [진행 현황](../STATUS.md)을 함께 사용한다. 구현·설치·빌드·lint/타입검사·mock/단위/통합·모델/음성 검증은 모두 지정 LXC에서 실행한다. 현재 문서는 실행 결과가 아니다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
