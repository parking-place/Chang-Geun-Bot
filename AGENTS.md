# 저장소 작업 지침

## 작업 기준

- 최신 기준은 `Plans/CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md`와 `Plans/0.DevPhase/`다. 먼저 해당 버전 계획, `STATUS.md`, `ENVIRONMENT.md`, `INFERENCE_PROFILES.md`를 읽는다.
- 현재는 개발 구현·LXC 검증 진행 중이다. 빈 디렉터리·설정 템플릿·저장소 CI와 부분 시험 통과를 전체 기능 인수·출시 PASS로 표시하지 않는다.
- 1.0.0 재생 범위는 승인 음원과 YouTube 링크/목록 관리다. `docs/decisions/0003-approved-audio-release-scope.md`를 따르며 직접 YouTube 오디오 추출·전송을 활성화하지 않는다.
- 1.0.1/1.0.2의 후속 범위는 `docs/decisions/0006-youtube-and-prefix-roadmap.md`와 해당 버전 계획을 함께 적용한다. 현재 IN_PROGRESS이며 1.0.0 제한을 소급 제거하거나 계획만으로 기능·Discord intent를 활성화하지 않는다.
- 1.0.3 주시 채널 관리는 사용자 구현 요청으로 IN_PROGRESS다. `docs/decisions/0007-watch-channel-management.md`와 해당 버전5단계·실행 증거를 따른다. 구현/개발 후보와 W 전건 실제 인수·정식 출시를 구분한다. 기존 DB/바이너리 복귀 묶음과 gateway 예산을 보존한다.
- 1.1.0~1.1.7 후속 계획은 `Plans/1.PatchPhase/`의 README·EXECUTION_RULES·ITEM_COVERAGE·STATUS·TEST_MATRIX와 해당 버전 README를 따른다. 현재 1.1.0 개발 후보·부분 시험 진행 중, 1.1.1~1.1.7 PLANNED다. 계획/부분 시험만으로 정식 VERSION·태그·DONE을 만들지 않는다. 기존 미완료 인수와 후보별 증거를 유지한다.
- 사용자의 요청 범위를 따른다. 구현·시험 증거 없이 제품 `VERSION`, 출시 태그, 완료 상태를 만들지 않는다.

## 비공개 정보와 데이터

- `.private/`는 사용자가 지정한 입력을 확인할 때만 필요한 범위에서 읽는다. 키·접속 정보는 출력하거나 공개 문서/예시/로그/argv에 넣지 않는다.
- `.private/`, 환경 파일, 운영 DB/원장, 모델·캐시·로그·백업을 Git에 추가하지 않는다. 이 파일들을 강제 추가하거나 ignore를 해제해 업로드하지 않는다.
- 기존 변경과 운영 데이터를 보존한다. 동기화·복원은 격리된 테스트 경로를 사용한다.
- 내부 `JEV_API_TOKEN`과 hosted `JEV_HOSTED_API_KEY`는 서로 다른 인증값이다. 외부 키는 게이트웨이에서만 읽는다.

## 실행 위치

- 로컬 PC에서는 코드·설정·문서를 작성/검토하고 Git 메타데이터를 관리한다.
- `scripts/check_repository.py`는 저장소 파일/문서 검사 전용으로 로컬과 GitHub Actions에서 실행할 수 있다. 제품 모듈 import·설치·빌드·DB/모델/API 실행을 추가하지 않는다.
- 현재 제품 lint·타입 검사·단위/mock·통합·실제 Discord/음성·API 시험은 DiscordBotLXC에서만 수행한다. 원격 실패 뒤 로컬 시험으로 fallback하지 않는다.
- 실제 LXC 명령과 실행 모듈은 구현 및 원격 검증 뒤 runbook에 기록한다. 미구현 명령을 완성형 실행법처럼 적지 않는다.
- 2026-09-28 사용자는 OpenJevLXC를 더 이상 사용하지 않는다고 명시했다. 현재 제품 시험·봇·Jev API 중계는 DiscordBotLXC에서 수행한다. `docs/decisions/0008-single-lxc-jev-api.md`의 별도 `changgeun-gateway` 계정/loopback TLS를 쓰며, OpenJevLXC에 새 작업/모델/서비스를 적용하지 않는다. 이전 서버의 DB·원장·예산·역사는 보존한다. 새 실행 epoch/profile을 재시작 때 갱신하거나 예산을 초기화하지 않는다.

## 구조와 계약

- `bot`은 Discord·DB·재생·권한·공통 실행기, `inference`는 공통 판단 API·원장·제공자 어댑터다. 모델은 동작을 실행하지 않는다.
- 실제 제공자는 `jev-api`만 지원한다. `docs/decisions/0005-jev-api-only.md`를 따른다. `mock`은 지정 LXC의 격리 시험 전용이며 실제 Discord에 활성화하지 않는다. 로컬 모델 경로/의존성을 새 실행에 연결하지 않는다.
- API 1.2를 따른다. 판단/질문/provider dispatch는 요청당 최대3회다. hosted 내부 forward는 null/unavailable로 남긴다.
- 변경 후 해당 문서·설정 예시·시험 추적을 함께 갱신한다. LXC 증거가 없는 단계는 PLANNED/진행 중 상태로 유지한다.
