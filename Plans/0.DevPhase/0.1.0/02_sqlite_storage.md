# 0.1.0 02 — SQLite 마이그레이션과 서버별 저장

| 항목 | 내용 |
| --- | --- |
| 버전 | 0.1.0 |
| 단계 | 02 / 05 |
| 선행 조건 | 01_domain_contracts.md |
| 검증 호스트 | DiscordBotLXC |
| 상태 | IN_PROGRESS — 필수 인수 전 |

## 목표

- 음악봇 데이터 저장소를 DiscordBotLXC에 한정하고 재시작해도 목록·설정을 보존한다.
- 도메인 불변식이 애플리케이션 코드뿐 아니라 DB 제약으로도 유지되도록 한다.

## 추론 프로필 적용

[Jev API 전용 계약](../INFERENCE_PROFILES.md)을 따른다. 실제 자연어 판단은 `jev-api`만 사용하며 봇과 TLS 중계·영속 원장은 DiscordBotLXC에서 별도 계정으로 실행한다. 현재 배치는 [환경 계약](../ENVIRONMENT.md)을 따른다. `mock`은 지정 LXC의 격리 회귀 전용이다. 구조화 명령은 추론 없이 실행하고, API 장애가 기존 재생·슬래시·버튼을 막지 않게 한다.

## 로컬 코드 작업

로컬에서는 아래 코드·문서 작성과 읽기 검토만 한다. 설치·lint·타입검사·시험·build는 LXC에서 수행한다.

- guild_settings, tracks/source_metadata/annotations, aliases/tags, playlists/entries, sessions/queue/history, proposals, command/confirmation/change_events, migration 원장을 설계한다.
- 단계별 실제 사용 테이블을 마이그레이션하고 이후 테이블은 도입 버전과 스키마 변경 순서를 기록한다. 빈 구조를 기능 완성으로 표시하지 않는다.
- (guild_id, source_type, external_id) 곡 유일성, 활성 정규화 목록명 유일성, 서버당 활성 세션/현재 항목 최대 1개를 적용한다.
- 외래키와 guild 경계를 함께 강제하고 position 재정렬 중 유일성 충돌이 생기지 않도록 트랜잭션 알고리즘을 작성한다.
- 연결마다 필요한 SQLite 설정·쓰기 충돌 처리·짧은 트랜잭션 범위를 명시한다. 운영 DB 자동 삭제·초기화 경로를 만들지 않는다.

## 산출물

- 순서 있는 DB 마이그레이션과 저장소 구현 소스.
- 스키마/제약 목록 및 최초 DB·기존 버전 DB 업그레이드 설계.
- 음악봇 DB 소유권·경로 설정 예시와 격리된 시험 DB 생성 절차 초안.

## LXC 검증

- DiscordBotLXC의 disposable DB에서 최초 적용·재적용·업그레이드·잘못된 스키마 중단을 검증한다.
- 빈 목록 저장 후 프로세스 재시작 복원, 타 guild foreign key, 활성/논리삭제 이름 충돌, 중복 곡 참조를 시험한다.
- 3항목 이동·삭제·다중 재정렬과 실패 주입에서 순서·버전이 부분 적용되지 않는지 검사한다.

## 통과 기준

- T-01·02·06·10의 저장 계층 선행 시험을 통과한다. 실제 Discord 최종 시험은 0.2.0에 남긴다.
- 실패한 마이그레이션은 부분 스키마 변경 없이 중단되고 같은 버전을 무조건 성공으로 숨기지 않는다.
- LXC 실행 정보·적용 스키마·결과 증거가 남으며 DiscordBotLXC의 중계가 음악봇 DB를 소유/조회하지 않는다. run별 시험 봇 DB와 DiscordBotLXC의 중계의 추론 원장은 별도 경로이며 설정·후보 변경으로 원장을 초기화해 기존 요청을 재실행하지 않는다.

## 중단·후속 처리

- 스키마 손상·경계 침범·재정렬 충돌이 있으면 0.1.0 gate를 닫는다.
- 운영 백업·복원과 보존기간 정리 자동화는 0.8.0에서 강화하되 현재 데이터 보존 원칙은 유지한다.

[환경](../ENVIRONMENT.md) · [시험 추적](../TEST_MATRIX.md) · [증거 양식](../EVIDENCE_TEMPLATE.md) · [버전 목차](README.md)


## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
