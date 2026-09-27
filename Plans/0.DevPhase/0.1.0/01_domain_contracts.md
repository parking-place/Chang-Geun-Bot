# 0.1.0 01 — 도메인 경계와 명령 계약

| 항목 | 내용 |
| --- | --- |
| 버전 | 0.1.0 |
| 단계 | 01 / 05 |
| 선행 조건 | 0.0.0의 명세·환경·위험 기준선 |
| 검증 호스트 | DiscordBotLXC |
| 상태 | IN_PROGRESS — 필수 인수 전 |

## 목표

- Discord·모델 라이브러리 없이 서버별 곡·저장 목록·대기열·현재곡을 표현한다.
- 구조화 입력과 자연어 입력이 같은 ActionPlan·정책·실행기를 사용하도록 계약을 정한다.

## 추론 프로필 적용

[Jev API 전용 계약](../INFERENCE_PROFILES.md)을 따른다. 실제 자연어 판단은 `jev-api`만 사용하며 봇과 TLS 중계·영속 원장은 DiscordBotLXC에서 별도 계정으로 실행한다. 현재 배치는 [환경 계약](../ENVIRONMENT.md)을 따른다. `mock`은 지정 LXC의 격리 회귀 전용이다. 구조화 명령은 추론 없이 실행하고, API 장애가 기존 재생·슬래시·버튼을 막지 않게 한다.

## 로컬 코드 작업

로컬에서는 아래 코드·문서 작성과 읽기 검토만 한다. 설치·lint·타입검사·시험·build는 LXC에서 수행한다.

- 명세 §10.1 엔티티와 §18.2 디렉터리를 기반으로 도메인 타입·저장 인터페이스를 작성한다. 구현 규모는 실제 필요 범위로 제한한다.
- Discord snowflake는 문자열, 내부 대상은 안정적인 UUID로 표현한다. track ID와 playlist/queue entry ID를 구분한다.
- 원제목·게시 채널·운영자 표기 제작자·별칭·태그를 분리한다. 저장 목록에서 복사한 대기열 항목은 별도 ID와 순서를 가진다.
- ActionPlan에 인증된 actor/guild, allowlist action, DB 대상 ID, expected_versions, 확인 필요 여부, 요청/판단·질문·provider_calls 누계를 정의한다. provider/profile_id/비밀값 제외 config hash는 봇·게이트웨이의 검증된 요청 문맥에 고정하고 모델이 변경할 수 없게 한다.
- playback 상태·취소 generation·요청 상태·확인 상태의 전이와 오류 코드를 정의한다. 미해결 후보를 실행 계획으로 승격하지 않는다.

## 산출물

- 도메인 엔티티·값 타입·저장/외부 어댑터 인터페이스 소스.
- playlist.*·queue.*·playback.*·voice.*·catalog.*·proposal.*·settings.* 동작별 인자·권한·확인·상태 계약표.
- 초기 ActionPlan 스키마와 도메인 fixture 설계. future 기능은 구현 여부를 구분한다.

## LXC 검증

- DiscordBotLXC에서 타입·입력 스키마·도메인 단위시험을 실행한다. 설치·lint·타입검사도 해당 LXC에서만 수행한다.
- 큰 snowflake 문자열 왕복, 항목 ID/곡 ID 혼동, 타 guild 대상, 미등록 action·추가 인자·미해결 필드 입력을 검사한다.
- 단순 음악 목록 저장과 대기열 복사를 fixture로 분리하여 두 객체의 변경 전파 여부를 확인한다.

## 통과 기준

- Discord/모델 import 없이 도메인 코드가 검증되며 ID 손실과 다른 guild 대상 연결이 발생하지 않는다.
- 모델이 보낸 actor·역할·실행 승인을 신뢰하는 계약이 없고 모든 action에 정책 정의가 있다.
- 단위시험 증거를 남긴다. T-07·08 최종 재생 통과로 표시하지 않는다.

## 중단·후속 처리

- 명세 해석 충돌은 결정 기록과 관련 계획을 수정한 뒤 계속한다.
- 실제 소스·Discord·음성·Jev API/OpenJev 연결은 0.2.0 이후 의존 단계로 넘긴다.

[환경](../ENVIRONMENT.md) · [시험 추적](../TEST_MATRIX.md) · [증거 양식](../EVIDENCE_TEMPLATE.md) · [버전 목차](README.md)


## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
