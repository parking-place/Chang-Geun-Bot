# 06 — Jev 다중 질문·인수 해석·두 패스

- 상태: **IN_PROGRESS — 두 패스/묶음질문·선택적3차와 Jev wire 개발시험 완료, 실제품질·복수선택 대기**
- 선행: [04 실제 목록·새 값](04_typed_candidates_and_resolution.md), [05 API/예산](05_gateway_budget_and_api_migration.md).
- 명세: 6절·7.1~7.2·12.5. 시험: R120-12/13.

## 작업

1. 같은 `JevInterpreter`가 `initial`과 `after_rewrite`를 처리하게 한다. 패스별 요청/응답·질문 지표를 분리하고 두 번째 패스에서 명령을 다시 선택한다. 첫 결과나 rewrite를 정답으로 고정하지 않는다.
2. 1차에는 input_kind(single/multiple/not_request/unclear)와 command를 묶는다. 실제 허용 명령 등록부 목록과 `__NONE__`을 전달한다. 명령이 선택돼도 multiple/not_request이면 실행하지 않고 상충된 조합은 해석 실패로 기록한다.
3. 2차에는 확정 명령의 필요한 인수 질문을 한 원격 요청에 묶는다. 재생목록/곡/채널은04단계의 실제 완전 목록과 opaque ID, 새 이름/검색어는 원문 구간을 전달한다. 질문 키만으로 의미를 대신하지 않고 각 instructions에 역할·source 종류·예약 상태를 명시한다. 같은 호출의 한 답을 다른 질문이 이미 안다고 가정하지 않는다.
4. 목록형 인수는 후보별 Noul 포함 여부로 구성하고 코드가 순서/제외/불확실을 처리한다. Noul의 `noul` 값과 Choice의 choice/probabilities/confidence를 구분한다. 필요한 슬롯 하나가 실패해도 평균 점수로 확정하지 않는다.
5. 3차는 목록 선택 후 해당 목록의 실제 entry 전체 조회 등 새 정보가 생긴 경우만 사용한다. 같은 원문/목록의 ‘정말 맞아?’ 재질문과 낮은 점수의 동일ID 합의는 새 경로에서 제거한다. 긴 새 값 누락은 원문 추출/LLM 경로로 연결하되, 실제 목록의 크기 초과는 범위 질문/UI로 보낸다. 모든 목록 페이지를 별도 Jev 호출로 보내지 않는다.
6. confidence0.85·margin0.15, Noul yes0.85/no0.15를 초기값으로 사용하고 실제 개발 자료로 보정한다. 점수를 실제 정확도 확률로 표시하지 않는다. rewrite 뒤 임계값을 자동 완화하지 않는다.
7. rewritten pass에는 원문·정규화문·재작성문 출처를 명시하고 후보 이름/문장을 신뢰하지 않는 데이터로 취급한다. 각 선택은 해당 root/pass/command/arg 집합 소속을 검사한다. 서로 다른 명령/대상은 INTERPRETATION_CONFLICT로 남긴다.
8. Jev 무응답·429/529·timeout·회로 차단과 명령 NO_MATCH/실제 누락을 분리한다. 인증/스키마 오류는 설정 오류로 기록한다. semantic fail과 service unavailable을08단계의 서로 다른 전이로 전달한다.
9. 기존 provider adapter의 확률만 남기는 변환을 바꿔 질문별 confidence/usage를 보존한다. 실제 미제공 revision/내부 forward는 null/unavailable로 유지한다. Choice/Noul·질문 상한은 구현 시 공식 Jev 계약과 LXC 실제 응답에서 확인한다.

## 산출물

공통 JevInterpreter·질문 생성기·Choice/Noul 응답 검증·패스별 초안/실패 enum·query-dependent3단계 fixture·실제 전송 envelope/사용량 연결.

## 검증·종료 조건

- R120-12: 단일/복합/비명령 분기, 실제 명령/객체 목록과 새 값 추출 분리, 독립 질문 묶음, 타입별 역할/예약상태·Noul 확률·부분 목록 차단. 전체 전달 항목과 snapshot ID가04의 결과와 일치하고 질문 N개=원격1회가 원장/로그에서 일치한다.
- R120-13: 신규 조회가 있을 때만3차, 두 패스별 후보/지표 분리, pass 혼용 거부, 재해석 명령 변경·실제 누락·가용성 오류의 다른 결과. 같은 질문 재시도로 품질을 보정하지 않는다.
- 초기 시험은 LXC mock·고정DB만 사용한다. 실제 Jev 품질/성능은11단계에서 모델·질문·후보·threshold manifest와 함께 판정한다.
- 초안이 만들어진 것과 실행 가능한 것이 다르다. 어떤 패스 결과도09단계의 공통 검증을 우회하지 않는다.

[다음: LLM](07_llm_provider_profiles.md) · [시험표](TEST_MATRIX.md) · [목차](README.md)
