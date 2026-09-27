# 0.0.0 / 03 — 기존 LXC 준비와 시험 격리

| 항목 | 내용 |
| --- | --- |
| 버전·단계 | 0.0.0 / 3단계 |
| 상태 | IN_PROGRESS — 필수 인수 전 |
| 선행 조건 | [02단계](02_repository_and_remote_workflow.md) VERIFIED — 최소 계정·경로·runner 준비 |
| 검증 호스트 | DiscordBotLXC + DiscordBotLXC의 중계 |
| 명세 기준 | [개발 명세 1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) |

## 목표

02단계에서 최소 실행 기반을 마련한 기존 LXC를 재사용하고 상세 자원·권한·네트워크·시험 데이터 격리를 확인한다.

## 추론 프로필 적용

[Jev API 전용 계약](../INFERENCE_PROFILES.md)을 따른다. 실제 자연어 판단은 `jev-api`만 사용하며 봇과 TLS 중계·영속 원장은 DiscordBotLXC에서 별도 계정으로 실행한다. 현재 배치는 [환경 계약](../ENVIRONMENT.md)을 따른다. `mock`은 지정 LXC의 격리 회귀 전용이다. 구조화 명령은 추론 없이 실행하고, API 장애가 기존 재생·슬래시·버튼을 막지 않게 한다.

## 로컬 코드 작업

- 실제 확인 항목을 작성한다: OS/Python·CPU/RAM/disk·UTC 시간/DNS·호스트 공유 부하·서비스 계정·방화벽/UDP·설치된 서비스.
- 기록된 OpenJev 8 vCPU/10GB/32GB, 봇 2 vCPU/2GB/20GB와 명세 기본안의 차이를 명시한다. privileged를 nonprivileged라고 쓰지 않는다.
- 비root 앱 계정·프로필과 run_id별 분리된 시험 venv/DB/게이트웨이 원장/환경 파일/서비스 이름·증거 경로와 최소 쓰기 권한 구성을 작성한다. 운영 데이터와 다른 프로필의 원장을 재사용하지 않는다.
- 테스트 bot/guild/DJ/일반 회원/텍스트/음성채널과 운영 설정을 분리하는 placeholder·입력 검증을 작성한다.
- Jev API 프로필 공통 내부 API의 DNS·TLS 신뢰·`JEV_API_TOKEN` 인증·봇 출발지만 허용하는 방화벽 요구를 작성한다. 실제 주소·키는 제한된 비공개 입력으로 관리한다.
- `jev-api`는 게이트웨이의 허용된 hosted endpoint·TLS·모델 식별자와 `JEV_HOSTED_API_KEY`를 별도 검증한다. hosted 키는 DiscordBotLXC의 중계 게이트웨이의 제한된 환경 파일에만 주입하며 봇·일반 Plans·로그·manifest에는 포함하지 않는다. 키를 내부 `JEV_API_TOKEN`으로 재사용하지 않는다.
- 선택하지 않은 프로필의 키/가중치 누락은 해당 프로필의 미설정 상태로만 기록한다.

## 산출물

- 실측 환경 체크리스트, privileged 차이의 결정 기록, 시험/운영 데이터와 자격증명 분리표.
- 비밀값을 제외한 환경 manifest와 미발급 ID/토큰/DNS/CA/백업 입력 목록.
- 실제 API 구현 전 임시 전송/TLS/인증 probe의 범위·실행·정리 기록.

## LXC 검증

- E-03~04: DiscordBotLXC의 봇·중계의 자원·시간·런타임·경로·비root 권한을 확인한다. 호스트 정보는 기존 관리 경로의 읽기 자료로 확인하며 호스트에서 제품 시험을 실행하지 않는다.
- DiscordBotLXC에서 DiscordBotLXC의 중계로 허용된 내부 통신·TLS 신뢰·공유 토큰 검증을 임시 전송/인증 probe로 시험한다. 공유 토큰 없는 접근과 다른 출발지 요청의 거절을 확인하고 시험 종료 후 임시 listener를 정리한다.
- `jev-api` 선택 시 게이트웨이에서 허용된 hosted endpoint의 TLS/인증 경로를 별도 probe하고 비밀값을 출력하지 않는다.
- 이 probe는 아직 존재하지 않는 /v1/decide 서비스의 인증 인수를 뜻하지 않는다. 정식 인증 API·live/ready·오류 계약은 0.5.0에서 검증한다.
- 격리 fixture로 운영 DB/서비스와 경로가 겹치지 않는지 확인한다. 불필요한 root 권한·소스/설정의 비밀값 노출을 제거한다.

설치·빌드·lint·타입검사·단위/mock 시험을 포함한 제품 실행은 위 LXC에서만 수행한다. 로컬은 코드/문서 작성과 읽기 검토만 한다. [증거 양식](../EVIDENCE_TEMPLATE.md)에 실제 revision·실행 서버·결과를 남긴다.

## 통과 기준

- [ ] 필수 실행 경로·계정·테스트 ID 입력이 마련되어 후속 LXC 시험이 가능하다.
- [ ] 실제 OS/자원과 privileged 잔여 위험이 기록되고 운영 데이터에 영향 없는 시험 경로가 확인된다.
- [ ] 임시 probe와 정식 API 인수가 구분되며 필수 시험 증거가 있다. NOT_RUN/SKIPPED/실패를 PASS로 표시하지 않았다.

## 중단·후속 처리

공통 환경이나 테스트 토큰/ID가 없으면 해당 외부 연동은 BLOCKED다. 도메인 초안은 진행할 수 있지만 실제 Discord/API 연동 PASS를 주장하지 않는다.

통과 후 [버전 목차](README.md)와 [STATUS](../STATUS.md)를 갱신한다. 계획 문서 작성만으로 이 단계를 완료 처리하지 않는다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
