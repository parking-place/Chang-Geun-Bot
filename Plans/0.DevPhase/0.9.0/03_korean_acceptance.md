# 0.9.0 Phase 3 — 한국어 독립 평가

- 버전: `0.9.0`
- 단계: `3 / 5`
- 선행: [Phase 2](02_functional_security.md) 안전·권한·예산 회귀 통과.
- 검증 호스트: `DiscordBotLXC`의 별도 계정 중계·봇
- 상태: **PLANNED — 필수 인수 전**
- 추론 계약: [프로필 선택·시험 실행](../INFERENCE_PROFILES.md), [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md), 내부 API schema `1.2`.

## 목표

- 개발 중 조정한 문장과 다른 고정 평가 데이터로 실제 한국어 품질을 검증한다.
- 단계 추가의 이득과 안전성·확인 증가·지연 비용을 따로 측정한다.

## 로컬 코드 작업

- Jev API에서 같은 독립 최소 200문장(명확한 지원 120개·모호/비명령/부정 60개·우회/교란 20개)을 평가한다. hosted에 보낼 세트는 합성/익명화하고 최소 후보만 포함한다.
- 띄어쓰기·오타·존댓말·반말·수사·따옴표·짧은 곡명과 처음 보는 목록명을 섞는다.
- 의도·대상·확인 필요·최종 ActionPlan 정답과 채점 규칙·fixture/seed/초기 snapshot을 고정한다. Jev API 프롬프트/임계값·모델 선택은 개발 세트에서 정하고 held-out 평가 전에 manifest로 잠근다.
- 자동 해석 성공에서 불필요한 clarify를 제외하며 거절·실패·timeout을 별도 집계한다.
- Jev API의 1·2·3단계 정책을 같은 세트에서 비교하고 3단계는 허용 조건에서만 호출한다. 각 시험 run의 DB/큐·원장·증거를 분리하고 실제 명령 변경을 같은 DB/Discord에 중복 적용하지 않는다.

## 산출물

- 익명화된 평가 세트·정답·개발 세트 분리 기록과 데이터 버전.
- 프로필·모델·프롬프트·임계값·정책별 의도/대상/확인/ActionPlan 점수 및 오류 분석. Jev API/mock 점수를 합산하지 않고 결과별 source SHA·config_hash·run_id를 남긴다.
- 지원 구문·미지원 표현·확인 안내와 모델 교체 판단 기록.

## LXC 검증

- `DiscordBotLXC`: 고정 평가 세트의 요청 발생·후보·문맥·최대 3단계 오케스트레이션·ActionPlan 채점을 수행하고 실행 직전 권한·대상·확인을 시험한다.
- `DiscordBotLXC의 중계`: 선택한 프로필의 gateway가 실제 판단 API를 제공하고 provider_calls·원장·지연·자원을 계측한다. hosted는 반환 모델/API 버전·측정시각·고정 불가 한계를 기록한다. 모델 단독 평가와 전체 봇 해석 평가는 구분한다.
- DiscordBotLXC의 봇·중계: 실제 stage·질문/provider_calls 수·조기 종료·stage3_reason·기한·거절을 기록한다. hosted forward_passes와 request_forward_passes_total은 null, forward_passes_source=unavailable로 유지한다. 독립 held-out 전용 runner를 별도 구현·검증한 뒤 run별로 실행하고 전환 시 중지/drain·새 run/session을 사용한다.
- 현재 `scripts/test_profile.py --suite korean-eval`은 개발37문장 전용이다. 이 결과나 runner를 독립200문장 최종 인수로 사용하지 않는다.
- hosted 미달이면 계정에서 확인한 모델/어댑터·prompt/threshold 후보를 개발 세트로 조정한다. 어떤 경우도 자동 provider fallback이나 같은 평가 세트에 맞춘 최종 점수 개선으로 처리하지 않는다.
- 평가·설치·모델 실행·lint·빌드 등 실행 검증은 두 지정 LXC에서만 수행한다.

## 통과 기준

- Jev API의 필수 시험이 미실행·실패이면 해당 단계를 완료하지 않는다. mock·개발 소규모 시험으로 실제 품질·장시간 인수를 대체하지 않는다.
- 안전 회귀에서 무확인 부정·모호 삭제, 권한 우회, 취소 뒤 실행이 0건이다.
- 불필요한 후속 추론·clarify 후 재추론·숨은 번역/검수 호출이 0건이다.
- 단계 추가가 후보 밖 추측·권한·확인 우회를 만들지 않는다.

## 중단·후속 처리

- 평가 세트로 직접 프롬프트를 맞추면 새 독립 세트를 마련해 최종 평가를 반복한다.
- 품질·안전 미달은 모델·후보·지원 구문을 수정하고 새 후보로 관련 회귀를 재실행한다.
- 목표를 조용히 낮추지 않고 증거가 충족된 뒤 Phase 4 성능을 측정한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
