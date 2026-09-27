# 0.8.0 — 장애 복구와 운영 체계

- 상태: **계획 / 미구현 / 미검증**
- 선행 버전: [0.7.0](../0.7.0/README.md)의 기능·편의 기능 검증 완료.
- 명세 근거: [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) §13~16, §17.4, §19.
- 대상: `DiscordBotLXC`의 봇·별도 계정 중계. 기존 privileged LXC를 보존하고 앱은 비root 계정으로 실행한다.
- 로컬 범위: 코드·테스트 코드·운영 문서 작성. 설치·lint·빌드·모든 실행 검증은 DiscordBotLXC의 봇·중계에서만 수행한다.

## 범위

장애·취소·기한·정상 종료 정책을 서비스 운영과 연결하고, 일관성 백업·분리된 복원·관측·개인정보 삭제·업데이트 복구 절차를 갖춘다. `jev-api`를 명시 선택해 같은 안전·복구 시험을 수행한다. Jev API 모드에는 로컬 모델·torch 설치를 요구하지 않는다. 기능이 만들어졌다는 기록과 실제 운영 시험 PASS를 분리한다.

예정 runner의 `test-profile --profile <name> --suite <suite>`는 프로필에 대응하는 설정·분리 DB/원장·증거 경로를 함께 선택한다. `--dry-run`은 설정만 점검하며 실추론 PASS가 아니다. 시험 전환은 신규 요청 중지·drain·새 `run_id`/세션으로 수행하고, 이전 불명 요청 tombstone을 보존한다. 운영 전환은 별도 프로필 지정·재시작·rollback 절차로 관리한다.

## 단계

1. [01 — 장애·취소·복구 정책](01_failure_cancellation.md)
2. [02 — systemd와 프로세스 수명](02_systemd_lifecycle.md)
3. [03 — 일관성 백업과 분리된 복원](03_backup_restore.md)
4. [04 — 관측·로그·개인정보](04_privacy_observability.md)
5. [05 — 운영·업데이트·롤백 훈련](05_operations_drill.md)

## 버전 통과 조건

장애 주입 중 잘못된 실행·거짓 성공·원치 않는 자동 재생이 없어야 한다. 두 서비스의 재시작 제한, 독립 기동, 일관성 백업과 노드 밖 복사본, 실제 복원 및 롤백 절차를 같은 커밋의 run별 원격 증거로 확인한다. 자동 프로필 선택·자동 fallback·요청 도중 provider 변경·불명 요청 재전송은 허용하지 않는다. 이 버전 통과만으로 운영 승격을 수행하지 않는다.

## 공통 문서

- [환경·원격 실행 규칙](../ENVIRONMENT.md)
- [시험 매트릭스](../TEST_MATRIX.md)
- [검증 증거 양식](../EVIDENCE_TEMPLATE.md)

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
