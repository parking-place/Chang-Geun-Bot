# 0.4.0 01 — 재생 상태기계·세션과 오디오 실행 경계

| 항목 | 내용 |
| --- | --- |
| 버전 | 0.4.0 |
| 단계 | 01 / 05 |
| 선행 조건 | 0.3.0 허용 source·DAVE·음성 gate와 0.1.0 공통 실행기 |
| 검증 호스트 | DiscordBotLXC |
| 상태 | IN_PROGRESS — 필수 인수 전 |

## 목표

- 세션 버전과 generation으로 오래된 오디오/연결 결과를 폐기한다.
- DB 원하는 상태와 외부 음성 실행 결과를 분리하여 중간 실패를 복구 가능한 상태로 남긴다.

## 추론 프로필 적용

[Jev API 전용 계약](../INFERENCE_PROFILES.md)을 따른다. 실제 자연어 판단은 `jev-api`만 사용하며 봇과 TLS 중계·영속 원장은 DiscordBotLXC에서 별도 계정으로 실행한다. 현재 배치는 [환경 계약](../ENVIRONMENT.md)을 따른다. `mock`은 지정 LXC의 격리 회귀 전용이다. 구조화 명령은 추론 없이 실행하고, API 장애가 기존 재생·슬래시·버튼을 막지 않게 한다.

## 로컬 코드 작업

로컬은 코드·문서 작성과 읽기 검토만 한다. 모든 설치·검사·시험·build·오디오 실행은 LXC에서 수행한다.

- DISCONNECTED·CONNECTING·IDLE·RESOLVING·PLAYING·PAUSED·STOPPING·RECONNECTING 전이를 명세 §6에 맞게 작성한다.
- guild당 한 실행 경로에서 상태 변경을 직렬화하고 DB session version과 메모리 session_generation을 함께 관리한다.
- resolver/연결/오디오 종료/재연결 알림에 generation을 결합하여 현재 세션과 일치할 때만 반영한다.
- DB desired_state 기록→외부 실행→결과 재검증/반영 단계를 분리한다. 검색·추론·미디어 연결 동안 긴 DB 쓰기/lock을 잡지 않는다.
- stop/leave/cancel에서 current entry를 같은 ID로 한 번만 앞에 보존하는 공통 전이를 작성한다. 자동 새 entry 생성으로 중복시키지 않는다.

## 산출물

- 재생 상태기계·세션 executor·취소 generation 코드.
- AudioSourceResolver/AudioPlayer 연결과 FakeAudioSource fixture.
- 허용/거절 상태 전이·DB/음성 중간 실패·콜백 충돌 표.

## LXC 검증

- DiscordBotLXC에서 상태 전이·중복 stop/leave·늦은 end/resolve/reconnect 단위·mock 시험을 수행한다.
- 현재곡 전환 뒤 이전 종료 콜백, 퇴장 뒤 resolve 완료, DB 반영 전후 프로세스 종료를 주입한다.
- 0.3.0 실제 허용 소스로 정상 연결/곡 전환을 확인하되 전체 기능 T 인수와 구분한다.

## 통과 기준

- 한 guild에 현재곡은 최대 1개이고 과거 generation 결과가 현재 세션을 바꾸지 않는다.
- 정지/퇴장의 동일 항목 이중 삽입 0건, 늦은 콜백으로 인한 자동 재입장/재생 0건이다.
- 원하는 상태와 실제 실패 결과가 구분되어 실패를 재생 성공으로 표시하지 않는다.

## 중단·후속 처리

- 중복 current·과거 콜백 실행·DB/오디오 상태 혼동이 있으면 실제 제어 기능 확대를 중단한다.
- 복구 전이는 04단계와 연결하고 장시간 장애·운영 관측은 0.8.0에서 강화한다.

[환경](../ENVIRONMENT.md) · [시험 추적](../TEST_MATRIX.md) · [증거 양식](../EVIDENCE_TEMPLATE.md) · [버전 목차](README.md)


## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
