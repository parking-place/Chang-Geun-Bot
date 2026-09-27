# 0.0.0 / 04 — 음성·재생 소스·Jev API 추론 경로 초기 타당성

| 항목 | 내용 |
| --- | --- |
| 버전·단계 | 0.0.0 / 4단계 |
| 상태 | IN_PROGRESS — 필수 인수 전 |
| 선행 조건 | [03단계](03_lxc_readiness_and_isolation.md) VERIFIED |
| 검증 호스트 | DiscordBotLXC: 음성/소스, DiscordBotLXC의 중계: 공통 게이트웨이와 선택 공급자 |
| 명세 기준 | [개발 명세 1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) |

## 목표

핵심 기술의 불가능/미검증 위험을 전체 구현 전에 발견하고 후속 정식 검증 경로를 선택한다.

## 추론 프로필 적용

[Jev API 전용 계약](../INFERENCE_PROFILES.md)을 따른다. 실제 자연어 판단은 `jev-api`만 사용하며 봇과 TLS 중계·영속 원장은 DiscordBotLXC에서 별도 계정으로 실행한다. 현재 배치는 [환경 계약](../ENVIRONMENT.md)을 따른다. `mock`은 지정 LXC의 격리 회귀 전용이다. 구조화 명령은 추론 없이 실행하고, API 장애가 기존 재생·슬래시·버튼을 막지 않게 한다.

## 로컬 코드 작업

- DAVE/음성 의존성·Gateway/interaction·YouTube 메타데이터/재생 정책·hosted Jev API와 OpenJev 원본 API를 구현 시 공식 자료로 다시 확인할 체크리스트와 결정 양식을 작성한다. hosted의 실제 wire schema·모델 식별·오류·내부 forward 공개 여부는 검증 전 추정하지 않는다.
- 소스의 플랫폼 정책·콘텐츠 전송 권리·실제 기술 검증을 별도 항목으로 분리한다. youtube_audio_enabled=false가 출발값이다.
- 승인된 시험 음원과 실제 Discord 테스트 채널을 사용하는 최소 음성 probe 및 `jev-api` 선택형 질문 probe를 작성한다.
- hosted probe도 단계당 한 질문·한 dispatch로 제한하며 SDK/HTTP 자동 재시도와 다른 공급자 fallback을 끈다. 응답 유실·timeout 뒤 실제 실행 여부가 불명하면 재전송하지 않고 관측 한계를 남긴다.
- `jev-api`는 모델 런타임을 로드하지 않고 hosted 모델 식별·요청/질문/provider_calls 수·왕복 지연·실패를 계측한다. 내부 forward는 `null`/`unavailable`로 남긴다.
- 최종 평가와 겹치지 않는 한국어 탐색 문장(예: 30개)을 준비하여 명령·부정문·모호함을 비교한다. 같은 source/fixture/snapshot/seed를 Jev API 프로필에 사용하되 독립 run_id와 별도 품질·성능 결과를 남긴다. 소규모 성공으로 95% 출시 품질을 보장하지 않는다.
- hosted 탐색은 합성/익명 fixture와 최소 후보 설명만 보내며 실제 Discord 식별자·전체 대화·DB·내부 토큰을 전송하지 않는다. 준비 호출을 포함한 run 전체 호출 한도와 예상량을 먼저 고정하고 초과 시 시작하지 않는다. 가격·사용량·제공자 데이터 보존정책은 확인 출처와 미제공 항목을 구분한다.

## 산출물

- 직접 YouTube/승인된 별도 음원/메타데이터의 지원 상태표와 모델·오디오 경로의 차단 목록.

## LXC 검증

- E-05: DiscordBotLXC에서 테스트 guild 입장·승인 음원 전송·퇴장 및 UDP 왕복/DAVE 의존성을 탐색한다. 정식 어댑터 인수는 0.3.0에서 반복한다.
- E-06: DiscordBotLXC의 중계 공통 게이트웨이에서 선택 프로필의 선택형 질문·한국어 탐색·판단/질문/provider_calls 상한을 확인한다. hosted는 TLS/인증·응답 검증·네트워크 실패·관측 가능한 호출수와 forward 미제공을 별도로 기록한다. API/예산 원장 정식 검증은 0.5.0이다.
- 명세 자원 수치나 외부 README 설명을 이 환경의 실측값으로 사용하지 않는다.

설치·빌드·lint·타입검사·단위/mock 시험을 포함한 제품 실행은 위 LXC에서만 수행한다. 로컬은 코드/문서 작성과 읽기 검토만 한다. [증거 양식](../EVIDENCE_TEMPLATE.md)에 실제 revision·실행 서버·결과를 남긴다.

## 통과 기준

- [ ] 세 핵심 위험마다 관측 증거·진행 경로·미검증 부분·다음 정식 게이트가 명확하다.
- [ ] Jev API 경로에서 판단·질문·요청별 provider 호출 누계가 각각 최대 3회인 후보 계약이 있다. hosted 내부 forward를 검증한 것으로 표시하지 않는다.
- Jev API의 필수 시험이 미실행·실패이면 해당 단계를 완료하지 않는다. mock·개발 소규모 시험으로 실제 품질·장시간 인수를 대체하지 않는다.
- [ ] 필수 시험의 실행 증거가 있으며 NOT_RUN/SKIPPED/실패를 PASS로 표시하지 않았다.

## 중단·후속 처리

YouTube 직접 소스는 승인된 1.0.0 범위에서 제외하고 비활성으로 유지한다. 승인 음원 소스와 메타데이터의 필수 인수가 미완료면 1.0.0은 차단한다. 한국어 후보가 부적합한 경우 대체 평가 계획 없이 자연어 완성으로 넘기지 않는다.

통과 후 [버전 목차](README.md)와 [STATUS](../STATUS.md)를 갱신한다. 계획 문서 작성만으로 이 단계를 완료 처리하지 않는다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
