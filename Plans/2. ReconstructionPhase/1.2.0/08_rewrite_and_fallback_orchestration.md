# 08. rewrite·재해석·full fallback 상태 전이

상태: **IN_PROGRESS**. 유한 상태 전이·보호 리터럴 검사·mock 전이 시험은 완료, 실제 후보/Discord·최악8회 통합 시험은 미완료다.

[버전 개요](README.md) · [아키텍처](ARCHITECTURE.md) · [시험 추적](TEST_MATRIX.md) · [실행 상태](STATUS.md)

## 목적과 선행 조건

- [재구성 명세](../changgeun_jev_llm_fallback_command_parser_spec_v1.3.md) §6.7·7·8·10의 복구 경로를 유한한 상태기계로 구현한다.
- 03/04의 원문·후보, 05의 `parser-api-v2` 공통 예산, 06의 Jev 두 패스, [07의 LLM 계약](07_llm_provider_profiles.md)이 선행 조건이다.
- 공급자는 해석만 담당한다. 오케스트레이터는 SDK 타입·모델명으로 업무 분기하지 않고 검증된 초안을 09에 전달한다.
- 현재 운영의 Jev-only/API 1.2 경로는 별도로 유지하며 새 경로를 계획만으로 활성화하지 않는다.
- 후속 사용자 지시에 따라 재생목록·곡·채널처럼 실제 목록이 있는 인수는 권한·명시적 범위 안의 전체 목록을 전달한다. 언어 후보·fuzzy/top-K로 대체하지 않는다.

## 기본 경로와 예외

| 현재 결과 | 다음 상태 |
|---|---|
| 최초 Jev 성공 | 공통 검증 |
| 원문에 답이 있는 복구 가능한 해석 실패 | rewrite 최대 1회 |
| 유효하게 바뀐 rewrite | Jev `after_rewrite`, 명령부터 재선택 |
| unchanged·동일문장 | 동일 Jev 생략 후 원문 full_parse |
| 복구 가능한 rewrite 형식·보존 검사 실패 | rewrite 폐기 후 원문 full_parse |
| 재해석 Jev의 해석 실패 | full_parse 최대 1회 |
| 실제 필수값 누락·구분 불가 동명 객체 | typed 질문/선택, 값 발명 금지 |
| 실제 목록이 전송 한도 초과·범위 불명확 | 범위 질문/목록 UI, 조용한 절단·모델 페이지 반복·LLM 우회 금지 |
| 권한·서버 범위·금지 동작·실제 값 검증 오류 | 차단/오류 안내 |
| 명확한 잡담·미지원·복합 요청 | 실행 없이 안내/종료 |
| LLM 거절·인증·통신·제한·timeout·요청 오류 | 종료, 다른 mode로 통신 재시도 금지 |
| Jev unavailable | 허용 설정·LLM 가용·잔여 예산이 모두 있을 때 원문 full_parse |
| full_parse 완료 또는 실패 | 공통 검증/질문/종료, 모델 경로 재진입 금지 |

## 구현 작업

1. 원문·정규화문·rewrite·후보 snapshot을 서로 구분하고 요청마다 고정된 계약·프로필·registry 버전을 보관한다.
2. 자유 문자열의 원문 구간 누락과 실제 목록 snapshot 부재/변경을 구분한다. 한 번의 `NO_MATCH`만으로 DB 부재를 확정하지 않는다.
3. rewrite 상태별 필드 관계·길이·보호 리터럴·숫자·URL·범위·부정·제외를 검사하고 잘못된 문장은 이후 입력에서 제거한다.
4. rewrite는 의미 보존을 완전히 증명할 수 없으므로 09의 원문 근거 검사와 LLM 관여 write 확인을 유지한다.
5. 재해석은 initial 명령을 고정하지 않는다. pass별 후보 ID·질문 지표를 격리하고 낮은 확신을 rewrite 뒤에 확정값처럼 취급하지 않는다.
6. 두 패스의 명령·대상 상충은 `INTERPRETATION_CONFLICT`로 기록한다. 어느 패스도 자동 우선하지 않는다.
7. full_parse의 `repair_arguments`는 명령 확정 시 모든 인수를 포함한 전체 초안을 요구한다. 불확실/상충 시 `reparse`를 사용한다.
8. Jev 인수 일부와 LLM 인수 일부를 합치지 않는다. 검사 통과한 rewrite만 참고로 보내고 원문은 항상 포함한다.
9. 생략 단계는 `stage.skipped`와 이유를 기록한다. unchanged/JEV_UNAVAILABLE 생략과 임의 최적화를 구분한다.
10. Jev 장애 우회는 명시적 설정에 한정한다. registry·후보 생성 자체의 치명적 오류나 권한 거부는 공급자 변경으로 우회하지 않는다.
11. 실행 실패는 서비스 오류로 반환한다. 파서 재진입·새 request_id·다른 provider로 재실행을 만들지 않는다.
12. 모든 await 전후에 취소·권한 무효화·남은 deadline을 확인하고 늦은 모델 결과를 실행에서 배제한다.

실제 목록 snapshot은 root request/pass/argument/원본 버전에 묶고 패스 전환 시 현재 상태를 확인한다. stale이면 같은 범위를 새로 조회하고 opaque ID를 다시 결합한다.
entity의 최종 대상은 전달한 실제 목록의 구성원이어야 한다. raw query는 실제 범위 목록 재조회/질문으로 연결하고 검색 첫 결과나 생성한 DB ID로 확정하지 않는다.
full_parse 이후 새 목록에서 선택이 필요하면 모델 재호출 없이 UI/typed 질문으로 종료·보완한다. 3회/8회 상한을 페이지나 재검색용 새 request_id로 우회하지 않는다.

## 예산과 관측 계약

- 초기 상한은 Jev 2패스×최대 3호출=6, rewrite 1, full_parse 1, 총 원격 시도 8회다. 숨은 SDK 재시도는 0이다.
- 전체 deadline 35초와 작업 timeout은 초기 튜닝값이다. 단계마다 남은 시간을 사용하고 후속 질문·확인 때문에 새 모델 예산을 열지 않는다.
- JevUnavailable 직접 fallback도 같은 parent request 원장을 사용한다. 예산 부족·취소 뒤 새 호출을 예약하지 않는다.
- reservation과 실제 전송, 호출 수와 질문 수를 분리한다. 기존 Jev epoch·누적 원장은 초기화하지 않는다.
- 최종 `parser_source`, `final_pass_id`, rewrite/full_fallback 사용 여부와 실패/생략 이력을 서버가 기록한다.
- full_parse 최종 결과의 `final_pass_id`는 null이다. 재해석 Jev 성공도 LLM이 관여한 경로임을 유지한다.

## 산출물

- orchestrator와 RewritePolicyValidator, 전이표·종료 코드·이벤트 정의.
- 정상·생략·질문·오류·취소 경로별 기대 call graph와 예산 fixture.
- 공통 검증으로 전달할 단일 초안 및 출처 metadata 계약, 운영 rollout 전 비활성 설정.

## 검증 계획 — DiscordBotLXC 전용

- **R120-16:** 곡명/새 이름·부정·제외·인용·숫자·URL·“모두” 삽입과 보호구간 손상을 주입하여 rewrite 폐기와 원문 복귀를 검증한다.
- **R120-16:** unchanged·동일문장·후보 누락·후보 패스 교체에서 동일 Jev 반복과 이전 후보 ID 사용을 차단한다.
- **R120-17:** 표의 모든 전이와 unavailable 설정 on/off, full_parse 범위, 모드별 장애, 재진입 금지를 검증한다.
- **R120-17:** 최악 경로 8회, 각 단계 취소·35초 초과·잔여시간 부족·동시 요청·재시작에서 상한과 늦은 실행 차단을 확인한다.
- **R120-08/09/12 연계:** 전체 scoped 목록 전달·snapshot stale·범위 초과·raw query 재조회와 full_parse 이후 모델 0회를 검증한다.

## 종료 게이트

- [ ] R120-16/17 모든 전이에 call 수·최종 상태·실행 여부 증거가 연결된다.
- [ ] 권한/누락/서비스 오류를 의미 해석 실패로 바꾸는 경로와 숨은 재시도가 없다.
- [ ] 09의 공통 검증 이전에 실행 가능한 결과를 만들지 않으며 결과를 STATUS에 기록한다.
