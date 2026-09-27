# 1.0.0 — 검증한 후보의 정식 운영 출시

- 상태: **계획 / 미구현 / 미검증**
- 선행 버전: [0.9.0](../0.9.0/README.md)의 모든 필수 출시 게이트 통과.
- 명세 근거: [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) §11, §14~17, §19.
- 대상: `DiscordBotLXC`의 봇·별도 계정 중계. 기존 LXC를 활용하며 비root 서비스와 분리된 검증 컨텍스트를 유지한다.
- 로컬 범위: 출시 자료·도움말·배포 코드 작성. 설치·lint·빌드·시험·배포 실행은 DiscordBotLXC의 봇·중계에서만 수행한다.

## 범위

0.9.0에서 `jev-api`로 통과한 후보와 run별 설정을 고정하고, 운영에 사용할 프로필 하나를 명시해 단계적으로 배포한다. hosted 배포에는 모델/torch를 요구하지 않는다. 배포 뒤 선택한 운영 프로필의 기능·권한·음성·자연어·백업 상태를 확인한다. 고정 Jev API 운영 프로필과 후보 증거를 기록한다. 이번 계획 작성은 실제 배포·공개·태그 발행을 수행하거나 완료로 선언하지 않는다.

테스트 선택은 예정 runner의 `test-profile --profile <name> --suite <suite>`로 설정·격리 경로·증거를 함께 선택하며 `--dry-run`은 순수 설정 점검이다. 운영 프로필 변경은 별도 manifest 지정·신규 접수 중지·drain·이전 불명 tombstone 보존·새 실행 세대/세션·재시작·smoke·실패 시 명시적 rollback을 거친다. 자동 fallback·요청 도중 hot switch·이전 불명 요청 재전송은 허용하지 않는다.

## 단계

1. [01 — 출시 manifest와 후보 일치](01_release_manifest.md)
2. [02 — 도움말·지원 범위 확정](02_help_support_contract.md)
3. [03 — 단계적 실제 배포](03_staged_deployment.md)
4. [04 — 배포 후 smoke와 감시](04_postdeployment_checks.md)
5. [05 — 최종 증거와 출시 종료](05_release_closure.md)

## 버전 통과 조건

운영에 배포된 코드·의존성·스키마·provider/profile_id/config_hash·모델 정보·프롬프트/임계값이 해당 프로필의 검증 후보와 일치하고, 배포 후 필수 smoke·복구·백업 확인이 통과해야 정식 완료로 기록한다. Jev API 후보의 0.9.0 안전·한국어·성능·8시간 증거를 유지하며 미통과 프로필을 지원 범위에서 묵시적으로 제외하지 않는다. 출시 필수 소스·권한·3회 예산·한국어·복원 게이트가 남으면 승격하지 않는다. 사용자 승인된 변경 범위에 따라 승인 음원 재생과 YouTube 링크·목록 관리가 1.0.0 필수다. 직접 오디오 추출·전송은 제외하되 승인 음원 인수 실패는 출시에 차단 사유다.

## 공통 문서

- [환경·원격 실행 규칙](../ENVIRONMENT.md)
- [시험 매트릭스](../TEST_MATRIX.md)
- [검증 증거 양식](../EVIDENCE_TEMPLATE.md)

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
