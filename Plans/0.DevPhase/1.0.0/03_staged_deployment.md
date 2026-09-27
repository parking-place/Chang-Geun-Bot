# 1.0.0 Phase 3 — 단계적 실제 배포

- 버전: `1.0.0`
- 단계: `3 / 5`
- 선행: [Phase 2](02_help_support_contract.md), 0.9.0 전 필수 인수 PASS.
- 검증 호스트: `DiscordBotLXC`의 별도 계정 중계·봇
- 상태: **PLANNED — 필수 인수 전**
- 추론 계약: [프로필 선택·시험 실행](../INFERENCE_PROFILES.md), [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md), 내부 API schema `1.2`.

## 목표

- 검증한 후보를 기존 DiscordBotLXC의 봇·중계에 단계적으로 적용하고 실제 운영 상태를 확인한다.
- 데이터·비밀값·기존 LXC를 보존하면서 이상 발생 시 복구 가능한 변경을 수행한다.

## 로컬 코드 작업

- 운영 프로필 하나를 manifest로 명시하고 사전 backup·후보/설정 비교·비밀값 주입·신규 접수 중단·drain·service 재시작·health 순서를 배포 코드에 반영한다. 이전 불명 요청 tombstone을 보존하고 새 실행 세대/세션을 사용한다.
- 공통 gateway의 live/ready·내부 인증/TLS·봇과 provider/profile_id/config_hash 일치를 확인한 뒤 자연어를 활성화한다. 주기 health는 유료 추론을 수행하지 않는다.
- 봇 DB 마이그레이션·구조화 명령·DAVE/음성·허용 소스 확인을 개별 단계로 나눈다.
- 테스트 guild 확인 뒤 확정한 운영 allowlist에 한정해 실제 운영 연결을 전환한다.
- 실패 단계·로그·되돌릴 후보/프로필·스키마 호환 조건에 따른 중단/rollback을 명시한다. 자동 provider fallback·hot switch·SDK retry 없이 같은 중지/drain·명시 선택·재시작 순서로 복구한다. 봇 재시작에 따른 재생 중단을 운영 안내에 포함한다.

## 산출물

- 실제 파일·진입점에 근거한 배포 절차와 단계별 확인 목록.
- 배포 전 일관성 backup·외부 복사본·rollback manifest.
- 실제 실행 시각·SHA·provider/profile_id/config_hash·서비스 상태·migration 결과를 남길 배포 기록. 양쪽의 RC 증거 링크는 보존하고 운영 선택이 미통과 경로 제외를 의미하지 않게 한다.

## LXC 검증

- `DiscordBotLXC의 중계`: 비root gateway의 TLS·원장·ready·단일 dispatch와 선택 프로필을 확인한다.
- `DiscordBotLXC`: 백업 뒤 검증한 migration·비root service·테스트 명령을 적용한다.
- DiscordBotLXC의 봇·중계: 테스트 guild에서 확인된 후보와 동일한 운영 설정 차이만 적용한다.
- 운영 allowlist·DJ·권한·음성 소스·최대 3판단/질문·request_provider_calls_total≤3의 동작을 작은 범위로 확인한다.
- 설치·빌드·lint·service 기동·배포 실행을 로컬에서 수행하지 않는다.

## 통과 기준

- 실제 운영 서비스가 manifest와 같은 후보로 실행되고 제한된 비root 권한을 사용한다.
- 필수 health·DB·Discord·DAVE·허용 소스·자연어 연동이 단계별로 통과한다.
- 설정 미완료·gateway/provider 장애·프로필 불일치가 임의 전체 허용·다른 provider 자동 호출·음성 자동 재개를 만들지 않는다.
- 문서 작성·태그 존재가 아닌 실제 배포 결과로 진행 상태를 기록한다.

## 중단·후속 처리

- 필수 게이트 실패·후보 불일치·DB 오류이면 이후 승격을 멈추고 검증한 복구를 수행한다.
- DB 삭제·LXC 재생성 등 파괴적 변경이 필요하면 구체적 영향·복구안을 먼저 준비한다.
- 성공한 실제 배포 기록을 확보한 뒤 Phase 4에서 운영 smoke를 수행한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
