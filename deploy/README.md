# 설정과 배포 템플릿

이 디렉터리는 비밀 없는 예시만 Git에 포함합니다. 설정 loader·프로필 선택·서비스 진입점은 개발 구현했으며 [원격 runbook](../docs/REMOTE_DEVELOPMENT.md)의 제한 설정/경로를 사용합니다. 템플릿은 그대로 실행/설치할 수 없습니다.

- `config.example.yaml`: 명세 §12의 공통 앱 정책·기한·저장 경로 예시. 프로필의 inference 블록을 따로 결합합니다.
- `profiles/eval-jev-api-single-lxc-v1.yaml`: 현재 한 LXC 배치의 개발평가 목적·최대3000 호출 템플릿. 이전 `eval-jev-api.yaml`(v2)과 v3/v4/v5는 과거 고정 후보의 기록으로 보존합니다.
- `profiles/jev-api.yaml`: 실제 판단/smoke 전용20 호출. `profiles/mock.yaml`: 명시 격리 시험 전용이며 Discord 서비스 활성화 금지.
- `bot.env.example`: Discord 봇·내부 API 인증값의 이름만 정의.
- `gateway.env.example`: 내부 API 인증·hosted 외부키의 이름만 정의.
- `systemd/*.service.example`: 비root·권한/재시작·정상종료 정책의 미설치 초안. 실제 executable/계정/경로는 원격 검증 후 확정합니다.

프로필 파일은 `inference`에 결합할 mapping입니다. 공통 기본값 → 선택한 프로필 → 허용 비밀 환경변수 순서로 구성합니다. `config_hash`와 run별 격리 경로는 선택 도구가 계산·검증합니다. local 설정/비지원 provider는 거절하며 모델 모듈/가중치를 로드하지 않습니다.

예시 환경 파일은 실제 키를 포함하지 않습니다. 복사한 `bot.env`/`gateway.env` 및 실제 환경/개인 설정 파일은 ignore 대상이며 지정 LXC의 권한 제한 경로에서 준비합니다. `.private` 원본을 source하거나 일반 소스 동기화에 포함하지 않습니다.

[명세 §12](../Plans/CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md#s12) · [프로필 계약](../Plans/0.DevPhase/INFERENCE_PROFILES.md) · [운영 runbook](../docs/OPERATIONS.md)
