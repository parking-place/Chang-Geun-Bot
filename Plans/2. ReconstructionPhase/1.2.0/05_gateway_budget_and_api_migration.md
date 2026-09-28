# 05 — 신규 gateway 계약·영속 예산·기한·취소

- 상태: **PLANNED**
- 선행: [01 계약](01_baseline_and_contracts.md), [02 등록부](02_registry_and_command_service.md).
- 명세: 1.2·6.1·10·12.6·15.16. 시험: R120-10/11.

## 작업

1. `inference/contracts.py`, bot `nlp/client.py`, `domain/models.py`, `shared/schemas`의 API1.2·최대3회·stage=question=call 가정을 조사한다. 별도 `parser-api-v2`로 named questions/Choice/Noul/LLM operation과 사용량 envelope를 추가하고 옛 응답에 새 의미를 덧씌우지 않는다.
2. root 등록과 하위 전송을 분리한다. root owner/config/원문 binding/마감시간은 불변, pass·operation·stage·call·attempt는 하위 식별자다. ledger의 기존 `(request_id,stage)`와 단순 연속성 제약은 새 테이블/버전으로 이관하며 구버전은 그대로 검증한다.
3. gateway 하나의 durable RequestBudget에서 initial≤3, after_rewrite≤3, Jev합≤6, rewrite≤1, full_parse≤1, LLM합≤2, 전체≤8을 동시에 예약한다. 단계 질문5개를 원격5회로 계산하지 않는다. 질문 수/선택지 수/입력 byte 제한은 호출 횟수와 따로 둔다.
4. 원자 예약 이후 전송 여부를 `remote_attempted`로 남긴다. 로컬 preflight 실패는 원격0회이며 이미 예약한 슬롯은 보수적으로 소비 처리할 수 있다. 전송 뒤 timeout·응답유실·취소·재시작 불명은 예약/비용0으로 환불하거나 자동 재전송하지 않는다.
5. 원문 기준 하나의 취소 토큰과 절대 monotonic deadline을 두 패스·LLM 모두 공유한다. 전체35초/호출별5·5·10초는 초기값이며 실제 timeout은 잔여 시간의 최솟값이다. 큐 대기/조회도 전체 기한에 포함한다. 재시작한 in-flight 요청은 interrupted/unknown으로 닫고 시간/횟수를 새로 주지 않는다.
6. SDK·HTTP 자동 retry0, redirect0, 고정 HTTPS endpoint·TLS 검증·환경 proxy 미사용을 유지한다. Jev/OpenAI 키와 내부 토큰을 분리하고 봇 계정의 외부 키 읽기를 거부한다. gateway의 현재 worker1/활성dispatch1/대기4를 기본 보존하고 증설은 별도 성능 근거로만 변경한다.
7. 기존 epoch/run 예산·소유권 tombstone과 새 계약의 할당량 계보를 결합한다. cache hit/진행 합류는 신규0회이고 누계는 보존한다. operation/model/config/권한범위/candidate set을 cache key에 포함하고 부모7일 만료를 연장하지 않는다.
8. 새 GPT 평가에 유한 금액·토큰 한도, 가격표 버전, 응답 usage 불명 시 보수적 예약 정책을 추가한다. Jev 기존3000 한도는 자동 증액하지 않는다. provider별 원장과 root별 누계를 함께 제시하고 전송 전 최악 잔여 비용을 점검한다.
9. sanitized usage/attempt observer를10단계와 연결한다. API health는 모델0회로 유지하고 `LLM_FALLBACK=disabled` readiness와 nano 모델 실호출 여부를 혼동하지 않는다.

## 산출물

신규 wire/JSON Schema·호환 client·durable root/attempt ledger 이관·RequestBudget·취소/기한 포트·예산/토큰 정책·비밀 없는 설정 계약. 기존 배포 파일의 활성값 변경은12단계 전환까지 하지 않는다.

## 검증·종료 조건

- R120-10: LXC 기록형 대역으로3+1+3+1=8 예약,9번째/패스4번째/rewrite2번째/full_parse2번째 거부. 동시 예약·합류·cache·preflight·전송불명·재시작·동일 메시지에 대해 상한 우회0.
- R120-11: 35초 전체/잔여timeout·취소·주시 세대변경·늦은 응답에서 신규 전송/실행0. 구/신 API mismatch 거부와 구버전3회 계약 유지. 원장 장애 시 dispatch 금지, 관측 장애와 구분.
- source/wheel 버전이 다른 contract 실패를 성공으로 분류하지 않는다. 실제 paid API 검증은07·10의 관측/마스킹 준비 뒤11단계에서 별도 수행한다.
- 예산 fixture는 실제 외부8회 호출로 증명하지 않는다. 기록형 대역의 예약 증거와 실호출의 호환 증거를 구분한다.

[다음: Jev](06_jev_interpreter.md) · [아키텍처](ARCHITECTURE.md) · [목차](README.md)
