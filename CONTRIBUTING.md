# 개발 안내

[명세 1.3](Plans/CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md)와 [해당 버전 계획](Plans/0.DevPhase/README.md)을 먼저 읽고 작업 범위와 인수 시험을 정합니다. 구조·패키지 메타데이터가 준비됐어도 실제 구현과 시험은 별도입니다.

현재 제품 실행은 [결정0008](docs/decisions/0008-single-lxc-jev-api.md)에 따라 DiscordBotLXC의 봇·별도 계정 중계에서 수행합니다. OpenJevLXC에 새 작업을 수행하지 않습니다.

## 변경 절차

1. 코드·시험·설정 예시·문서를 로컬에서 작성합니다. 도메인이 Discord/모델 라이브러리에 의존하지 않게 합니다.
2. `python3 scripts/check_repository.py`로 공개 후보와 문서/설정 파일을 점검합니다.
3. revision을 고정하고 비공개 파일과 데이터 경로를 제외해 지정 LXC에 전달합니다.
4. 해당 LXC에서 의존성·lock 생성/검증, 설치·lint·타입/빌드·필요 시험을 수행합니다.
5. [증거 양식](Plans/0.DevPhase/EVIDENCE_TEMPLATE.md)에 프로필·revision·실제 결과를 기록하고 [STATUS](Plans/0.DevPhase/STATUS.md)를 갱신합니다.

처음 만드는 기능은 명확한 실패/미지원 상태를 사용합니다. 빈 시험 모음·skip·mock·문서 CI만으로 VERIFIED/DONE을 표시하지 않습니다. [tests 안내](tests/README.md)를 따릅니다.

## 프로필과 의존성

`bot/pyproject.toml`과 `inference/pyproject.toml`은 초기 패키지 메타데이터입니다. LXC 개발 후보에는 의존성 제약과 wheel/바이너리 manifest를 기록했습니다. gateway console entry point와 봇 실행 모듈을 구현했으며 정식 출시용 잠금/전체 인수는 아직 완료 전입니다. 버전 `0.0.0.dev0`은 패키지 초기 메타데이터이며 0.0.0 단계 완료 또는 제품 출시 번호가 아닙니다.

봇과 Jev API 게이트웨이 의존성/lock을 분리합니다. hosted를 설치할 때 모델 런타임을 import/다운로드하지 않습니다. 도구 설정은 루트 `pyproject.toml`에 있고, 도구 설치·실행도 LXC에서 수행합니다.

## PR에 기록할 내용

문제와 결과 동작, 영향을 받는 버전/계약, 실제 LXC 검증과 미실행 항목을 기록합니다. Jev 관련 변경은 실제 API와 mock 증거를 구분하고 hosted dispatch를 실측 forward로 표시하지 않습니다. 비밀값·실제 Discord ID·원문·접속 주소를 PR/이슈에 붙이지 않습니다.

[Git 업로드 안내](docs/GIT_SETUP.md) · [원격 개발 runbook](docs/REMOTE_DEVELOPMENT.md)
