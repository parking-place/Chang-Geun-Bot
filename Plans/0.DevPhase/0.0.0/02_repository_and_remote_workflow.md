# 0.0.0 / 02 — 코드 구조와 원격 검증 루프

| 항목 | 내용 |
| --- | --- |
| 버전·단계 | 0.0.0 / 2단계 |
| 상태 | IN_PROGRESS — 필수 인수 전 |
| 선행 조건 | [01단계](01_scope_and_contracts.md) REVIEWED — 문서 계약 검토 증거 |
| 검증 호스트 | DiscordBotLXC + DiscordBotLXC의 중계 |
| 명세 기준 | [개발 명세 1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) |

## 목표

향후 코드는 로컬에서 작성하고 지정 LXC에서만 검증할 수 있는 재현 가능한 개발 흐름을 만든다. 초기 runner 설치에 필요한 최소 LXC 준비를 이 단계에서 먼저 수행한다.

## 추론 프로필 적용

[Jev API 전용 계약](../INFERENCE_PROFILES.md)을 따른다. 실제 자연어 판단은 `jev-api`만 사용하며 봇과 TLS 중계·영속 원장은 DiscordBotLXC에서 별도 계정으로 실행한다. 현재 배치는 [환경 계약](../ENVIRONMENT.md)을 따른다. `mock`은 지정 LXC의 격리 회귀 전용이다. 구조화 명령은 추론 없이 실행하고, API 장애가 기존 재생·슬래시·버튼을 막지 않게 한다.

## 로컬 코드 작업

- 향후 Git 추적·ignore 규칙을 작성한다. 비밀값·.private·venv·DB·모델 캐시·로그·백업은 제품 소스 동기화에서 제외한다.
- hosted 프로필 설치에 모델 런타임/가중치 다운로드를 요구하지 않는 lock·runner 진입점을 작성한다.
- 도메인이 Discord/model 라이브러리에 의존하지 않게 경계를 정하고 FakeDiscordGateway/FakeAudioSource/MockJevAdapter 계약을 설계한다.
- 원격 명령의 실행 서버를 이름으로 지정하는 개발 스크립트를 작성한다. 로컬 fallback이나 SSH 실패 뒤 로컬 pytest 실행 경로를 넣지 않는다.
- 구현한 `python3 scripts/test_profile.py --profile jev-api|mock --suite contract|activate|status|transport`와 `--dry-run`을 사용한다. 실제 SSH 설정/인자는 원격 runbook을 따른다. 키 존재로 자동 선택하거나 실패 뒤 다른 경로로 전환하지 않는다.
- 프로필 하나로 설정·분리 시험 DB/원장·필요 의존성·증거 경로를 선택한다. dry-run은 비밀값 없이 파일·설정·선택 범위만 확인하며 네트워크·모델 실행·데이터 변경을 하지 않는다. 새 후보/설정은 test bot/gateway를 drain·중지한 뒤 검증된 run에서 활성화하며 미완료/불명 요청을 재실행하지 않는다.
- 격리된 시험 경로에 동일 revision을 전달하고 데이터 경로를 제외하는 동기화 규칙·dry-run 확인 절차를 문서화한다.

## 산출물

- 초기 소스 구조·의존성 정의·테스트/배포 스크립트 초안과 실제 진입점이 생긴 뒤 채울 원격 실행 runbook.
- 코드 SHA/lock hash/설정 hash를 담는 배포 manifest와 증거 수집 구조.
- 각 LXC의 최소 비root 시험 계정·분리 경로·Python 준비 결과.

## LXC 검증

- venv/설치/runner보다 먼저 DiscordBotLXC의 봇·중계의 기본 접근·Python 가용성을 확인하고 비root 시험 계정과 독립된 시험 경로·필요 쓰기 권한을 마련한다. 운영 계정/DB/서비스 경로를 재사용하거나 덮어쓰지 않는다.
- 최소 준비 후 DiscordBotLXC에 봇 가상환경, DiscordBotLXC의 중계에 공통 게이트웨이 가상환경을 마련하고 각 잠금 파일을 생성·검증한다. 모델 미설치가 `jev-api` 개발을 차단하지 않는다.
- 각 LXC에서 해당 패키지 설치·import·lint·타입검사·패키지 빌드 및 최소 runner 시험을 수행한다. 비어 있는 시험 모음을 기능 PASS로 세지 않는다.
- E-01~02: 현재 파일 목록·소스 해시·전송 범위·동일 revision, 금지 경로 동기화 제외, 잘못된 호스트 거절과 로컬 fallback 부재를 확인한다. 프로필 오타·선택값 혼합·필수값 누락의 사전 거절과 dry-run의 무호출·비밀값 비노출을 확인한다.

설치·빌드·lint·타입검사·단위/mock 시험을 포함한 제품 실행은 위 LXC에서만 수행한다. 로컬은 코드/문서 작성과 읽기 검토만 한다. [증거 양식](../EVIDENCE_TEMPLATE.md)에 실제 revision·실행 서버·결과를 남긴다.

## 통과 기준

- [ ] 로컬 Python/모델/FFmpeg 실행 환경 없이 각 LXC의 runner로 검증할 수 있고, Jev API 키/연결 미설정이 추론 없는 도메인·구조화 시험을 막지 않는다.
- [ ] 최소 비root 계정·Python·시험 경로가 준비되고 전송 소스와 manifest가 일치한다. 비공개 파일·운영 데이터가 포함되거나 지워지지 않는다.
- [ ] 필수 시험의 실행 증거가 있으며 NOT_RUN/SKIPPED/실패를 PASS로 표시하지 않았다.

## 중단·후속 처리

경로·접속·설치 실패는 원격 실행 BLOCKED로 기록한다. 로컬 설치/시험으로 우회하지 않으며 정확한 명령은 실제 LXC 검증 뒤 확정한다. 상세 자원·운영 격리·ID·네트워크 준비는 03단계에서 이어서 검증한다.

통과 후 [버전 목차](README.md)와 [STATUS](../STATUS.md)를 갱신한다. 계획 문서 작성만으로 이 단계를 완료 처리하지 않는다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
