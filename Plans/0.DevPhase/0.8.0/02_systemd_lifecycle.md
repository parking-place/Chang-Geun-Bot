# 0.8.0 Phase 2 — systemd와 프로세스 수명

- 버전: `0.8.0`
- 단계: `2 / 5`
- 선행: [Phase 1](01_failure_cancellation.md) 장애·취소 검증 통과.
- 검증 호스트: `DiscordBotLXC`의 봇·별도 계정 중계
- 상태: **IN_PROGRESS — 필수 인수 전**
- 추론 계약: [프로필 선택·시험 실행](../INFERENCE_PROFILES.md), [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md), 내부 API schema `1.2`.

## 목표

- 두 앱을 비root 계정과 제한된 쓰기 경로로 안정적으로 실행한다.
- 기존 privileged LXC를 보존하며 앱의 최소 권한과 정상 종료를 검증한다.

## 로컬 코드 작업

- 실제 패키지 진입점이 정해진 뒤 두 서비스 unit·run별 환경/데이터/증거 경로를 작성한다. 봇은 `DiscordBotLXC`, Jev API 경로의 gateway·영속 원장은 `DiscordBotLXC의 중계`에 둔다.
- `changgeun-bot.service`, `changgeun-jev.service`에 재시작 간격·횟수·종료 시간을 설정한다.
- 공통 gateway worker 1개·dispatch 동시 1개를 유지한다. health 조회가 유료 추론을 반복 호출하지 않게 한다.
- 봇 시작을 Jev readiness에 강하게 묶지 않고 live와 ready의 의미를 분리한다.
- 봇 종료 시 신규 요청 차단·오디오 자식 정리·현재곡 상태 보존, gateway 종료 시 대기 실패·진행 중 drain/불명 tombstone 처리를 구현한다. 시작 시 봇과 gateway의 provider/profile_id/config_hash 일치 여부를 검사하고 요청 수명 동안 고정한다.

## 산출물

- 실제 실행 경로를 사용한 systemd unit과 비밀값 없는 프로필 환경 예시, 전용 계정·권한 목록. hosted의 `JEV_HOSTED_API_KEY`는 gateway 전용으로 두고 내부 인증 `JEV_API_TOKEN`과 분리한다.
- 읽기·쓰기 가능 디렉터리와 TLS 프록시·루프백 API의 배치 문서.
- privileged 환경 차이와 비특권 환경 이관의 별도 검토 항목.

## LXC 검증

- `DiscordBotLXC`: 비root 기동·정상 종료·강제 종료·재시작에서 자식 프로세스 누수를 확인한다.
- `DiscordBotLXC의 중계`: Jev API에서 worker·dispatch 수와 재시작 제한을 확인한다. hosted는 로컬 모델/torch 미설치 기동·무과금 health·키 접근 제한을 확인한다.
- DiscordBotLXC의 봇·중계: Jev 미기동 상태로 봇이 기본 기능을 제공하며 환경 파일 접근이 제한되는지 확인한다.
- 허용 쓰기 경로 외 접근을 시험하고 실제 디스크·메모리 제한을 기록한다.
- 설치·unit 실행·lint·빌드·시험은 해당 LXC에서만 수행한다.

## 통과 기준

- 관리용 root 접속과 앱 서비스 실행 권한이 분리된다.
- 시작 시 최신 브랜치 자동 다운로드와 `pip install -U`를 수행하지 않는다.
- 정지 후 음성·오디오·추론 프로세스가 정의한 종료 정책대로 정리된다.
- 제한된 재시작과 독립 기동이 run별 서비스 상태로 증명된다. 운영은 지정한 프로필 하나만 활성화하며, 변경 시 중지/drain·프로필 명시·재시작·불일치 거절·rollback을 거친다. hot switch는 제공하지 않는다.

## 중단·후속 처리

- LXC 재생성·privilege 변경이 필요하면 별도 영향·복구 계획과 구체적 작업 승인을 준비한다.
- 기존 LXC 설정을 임의 변경하지 않고 증거를 남긴 뒤 Phase 3으로 진행한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
