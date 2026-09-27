# 1.0.0 Phase 1 — 출시 manifest와 후보 일치

- 버전: `1.0.0`
- 단계: `1 / 5`
- 선행: [0.9.0](../0.9.0/README.md) 전 필수 게이트 통과.
- 검증 호스트: `DiscordBotLXC`의 봇·별도 계정 중계
- 상태: **PLANNED — 필수 인수 전**
- 추론 계약: [프로필 선택·시험 실행](../INFERENCE_PROFILES.md), [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md), 내부 API schema `1.2`.

## 목표

- RC에서 검증한 불변 후보를 그대로 운영 배포의 기준으로 고정한다.
- 계획 문서·태그·버전 문자열을 실제 배포 완료 증거와 구분한다.

## 로컬 코드 작업

- 후보 SHA·bot/gateway 및 provider별 잠금 파일·API schema `1.2`·provider/profile_id/config_hash·prompt/threshold·안전 정책을 묶는다. hosted는 어댑터/API 버전·요청/반환 모델·측정시각·고정 불가 한계를 기록한다.
- 설정 fingerprint·서비스 unit·마이그레이션·아티팩트 checksum과 증거 링크를 연결한다.
- 앱 버전 문자열·메타데이터·도움말 변경이 RC 뒤 추가되면 새 후보로 처리한다.
- 운영 설정과 테스트 설정의 차이를 허용 목록으로 명시하고 보안·성능 영향을 검토한다. Jev API 프로필 지원 증거와 실제 활성화할 운영 프로필 하나를 구분한다. provider·모델·prompt/threshold 변경을 단순 경로/비밀값 주입 차이로 취급하지 않는다.
- 실제 배포 전 백업·되돌릴 후보/프로필·스키마 호환 조건·실패 중단 기준을 manifest에 넣는다. hosted는 확인한 endpoint/인증/한도·단가·외부 전송/보존 정책의 근거와 시각을 연결하며 값을 추정하지 않는다.

## 산출물

- 1.0.0 release manifest와 후보별 전체 인수 증거 묶음.
- 테스트/운영 설정 차이표, run별 잠금 파일·모델 정보·DB revision·데이터 경로의 재현 기록.
- 실제 완료 뒤 사용할 release note 초안과 현재 미배포 상태 기록.

## LXC 검증

- DiscordBotLXC의 봇·중계: 운영에 선택한 프로필의 RC 코드·잠금 파일·스키마·prompt/threshold checksum/SHA와 provider/profile_id/config_hash를 확인한다. 봇과 gateway가 예상 프로필/설정에 불일치하면 자연어를 잠근다.
- `DiscordBotLXC`: 서비스 진입점·음성 의존성·마이그레이션·백업 후보를 확인한다.
- `DiscordBotLXC의 중계`: 공통 gateway 단일 worker/dispatch·인증·TLS·영속 원장을 확인한다.
- 새 설치·lint·빌드가 필요하면 해당 LXC에서 같은 잠금 파일로 수행한다.
- 비밀값은 제한된 환경 경로에서 제공하며 공개 manifest에는 실제 값을 담지 않는다. hosted JEV_HOSTED_API_KEY는 gateway 전용이며 내부 JEV_API_TOKEN과 별개다. 테스트/운영 키·DB·원장·서비스·증거 경로를 분리한다.

## 통과 기준

- 배포할 후보와 0.9.0 PASS 후보의 내용·환경 계약이 일치한다.
- 후보 내용이 바뀌었으면 영향 검증을 다시 수행한 증거가 존재한다.
- Jev API의 필수 차단 목록이 비어 있고 승인 음원·YouTube 링크/목록 관리의 인수가 완료되어야 한다. 직접 YouTube 오디오는 범위 제외/비활성으로 표시한다. 한쪽 미통과를 제외하려면 먼저 명세·인수 기준의 범위 변경 결정을 남긴다.
- 릴리스 manifest 작성만으로 정식 출시 완료를 선언하지 않는다.

## 중단·후속 처리

- SHA·provider/profile_id/config_hash·모델 정보·스키마 불일치이면 배포를 시작하지 않는다. hosted 모델 변경/고정 불가 한계로 RC 적용 여부를 판단할 수 없으면 재검증하거나 제한 결정을 문서화한다.
- 최신 브랜치 자동 다운로드·서비스 기동 중 의존성 업데이트를 허용하지 않는다.
- 후보와 복구 조건을 고정한 뒤 Phase 2 지원 문서를 확정한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
