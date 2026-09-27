# 0.6.0 · 2단계 — 의도·행동 선택과 조기 종료

| 항목 | 내용 |
| --- | --- |
| 버전 / 단계 | 0.6.0 / 2 of 5 |
| 의존성 | 1단계 전처리·후보·snapshot, 0.5.0 API/예산 클라이언트 |
| 시험 호스트 | DiscordBotLXC orchestration; DiscordBotLXC의 중계 실제 1/2단계 |
| 상태 | IN_PROGRESS — 필수 인수 전 |

## 목표

[Jev API 실제 프로필](../INFERENCE_PROFILES.md)에서 의도·행동·대상이 명확해지는 즉시 판단을 끝낸다. `clarify`와 잘못된 응답을 추가 모델 질문으로 덮어쓰지 않고 공통 실행 전 검사 또는 사용자 UI로 이동한다.

## 로컬 코드 작업

- 검증한 구문·snapshot에서 가능한 의도만1단계 후보로 구성하고 non_command/clarify를 유지한다. 복합 변경·설명 질문은 추론 전 거절하고 임계값·margin·권한/확인 정책은 유지한다.

- 1단계 `classify_intent`에서 `play_request`, `playback_control`, `queue_edit`, `playlist_edit`, `playlist_generate`, `info_query`, `voice_control`, `song_proposal`, `non_command`, `clarify`를 계약으로 정의한다.
- 미구현 P1 의도는 미지원 안내로 처리하거나 실행 후보에서 제외한다. 정의된 의도와 실제 활성 기능을 구분한다.
- 1단계 결과를 검증한 뒤 실제 권한을 확인하고, 규칙으로 완성되는 행동/대상은 즉시 실행 전 검사로 보낸다.
- N-03 형태처럼 의도와 스냅샷 항목이 명확하면 공급자 dispatch 1회로 종료한다.
- `non_command`는 미실행, `clarify`·잘못된 응답·권한 거절·취소·만료는 후속 모델 없이 종료한다.
- 세부 행동이 불명확한 경우만 2단계 `select_action`을 호출한다. 가능한 모든 도구를 한꺼번에 나열하지 않는다.
- 실제 데이터에서 가능한 소수 후보와 `clarify`를 만들고 각 후보의 서버 보유 계획을 유지한다.
- 행동/대상이 완성되면 2회로 종료한다. 모델 점수 개선 목적의 3단계 재검수를 넣지 않는다.
- 행동만 확정되면 `unresolved_fields`가 있는 중간 후보로 유지하고 ActionPlan으로 승격하지 않는다.
- 2단계 `clarify`·잘못된 응답을 3단계 진입 근거로 쓰지 않는다. 정보 부족은 선택 메뉴/입력창으로 보낸다.
- API 1.2 요청은 동일 request ID·공통 만료·provider/profile_id/config_hash를 유지하고 task·stage·snapshot·candidate set을 검증한다. 실행 중 공급자 변경과 다른 프로필 fallback은 거절한다.
- `early_exit_enabled=true`, 자동 재시도 0, 단계당 질문/공급자 dispatch 1회를 유지한다. `usage.provider_calls`는 단계별 신규 dispatch(0 또는 1), `usage.request_provider_calls_total`은 요청 누계(3 이하), `usage.request_stages_total`은 단계 수로 관측한다.
- raw confidence로 공통 threshold를 가정하지 않는다. 개발 세트에서 보정한 provider별 prompt/threshold 버전을 선택 프로필/설정 해시에 묶는다.

## 산출물

- 1/2단계 라우터·의도 allowlist·행동 후보·중간 후보·조기 종료 상태 전이.
- clarify/non-command/미지원 기능의 한국어 안내와 선택 UI 연결.
- 1/2단계 경로·추가 판단 이유·권한 거절·조기 종료율 지표와 시험 코드.

## LXC 검증

- [B-04·B-05·B-06](../TEST_MATRIX.md)의 API 프로필/응답 검증·단계별/요청누계 호출 계측·자동 재시도 금지를 1/2단계 조기 종료 경로에서 회귀 검증한다.
- DiscordBotLXC에서 설치·빌드·lint·타입 검사·라우팅 mock 시험을 실행한다.
- DiscordBotLXC의 중계 게이트웨이에서 Jev API 실제 프로필을 순차 선택하여 N-21 1회 종료, N-22 2회 종료, N-24 clarify 즉시 UI를 같은 fixture/seed/snapshot으로 검증한다. 결과는 프로필/run별로 분리한다.
- N-01 등록 목록 재생, N-02 현재곡 추가, N-06 조회 부정문, N-07 감상 표현을 개발 데이터로 시험한다.
- N-13 독립 복합 작업은 분리 안내, 명세의 사전 정의된 목록 불러와 재생만 허용되는지 확인한다.
- 비DJ 요청 T-04/N-11에서 실제 역할 거절 후 후속 추론/실행이 발생하지 않는지 확인한다.
- hosted 모델 내부 실행 횟수로 해석하지 않는다.

## 통과 기준

- Jev API 실제 프로필의 N-21/22/24 통과, 명확한 1/2단계 요청의 불필요한 추가 dispatch 0건. 출력 선택·확률의 완전 일치는 요구하지 않는다.
- 미해결 계획·non-command·clarify·권한 거절 결과는 실행되지 않는다.
- 동일 request ID·deadline·프로필을 유지하며 hosted forward는 미확인으로 보고한다.

## 중단·후속 처리

명확한 요청을 항상 3회로 돌리거나 clarify 뒤 재추론하면 안전 회귀 실패로 처리한다. 후보/구문을 수정해 해당 LXC에서 재검증하고, 남은 대상에 실제 문맥 근거가 있을 때만 다음 단계 조건을 검토한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
