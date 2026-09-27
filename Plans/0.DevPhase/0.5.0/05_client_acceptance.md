# 0.5.0 · 5단계 — 봇 클라이언트와 API 안전 인수

| 항목 | 내용 |
| --- | --- |
| 버전 / 단계 | 0.5.0 / 5 of 5 |
| 의존성 | 1–4단계 API·어댑터·원장·기한 검증 |
| 시험 호스트 | DiscordBotLXC 클라이언트/재생; DiscordBotLXC의 중계 실제 API |
| 상태 | PLANNED — 필수 인수 전 |

## 목표

봇이 API 1.2의 검증된 후보 결과만 소비하고, 명시 선택한 `jev-api`의 장애가 기존 명령·재생 기능에 영향을 주지 않는 상태로 0.6.0에 전달한다. 시험 선택/전환은 [추론 프로필](../INFERENCE_PROFILES.md)을 따른다.

## 로컬 코드 작업

- 봇 API 클라이언트에서 공유 인증·TLS 인증서 검증·등록 프롬프트·공통 request ID를 적용한다.
- 시작 시 봇에 고정한 provider/profile_id/config_hash와 게이트웨이 readiness/API 버전을 확인한다. 불일치는 자연어만 잠그며 요청·응답·후속 단계에서 동일 프로필을 유지한다.
- 기본 자동 HTTP 재시도와 모델 재시도를 끈다. 불가피한 동일 전송은 원장의 기존 실행/결과 재사용 계약만 이용한다.
- 봇→게이트웨이 동일 요청 조회/합류는 공급자 재전송이 아니다. hosted timeout/전송불명 상태는 같은 키·새 ID·다른 프로필 어느 경로로도 다시 호출하지 않는다.
- 응답의 schema/request/stage/task/snapshot/candidate set·provider/profile_id/config_hash·확률·usage·확인 가능한 revision을 원 요청과 검사한다.
- hosted 두 forward 필드 `null`/source=`unavailable`, 미공개 model revision `null`/`model_revision_source=unavailable`를 허용하며 누락된 공통 호출 누계는 거절한다.
- 후보 밖 ID·NaN·깨진 응답·예산 초과 usage는 미실행으로 실패시킨다. 다른 후보로 자동 보정하지 않는다.
- 400/422·401/403·409·429·503·504를 한국어 안내와 기계 판독 오류에 매핑한다.
- 음악봇 전체 health를 Jev ready와 묶지 않는다.
- 반환된 후보는 봇이 이미 보유한 계획으로 조회하고 미해결 필드가 있는 계획을 실행기로 넘기지 않는다.
- 봇 공통 실행기의 실제 actor·권한·대상 버전·generation·확인 정책 검사를 유지한다.
- hosted 내부 inference 시간과 외부 왕복 시간은 구분한다.
- 원문 로깅 off·외부 LLM fallback off를 유지하고 비밀값·raw prompt를 오류/지표에 노출하지 않는다.
- 0.5.0 계약 시험과 0.6.0 전체 NL 시험의 책임을 구분한다. 이 단계는 자연어 품질 완료를 선언하지 않는다.
- 구현한 `scripts/test_profile.py`의 `jev-api` 전용 activate/status/transport와 명시 mock contract의 선택·격리·dry-run·전환 절차를 인수한다. 단일 선택으로 DiscordBotLXC의 봇·중계의 테스트 설정/의존성/DB/원장/증거를 결합하고 설정·후보 변경 후 이전 세션/확인 토큰을 폐기한다.

## 산출물

- API 클라이언트·응답 검증·오류 안내·readiness 격리·관측 코드 및 시험 코드.
- N-16/17/18/26/27/28/29/33/35/36 계약 시험과 공통 프로필 선택/키 격리/전환/계측 시험 결과.

## LXC 검증

- [B-01–11](../TEST_MATRIX.md)의 0.5.0 책임 범위를 단계 1–4 증거와 실제 봇 연동으로 인수한다. 특히 B-01 선택·B-04 응답 일치·B-06 재전송 차단·B-08 전환·B-09 격리·B-10 장애 중 재생 유지·B-11 전송/한도를 클라이언트 관점에서 확인한다. B-08 복원/롤백과 B-12 품질 평가는 후속 버전의 별도 증거다.
- DiscordBotLXC에서 클라이언트 설치·빌드·lint·타입 검사·단위/mock 시험을 수행한다.
- DiscordBotLXC의 중계와 DiscordBotLXC 사이에서 같은 fixture/seed/snapshot의 Jev API 실제 프로필 인증·TLS·ready·정상/오류 응답을 독립 검증한다. 선택 결과의 동일성을 요구하지 않는다.
- mock·오류 주입·실제 공급자 증거를 따로 보고한다.
- 활성 요청 중 프로필 변경 거절과 정지·drain·tombstone·새 run/세션의 전환을 검증한다. 잘못된 프로필/설정 해시가 일치하는 것으로 처리되지 않아야 한다.

## 통과 기준

- 공급자 장애 중 기존 재생·슬래시·버튼 유지, 실패·취소 뒤 실행·자동 재시도·fallback 0건.
- 증거에 DiscordBotLXC의 봇·중계 코드 SHA·프로필/설정 해시·확인 가능한 모델/API/프롬프트 버전·실제 호출 누계와 미확인 항목이 기록된다.

## 중단·후속 처리

Jev API의 필수 시험이 미실행·실패이면 해당 단계를 완료하지 않는다. mock·개발 소규모 시험으로 실제 품질·장시간 인수를 대체하지 않는다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
