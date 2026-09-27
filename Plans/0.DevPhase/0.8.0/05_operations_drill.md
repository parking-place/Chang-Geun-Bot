# 0.8.0 Phase 5 — 운영·업데이트·롤백 훈련

- 버전: `0.8.0`
- 단계: `5 / 5`
- 선행: [Phase 4](04_privacy_observability.md), Phase 1~3 원격 증거 확보.
- 검증 호스트: `DiscordBotLXC`의 봇·별도 계정 중계
- 상태: **PLANNED — 필수 인수 전**
- 추론 계약: [프로필 선택·시험 실행](../INFERENCE_PROFILES.md), [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md), 내부 API schema `1.2`.

## 목표

- 같은 후보의 업데이트·장애 대응·복원·롤백 절차를 실제 시험한다.
- 운영자가 장애 범위와 복구 조건을 판단할 수 있는 runbook을 마련한다.

## 로컬 코드 작업

- 배포 커밋·run별 잠금 파일·provider/profile_id·스키마·프롬프트/임계값·설정 fingerprint의 묶음을 정의한다.
- 변경 전 일관성 백업, 마이그레이션 호환성, 단계별 health 확인을 배포 절차에 넣는다.
- 앱 rollback과 DB rollback을 구분하고 미검증 역마이그레이션을 금지한다.
- 모델/공급자 설정 변경은 같은 fixture·seed·원본 snapshot·안전 정책으로 품질·거절률·지연을 비교한 뒤 이전 프로필 설정·정책으로 되돌릴 경로를 작성한다.
- hosted endpoint·단가·한도·외부 보존 정책은 보호 설정에서 확인한 근거와 시각을 기록하며 값을 추정하지 않는다.

## 산출물

- 운영 점검·장애 triage·업데이트·롤백·모델 교체 runbook과 변경 이력 양식. 시험은 예정 runner의 `test-profile --profile jev-api --suite operations`로 설정/DB/원장/증거를 함께 선택하며, 운영은 별도 프로필 지정·중지/drain·재시작·health·rollback 절차를 따른다.
- 테스트 컨텍스트의 실제 릴리스 묶음·마이그레이션 호환표·rollback 후보.
- 0.8.0 인수표와 0.9.0에서 반복할 필수 위험 목록.

## LXC 검증

- `DiscordBotLXC`: 시험 DB로 업데이트·실패·되돌리기를 수행하고 큐·목록을 확인한다.
- `DiscordBotLXC의 중계`: Jev API의 readiness 실패·이전 설정/정책 복귀를 시험하고 원장 수명을 확인한다. 전환 시 새 run_id/세션을 발급하고 이전 불명 요청 tombstone 유지·재전송 금지·요청 중 provider 고정을 확인한다.
- DiscordBotLXC의 봇·중계: 인증서·API 통신·음성 네트워크 장애와 프로세스 종료를 주입한다.
- 분리 경로의 백업을 복원하고 운영 guild·DB 접속이 차단되는지 확인한다.
- 모든 실행은 원격에서 수행하며 커밋·호스트·설정·변경 전후 상태를 남긴다.

## 통과 기준

- 운영 문서의 절차가 실제 원격 실행 결과와 일치한다.
- Jev API의 백업·복원·rollback 후 데이터 손상·중복 명령·자동 음성 재개가 없다. 자동 fallback/SDK retry가 없고 프로필 간 시험 DB/원장/증거가 섞이지 않는다.
- 오류 원인과 Jev 장애 중 유지되는 기본 기능을 운영자가 구분할 수 있다.
- 남은 필수 실패를 숨기지 않고 0.9.0 선행 조건으로 기록한다.

## 중단·후속 처리

- rollback 불가·스키마 불일치·복원 실패이면 RC 진행을 보류한다.
- 변경된 코드·잠금 파일로 기존 PASS를 재사용하지 않고 영향 범위를 재검증한다.
- 전 단계 증거가 모이면 [0.9.0](../0.9.0/README.md) 후보 고정으로 진행한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
