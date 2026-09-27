# 0.5.0 · 2단계 — Jev API 어댑터와 계측

| 항목 | 내용 |
| --- | --- |
| 버전 / 단계 | 0.5.0 / 2 of 5 |
| 의존성 | 1단계 API 1.2/프로필 계약; 0.0.0 Jev API 공급자 타당성 조사 |
| 시험 호스트 | DiscordBotLXC의 중계; 자연어 장애 격리는 DiscordBotLXC |
| 상태 | IN_PROGRESS — 필수 인수 전 |

## 목표

공통 게이트웨이 뒤에 `jev-api`를 구현하고, 동일 후보 선택 계약과 단계당 공급자 dispatch 1회를 검증한다.

## 로컬 코드 작업

- hosted용 HTTP 의존성은 별도 묶음으로 두어 `torch`/모델 다운로드·로드를 요구하지 않는다.
- 공통 API worker 1개·동시 dispatch 1개를 기준으로 시작한다.
- 원본 라이브러리/서버 차이는 내부 어댑터에 가두고 봇에는 [API 1.2](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md)만 제공한다. 봇이 hosted endpoint를 직접 호출하지 않는다.
- Jev API 실제 프로필에서 질문 1개·등록 후보의 제한된 선택을 유지한다. 자유 JSON 생성·긴 사고 과정·도구 호출·다른 외부 LLM fallback을 연결하지 않는다.
- hosted 어댑터는 허용된 HTTPS endpoint로 단일 전송하며 인증서 검증을 유지하고 다른 호스트 redirect를 거절한다. upstream `remote.py`의 429/5xx/네트워크 자동 3-attempt 재시도와 `forward=len(questions)` 누계는 이 계약에 맞지 않으므로 그대로 사용하지 않는다. timeout·전송 성공 여부 불명 상태에서도 자동 재전송하지 않는다.
- 게이트웨이의 실제 공급자 진입 지점에서 단계별 신규 dispatch `usage.provider_calls`(0 또는 1)를 계측하고 단계 수와 별도 집계한다.
- 요청 누계 `usage.request_provider_calls_total`(3 이하), `usage.request_stages_total`, queue/dispatch 시간과 확인 가능한 token 수를 래퍼에서 생성한다. 캐시/합류의 신규 dispatch는 0회이며 누계는 유지한다. hosted 내부 inference 시간/token 수가 제공되지 않으면 외부 왕복 시간과 구분해 미확인으로 둔다.
- hosted는 두 값 `null`, `forward_passes_source=unavailable`이며 공급자 호출 수를 forward로 표시하지 않는다.
- 선택된 ID·확률·margin·`provider`/`profile_id`/`config_hash`·prompt version을 기록한다.
- 원본 confidence는 참고 필드이며 자동 실행 승인이나 정확도 백분율로 표시하지 않는다.
- hosted ready에는 자격증명 참조·고정 endpoint·지원 계약·single-send 설정을 검사하고 초기 실연결 검증 증거를 요구한다. 매 ready probe가 유료 추론을 일으키지 않게 한다.
- 예열/오프라인 검증은 운영 요청 처리와 분리한다. 요청 중 숨은 예열·번역·검수 호출을 넣지 않는다.
- 어느 실패에도 다른 제공자로 전환하지 않는다.
- `JEV_HOSTED_API_KEY`는 게이트웨이의 별도 접근 제한 파일에서 hosted 어댑터에만 전달하고 `JEV_API_TOKEN`과 분리한다.

## 산출물

- Jev API 공급자 어댑터·의존성 잠금·run별 readiness 검사 목록과 upstream 차단 지점.

## LXC 검증

- [B-03·B-04·B-05·B-06·B-11](../TEST_MATRIX.md)의 의존성 분리·정규화·호출/forward 계측·single-send·전송/한도 통제를 어댑터 인수에 포함한다.
- DiscordBotLXC의 중계에서 run별 의존성 설치·빌드·lint·타입 검사·격리 mock/실제 공급자 시험을 실행한다. hosted-only 환경은 `torch`/모델 없이 검증한다.
- 어댑터 내부 검수/배치로 질문을 숨기는 N-36을 검사한다.
- 선택지 밖 ID·NaN·확률 합 오류 N-16과 API 미기동/지연 N-17을 실제/주입 시험으로 구분한다.
- hosted는 외부 왕복 지연·오류·지원 계약을 별도 기록한다.
- hosted 429/5xx/네트워크 장애 주입에서 단일 전송만 발생하는지 검사한다.
- 같은 fixture/seed/snapshot의 Jev API 실제 프로필 결과를 따로 저장하고 출력 동일성을 통과 조건으로 삼지 않는다.
- DiscordBotLXC에서 ready 실패 중 기존 재생·슬래시·버튼이 유지되는지 확인한다.

## 통과 기준

- worker1·활성dispatch1·대기4, 무모델 의존성·single-send·automatic retries/fallback0·forward null/unavailable 검증.

- hosted forward는 미확인으로 유지하고 `usage`를 모델이 생성하지 않는다.
- 프로필·설정·확인 가능한 모델/OpenJev/API·프롬프트 버전이 증거와 응답에 일치하고 run별 준비 실패가 ready에 반영된다.

## 중단·후속 처리

최종 한국어 품질은 Jev API 실제 프로필의 0.6.0 개발 평가와 0.9.0 held-out 평가에서 별도로 판단한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
