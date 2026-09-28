# 10. 구조화 로그와 최초 수신 기준 7일 보관

상태: **PLANNED**. 아래 구현·마이그레이션·검증은 후속 작업이며 현재 적용된 로거를 뜻하지 않는다.

[버전 개요](README.md) · [아키텍처](ARCHITECTURE.md) · [시험 추적](TEST_MATRIX.md) · [실행 상태](STATUS.md)

## 목적과 선행 조건

- [재구성 명세](../changgeun_jev_llm_fallback_command_parser_spec_v1.3.md) §15 전체의 원문·정규화·두 Jev 패스·rewrite·full_parse·검증·실행 이력을 연결한다.
- 선행 구현은 01 기준선·계약, 05 durable 예산, 08 오케스트레이션, 09 검증·확인·Discord 포트다.09의 실제Discord 인수 완료를10 구현 착수 조건으로 삼지 않는다.
- trace 스키마와 관측 포트는 01/05부터 정의하고 각 구현에 연결한다. 07/08의 초기 시험은 LXC 테스트 대역으로 수행한다.
- **유료 실호출 전** 최소 마스킹·호출별 usage 관측·중복 합산 방지와 05의 지출 한도 검증을 통과해야 한다.

## 저장소 경계와 스키마

1. 업무 DB와 분리한 로컬 SQLite `command-traces-v2.sqlite3`를 사용한다. WAL DB를 NFS/SMB 공유 경로에 두지 않는다.
2. 기존 업무 DB의 `command_requests`는 실행 결과·멱등성 테이블이다. 이름이 같은 신규 trace 테이블을 기존 DB에 만들거나 기존 테이블에 7일 purge를 적용하지 않는다.
3. 기존 `message_requests`, `external_effects`, gateway `run_budget`·request ownership/tombstone은 별도 수명·복구 정책을 유지한다.
4. trace는 `command_requests` 요약, `model_calls` 예약/시도, `trace_events` 관측 이벤트로 분리하고 자식은 부모 삭제 시 cascade한다.
5. `attempt_no`는 1~8, `(request_id, attempt_no)`는 unique다. LLM `(request_id, operation)` 부분 unique와 공통 Budget으로 두 작업 각각 1회만 허용한다.
6. Jev는 `pass_id=initial/after_rewrite`, stage 1~3을 보존한다. LLM은 pass/stage null, `operation=rewrite/full_parse`로 구분한다.
7. JSON 구조·상태 enum·유한 confidence·bool/int·usage 일관성·후보의 패스 소속은 앱에서 검증한다. TEXT 컬럼이 JSON 검증을 대신하지 않는다.
8. `trace_events.call_id`의 동일 요청 소속을 검증한다. 중복 이벤트를 새 API 호출로 만들거나 종료된/삭제된 부모를 upsert로 되살리지 않는다.

## 수집과 처리 결과

- `ModelCallObserver → TraceRecorder → TraceStore`를 분리한다. 공급자 어댑터에는 SQL·보관 기간 대신 공통 관측 계약만 제공한다.
- 자연어 진입점을 통과한 요청을 초기 100% 수집한다. 일반 채팅·전체 멤버 정보·이전 대화 전문을 수집하지 않는다.
- 최초/재해석의 선택·confidence·확률·margin·실패 원인을 따로 남긴다. 실제 목록은scope/snapshot revision/전체·전달개수/완전성, 새 값은원문 구간 포함률을 분리하고 전체목록을 불필요하게 로그에 복제하지 않는다. 후속 성공으로 최초 실패를 덮어쓰지 않는다.
- rewrite 제안문과 accepted/rejected/unchanged/terminal 판정을 분리하고 생략은 `stage.skipped` 이벤트로 기록한다. 미호출 모델 행은 만들지 않는다.
- `resolved_command`는 검증 계획, `executed_command`는 실제 서비스 전달 시점에만 기록한다. shadow·미리보기·확인 대기는 후자가 null이다.
- `parse_status`, `execution_status`, 요청 최종 상태를 구분한다. 서비스 성공 확인에만 `success=true`, 확정 실패/거부/timeout은 false다.
- 확인 대기·질문·지원 불가·복합 요청·취소·만료·중단·결과 불명은 success=null이다. 서비스 전달 뒤 반영 여부를 모르면 `outcome_unknown`이다.
- 확인 버튼과60초 typed 보완은 원래 request ID·멱등성 키를 유지한다. 사용자가 해석을 바꾸는 별개의 새 자연어 요청은 새 ID와 parent ID를 쓰되 이전 원문을 복사해 보관을 연장하지 않는다. 자동 재시도용 새ID는 금지한다.
- UTC Unix milliseconds와 monotonic duration을 사용한다. 처리·확인 대기·전체 경과를 분리하고 재시작 복구 시간은 `wall_clock_recovered`로 표시한다.

## 사용량·비용과 관리자 조회

- 두 Jev 패스와 두 LLM 작업의 모든 실제 시도를 call ID당 한 번 합산한다. 한 호출의 여러 질문·response/result/finished 이벤트를 중복 가산하지 않는다.
- `remote_attempted=false`인 전송 전 중단은 실제 API·usage 누락률 분모에서 제외한다. 전송 후 timeout/취소는 공급자 수신·과금 확정이 아니다.
- input/output/total/cached/reasoning과 reported/partial/unknown을 구분한다. 미확인 값은 null이며 total만 보고 input/output을 역산해 만들지 않는다.
- `known_input_tokens`, `known_output_tokens`, `usage_complete`, `unknown_usage_call_count`와 경로별 누락률을 제공한다. 미확인 비용을 0원으로 표시하지 않는다.
- cached input은 입력의 부분집합, reasoning은 출력의 부분집합이다. 합계에 다시 더하지 않고 버전·기준일이 있는 공급자/모델별 요율표를 적용한다.
- 원격 호출 없는 로컬 경로만 이번 요청 usage=0이다. cache를 만든 과거 요청의 토큰을 재합산하지 않는다.
- 관리자·서버 범위의 목록/상세/필터에서 미호출·생략·API 실패·해석 실패를 구분하고 모든 지표의 분모를 표시한다. 일반 채널로 원문을 자동 전송하지 않는다.
- `jev_after_rewrite`는 LLM 관여 경로다. 서비스 성공률을 의미 정확도로 표시하지 않고 별도 정답 검토·독립 평가 결과를 사용한다.

## 정확한 만료·삭제·복구

1. `expires_at_ms = created_at_ms + 604800000`을 최초 INSERT에서 계산한다. created/expires 불변 trigger를 두고 운영 retention 설정은 7만 허용한다.
2. 목록·상세·자식·통계·관리자 API·export 모두 `expires_at_ms > now_ms`만 반환한다. 정확히 7일이면 삭제 스케줄 실행 전에도 조회에서 제외한다.
3. 정규화·rewrite·확인·갱신·조회·내보내기·cache hit은 TTL을 연장하지 않는다. 텍스트·인수를 담은 파생 사본도 원문 기산점을 따른다.
4. 시작 시 조회 개방 전에 만료 정리, 이후 매시간 작은 배치로 삭제한다. 전용 유휴 연결과 FK cascade를 사용하며 업무 트랜잭션을 함께 commit하지 않는다.
5. 삭제 지연·오류·마지막 성공·WAL 크기·checkpoint 실패를 관측한다. `secure_delete=ON`은 매체·백업 전체 즉시 소거 보증이 아니며 열린 WAL/SHM을 임의 삭제하지 않는다.
6. trace 디렉터리·WAL·export·cache·임시 파일을 장기 스냅샷에서 제외하거나 원문 만료를 적용한다. 이미 6일 된 원문을 백업한 뒤 7일 더 보관하는 방식은 허용하지 않는다.
7. 실제 trace v1 존재 여부부터 확인한다. 새 v2 파일 또는 명시 migration을 사용하고 `CREATE TABLE IF NOT EXISTS`만으로 기존 스키마를 바꿨다고 하지 않는다.
8. 이관 시 기존 Jev는 initial, 기존 fallback은 full_parse로 대응한다. 없던 정규화/rewrite/시간/usage는 null 또는 not_recorded로 남긴다.
9. 원래 ID·수신/만료·실행 상태를 유지하고 만료 원문은 이관하지 않는다. rollback·export·임시 DB에도 원래 만료를 적용한다.
10. 재시작/복원 후 결과는 독립 서비스 원장으로 확인한다. trace가 없다는 이유로 명령을 실행하거나 예산·epoch·tombstone을 초기화하지 않는다.

## 마스킹과 장애 처리

- 원문·정규화문·rewrite·후보·결과·오류·export를 큐 투입/영속화 전에 재귀 마스킹한다. 알려진 시크릿·키 이름·패턴·비밀 URL query를 조합한다.
- 처리용 불변 원문과 로그 사본을 분리한다. 텍스트 8000자·결과 16384 UTF-8 bytes·source map 256개 상한은 처리 입력을 자르지 않는다.
- 축약/마스킹 여부·원래 길이를 기록하고 JSON/UTF-8 유효성을 보존한다. 로그의 마스킹 후 인덱스를 실행 근거 source map으로 재사용하지 않는다.
- raw provider response·전체 프롬프트·헤더·SDK dump·숨겨진 추론은 기본 미저장이다. 최소 파일 권한과 사용자 대상 7일 보관 안내를 마련한다.
- bounded queue와 전용 writer/worker를 사용한다. 잠금·디스크 부족·큐 포화는 `LOG_WRITE_FAILED`·누락 수·마지막 성공으로 경보한다.
- trace는 best-effort이며 장애로 모델/서비스를 재호출하지 않는다. durable 비용 예약·실행 멱등성 원장은 별도 필수 기록이다.
- 설정 오류를 조용한 로깅 비활성으로 처리하지 않는다. 로컬 7일 보관과 외부 공급자의 보존 정책을 동일하다고 안내하지 않는다.

## 검증 계획과 종료 게이트 — DiscordBotLXC 전용

| 시험 ID | 필수 증거 |
|---|---|
| R120-21 | 모든 경로의 이벤트·두 패스·생략·중간 실패 보존; resolved/executed/확인/unknown 구분; 늦은 응답의 실행 차단 |
| R120-22 | 다질문·중복 observer의 usage 1회; 실패 응답 usage 보존; null/partial·토큰 부분집합·요율·분모 검증 |
| R120-23 | 정확히 7일 경계 전/동일/후 조회; 모든 읽기 경로 필터; cascade·불변 TTL; 업무/예산 원장 유지 |
| R120-24 | 비밀값이 큐/DB/콘솔/export에 남지 않음; 유효한 축약; lock/disk/queue 장애에도 원격/서비스 추가 시도 0회 |
| R120-25 | 로컬 WAL·cache·export·임시 복원 경로의 원문 기산 만료; 알려진 스냅샷 제외 설정과 미확인 범위 기록 |
| R120-26 | 기존 trace 유무 확인; 명시 migration/구독자 호환·원래 시각/상태 보존; 가상 과거 이력 및 예산 초기화 없음 |

- [ ] R120-21~26 결과·실패·잔여 범위를 STATUS에 연결한다. 단위/mock 결과와 실제 LXC 저장소·운영 증거를 구분한다.
- [ ] 기존 사용자 결정인 **백업 검증 SKIPPED**를 유지한다. 새 로컬 만료·이관 시험과 외부 백업/복원 검증을 구분하고 후자를 PASS로 추정하거나 자동 요구하지 않는다.
- [ ] 장기 스냅샷 제외가 확인되지 않으면 그 제한을 기록한다. 7일 조회 차단 성공만으로 모든 사본의 물리 삭제를 보증하지 않는다.
- [ ] 로그 계약·마스킹·사용량·예산 분리가 검증되어 11의 독립 평가가 요청 원문을 무단 장기 평가 데이터로 복제하지 않는다.
