# 01 — 기준선·아키텍처·이관 계약 잠금

- 상태: **IN_PROGRESS — p1 계약 구현·LXC3시험, 전수대응은p2에서 검증**
- 선행: 없음. [원본 명세](../changgeun_jev_llm_fallback_command_parser_spec_v1.3.md) 전체와 [아키텍처](ARCHITECTURE.md)를 입력으로 사용한다.
- 책임: R120-01~03. 이후 단계의 구현·시험 분모와 호환 경계를 먼저 확정한다.

## 작업

1. 구현 착수 시 Git SHA·dirty/worktree·제품 버전, 실제 봇/중계 wheel·source manifest·설정·DB schema·고정 epoch/profile·잔여 예산을 확인한다. 기록상 patch117b/patch116g와 미적용 patch118a를 구분하고 현재 LXC 관측값을 별도 남긴다. 새 확인을 위해 기존 데이터를 덮어쓰지 않는다.
2. C01~C47·공개 옵션·I01~I08, 도메인41 Action과 실제 서비스/화면을 대조한다. C39 진입점과 내부 비공개 Action을 구분한다. 기존 미완료가 사라지지 않도록 [STATUS](STATUS.md)의 이관표를 명령/시험 ID에 연결한다.
3. 원본 설계서의 예시와 제품 기능을 구분한다. 명세의 가상 명령·값 범위를 그대로 새 공개 기능으로 추가하지 않고 등록된 기능에 매핑한다. 복합 작업 차단과 기존 단일 기능 내부의 여러 서비스 동작을 구분한다.
4. `parser-api-v2`의 요청/응답·오류·취소·버전 협상 계약을 작성한다. root request, pass, operation, stage, question, attempt, call의 정의와 값 범위를 고정한다. API1.2와 새 계약의 동시 지원/거절 조합을 정한다.
5. root binding은 원문·호출자/서버의 불투명 범위·설정/프로필·기한에 고정하고 normalized/rewrite 입력은 하위 variant로 둔다. candidate set은 root+pass+command+argument에 귀속한다. 재해석에서 원문 binding을 덮어쓰거나 새 root로 예산을 재시작하지 않는다.
6. `CommandDraft`·`ValidatedCommand`·`ParserOutcome`·`RequestBudget`·`TraceRecorder`·`LLMFallback` 포트를 정의한다. 모델 제공자와 실행기·업무 저장소의 의존성을 분리하고, trace는 비필수 관측 저장소, budget/idempotency는 필수 영속 저장소로 구분한다.
7. 새 trace DB와 기존 업무 `command_requests`의 이름 충돌을 분리한다. 실제 trace v1 존재 여부를 조사하고 이관 가능한 자료만 이관한다. source/DB 원본·기존 tombstone·누적 예산은 보존한다.
8. 모델/설정/명령/프롬프트/스키마/정규화 버전과 산출물 SHA를 함께 고정할 manifest 형식을 정의한다. 모델 호출 상한과 금액 한도는 다른 축으로 기록한다. 35초 등 시작값의 실험 계획과 변경 절차를 명시한다.

## 산출물

- 현재/목표 계약 차이표와 C-ID→내부 명령 ID→서비스→화면 대응표.
- 신규 wire schema 초안·포트/오류 enum·버전 호환표·이관 및 복귀 순서.
- 업무DB/원장/trace/cache/확인 문맥의 소유자·보관기간·삭제 대상 목록.
- [REQUIREMENTS](REQUIREMENTS.md)와 [TEST_MATRIX](TEST_MATRIX.md)의 책임/선행 연결, 예산 계획과 후보 manifest 양식.

## 검증·종료 조건

- R120-01: 사용자 원본 명세와 요구사항 배정이 누락 없이 대응하고 기존 미완료/FAIL/SKIPPED가 보존돼야 한다.
- R120-02: API1.2와 새 계약의 구분·version reject·필드 상호 제약 시험을 설계하고, LXC에서 계약 fixture를 검증한다. 문서/원본 해시 비교 자체는 로컬 파일 검사로 할 수 있다.
- R120-03: 원장·업무DB·trace 삭제 범위가 겹치지 않고 기존 config/예산을 자동 변경하지 않는 이행안을 검토한다.
- 다음 단계 착수에는 계약 검토 기록이 필요하다. 문서 검토 완료와 이후 LXC fixture 결과를 분리하며, 문서를 만들었다는 이유로 단계 전체를 VERIFIED로 바꾸지 않는다.

[다음: 등록부](02_registry_and_command_service.md) · [목차](README.md)
