# 1.0.0 Phase 4 — 배포 후 smoke와 감시

- 버전: `1.0.0`
- 단계: `4 / 5`
- 선행: [Phase 3](03_staged_deployment.md) 실제 단계적 배포 완료.
- 검증 호스트: `DiscordBotLXC`의 봇·별도 계정 중계
- 상태: **PLANNED — 필수 인수 전**
- 추론 계약: [프로필 선택·시험 실행](../INFERENCE_PROFILES.md), [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md), 내부 API schema `1.2`.

## 목표

- 배포 이후 실제 운영 연결·권한·저장·음성·자연어 상태를 다시 확인한다.
- 초기 이상 징후를 발견하면 문서화된 복구 경로로 되돌린다.

## 로컬 코드 작업

- 운영 데이터를 대량 변경하지 않는 소규모 smoke·정리 절차를 작성한다.
- 조회·DJ 편집·비DJ 거절·필수 확인·음성 연결·명시적 퇴장 사례를 포함한다.
- 선택한 운영 프로필의 자연어 조기 종료·조건부 3단계·timeout 미실행·API 인증 오류를 확인한다. 전송불명 요청은 예산 환불/재호출 없이 tombstone으로 남기고 자동 fallback이 없는지 확인한다.
- 공통 단계 지연·provider_calls·음성 실패·restart·DB 오류·디스크·backup 시각을 감시한다. hosted는 네트워크/TLS·401·429·5xx·호출/요금 한도를 분리 감시한다. hosted health를 위한 상시 유료 추론은 금지한다.
- 임계값 초과·기능 회귀·비밀 노출의 중단·rollback 조건을 운영 기록에 연결한다.

## 산출물

- 선택한 운영 프로필의 배포 후 smoke 목록·실제 결과·시험 데이터 정리 기록. 실행 시각·run_id·provider/profile_id/config_hash·모델/API·prompt/threshold를 manifest와 연결하고 시험 프로필의 이전 증거와 혼합하지 않는다.
- 초기 관찰 기간·확인 빈도·담당·이상 기준을 정한 운영 관찰 기록.
- backup 성공·외부 복사본 확인·마지막 복원 증거·복구 가능한 후보 목록.

## LXC 검증

- `DiscordBotLXC`: 운영 allowlist 안에서 작은 시험 목록·큐·권한·음성을 확인한다.
- `DiscordBotLXC의 중계`: 공통 ready·단일 dispatch·최대 3회 provider_calls 원장·queue·TLS·지연을 확인한다.
- DiscordBotLXC의 봇·중계: gateway/선택 provider 장애 시 기본 기능·늦은 응답 폐기·service 정상 종료 정책을 확인한다. 운영 smoke를 위해 다른 프로필로 hot switch하거나 기존 불명 요청을 재전송하지 않는다.
- 파괴적 장애 주입은 분리된 시험 DB/service에서 수행하고 운영 저장소를 손상시키지 않는다.
- smoke·로그·metrics·build·test 실행은 원격에서만 수행하고 민감값을 제거해 기록한다.

## 통과 기준

- 배포 후 기본 기능·권한·확인·음성·자연어 smoke가 같은 manifest에서 통과한다.
- 지속적 음성 끊김·오류 급증·OOM 루프·잘못된 실행·비밀 노출이 없다.
- backup·외부 복사본·복구 후보가 실제 접근 가능하고 보존 정책이 적용된다.
- 배포 설정 차이로 선택 프로필의 RC 성능·안전 기준이 깨지면 최종 완료로 기록하지 않는다. 운영 smoke 성공이 RC 미실행/실패를 대체하지 않는다.

## 중단·후속 처리

- 이상 발생 시 신규 변경을 제한하고 안전한 기능만 유지하며 원인을 기록한다.
- 앱만 덮어쓰는 임의 rollback 대신 검증한 스키마·backup 절차를 따른다.
- 복구·수정 뒤 새 후보의 영향 검증과 배포 후 smoke를 반복한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
