# 1.2.0 아키텍처·이관 계약

상태: **PLANNED**. [원본 명세](../changgeun_jev_llm_fallback_command_parser_spec_v1.3.md)의 요구를 현재 저장소에 배치하는 계획이다. 아래 신규 모듈·API·설정은 아직 실행 가능한 배포 절차가 아니다.

## 책임과 배치

| 영역 | 책임 | 기존 기반 → 계획 산출물 |
| --- | --- | --- |
| Discord adapter | 진입점·주시/역할 필터, 상호작용과 비공개 표시 | `discord_adapter/client.py`, `natural.py`, `prefix.py`, `watch.py` → 얇은 입력/응답 어댑터 |
| 명령 등록부 | 명령/인수·권한·위험도·확인·고정 handler·응답 규격 | `nlp/command_registry.py` → typed registry, C-ID 호환표, slash/Schema 생성 |
| 봇 파서 | 원문/source map·실제 목록 전달·새 값 추출·패스 조정 | `nlp/pipeline.py` → `parser/normalizer.py`, `collections.py`, `value_extraction.py`, `jev_interpreter.py`, `orchestrator.py`, `validation.py` 등 역할별 모듈 |
| 공통 서비스 | 실제 객체 조회·최신 권한/세대·확인·멱등성·실행 | `application/executor.py`, watch/undo/transfer/generation, `natural.py` → 공통 `CommandService` |
| 게이트웨이 | 외부 전송·공통 원격 예산·deadline·취소·사용량 | `inference`의 contracts/service/ledger/server/providers → 구계약+`parser-api-v2`, Jev/LLM adapter |
| 공급자 독립 LLM | `rewrite()`/`full_parse()` 서비스와 `generate()` 어댑터 | gateway 내부 `llm` 모듈·profile factory·OpenAI Responses adapter |
| 관측 | 마스킹한 trace·하위 이벤트·7일 만료·관리자 조회 | 봇 observability의 별도 trace 저장소 + gateway의 sanitized usage 이벤트 |

봇과 중계는 현재처럼 DiscordBotLXC의 별도 계정과 loopback TLS를 사용한다. 봇이 원문·실제 목록 스냅샷·새 값의 원문 구간·명시적 문맥을 준비하고 중계는 허용된 모델 작업만 처리한다. gateway는 업무 DB를 읽거나 명령을 실행하지 않는다. 실제 OpenAI/Jev 키는 중계 계정에만 주입한다. 모델 SDK 타입이 공통 도메인/검증기/로그 스키마로 전파되지 않게 한다.

## 실제 목록 우선 계약 — 사용자 추가 지시

재생목록·카탈로그·선택 목록의 곡/entry·채널처럼 명확히 열거할 수 있는 자료에는 `selection_source=collection`을 사용한다. 권한·명령 종류·사용자의 명시 범위로 조회한 완전한 목록을 Jev에 전달하고 실제 항목을 불투명 ID로 선택하게 한다. 새 이름·검색어는 `source_span`, 숫자/URL/멘션은 결정적 추출, enum은 등록부 선택지로 구분한다. 명령 자체도 허용된 등록부 목록에서 선택한다.

`CollectionSnapshot`은 root/pass/argument/collection key/scope/revision과 ID→실제 객체 매핑을 결합한다. DB/API 페이지를 수집했다면 같은 범위의 완전성도 검증한다. 임의 유사도 top-k, 첫80개, 자동 일부 실행으로 목록 전달을 대체하지 않는다. 최대80개는 원문 span의 시작 설정이며 실제 목록에 적용하지 않는다. 모델의 Choice 상한·토큰/byte 예산을 넘으면 확정 범위를 좁히도록 질문/UI로 전환한다. 모든 페이지를 추가 모델 호출로 훑어3/8회 상한을 우회하지 않는다.

after_rewrite/full_parse도 실제 목록과 소속 검증을 공유한다. 명령이 바뀌면 올바른 resolver로 새 스냅샷을 만들고, 오래된 revision은 최신 상태를 검증한다. 원문에 근거한 query는 코드의 목록 조회·범위 질문을 도울 뿐 실제 없는 객체 ID를 만드는 기능이 아니다. 이 보완은 원본 명세5절의 일반 후보 생성 설명보다 우선하며 원본 파일은 그대로 보존한다.

새 경로 이름은 역할을 설명하는 제안이다. 구현01단계에서 최종 위치를 확정하고, 완성된 명령만 원격 runbook에 추가한다. 레지스트리 코드 공유가 필요하면 의존성이 없는 계약 패키지로 분리하고 gateway가 Discord/업무 DB 패키지를 import하지 않게 한다.

## 현재 계약과 목표 계약

| 항목 | 현재 API1.2 / 1.1.x | 계획한1.2.0 |
| --- | --- | --- |
| 실제 제공자 | Jev API만 | Jev 우선 + 명시적 GPT rewrite/full_parse 프로필 |
| API 버전 | 단일 choice, 후보2~12, 단계1~3 | 별도 `parser-api-v2`; named questions·Choice/Noul·LLM operation·pass ID |
| 수량 관계 | stage=question=provider call | pass/stage/question/attempt/call을 분리; 묶음 질문은 원격1회 |
| 요청 상한 | Jev 최대3회 | initial≤3, after_rewrite≤3, Jev합≤6, rewrite≤1, full_parse≤1, LLM합≤2, 전체≤8 |
| 기한 | 전체12초 / 단계4초 | 전체35초 / Jev5초 / rewrite5초 / full_parse10초를 초기 실험값으로 설정 |
| 임계값 | 기본0.80/0.10 + 개발용 동일후보 재질문 합의 | confidence0.85/margin0.15, Noul포함0.85/제외0.15부터 보정; 재해석 완화/동일질문 합의 제거 |
| 로그 | 업무/요청/감사 자료 혼재 | 업무·비용/멱등성 원장과 별도 `command-trace-v2` DB |
| 사용자 대기 | 1.1.8 typed continuation 미구현 | 단회 슬롯 보충60초·실행 확인300초, 둘 다 모델 파이프라인 종료 후 별도 검증 |

**원본 설계서10.1의 ‘기존 최대4회’는 설계서 이전 판의 설명**이다. 실제 이 저장소는3회이므로 3→8로 이관한다. 설계서15.16의 trace v1 이관도 해당 형식의 실제 데이터가 존재할 때만 적용한다. 기존 자료를 가짜 v1 trace로 간주하거나 없는 rewrite 이력을 생성하지 않는다.

문서 버전1.3, 제품1.2.0, wire `parser-api-v2`, `rewrite-pipeline-v1`, `command-parse-v1`, `command-rewrite-v1`, `command-trace-v2`는 서로 다른 식별자다. 구 API1.2 소비자는 기존3회 계약을 유지하며 새 payload를 잘못 읽으면 시작/요청을 거부한다. 새 API 활성화는 양쪽 candidate와 호환 검증을 함께 요구한다.

## 요청·예산·취소의 소유권

봇 입력 원장은 Discord 메시지/interaction을 하나의 root request에 결합한다. gateway는 root의 소유 범위 digest·원문 binding·고정 profile/config·절대 기한과 예약 누계를 영속 보관한다. `pass_id`, `operation`, `stage_index`, `attempt_no`, `call_id`는 root 아래의 하위 키다. rewrite문을 root binding에 덮어쓰지 않고 별도 입력 variant로 결합한다. 새 request_id나 새 Budget을 만들어 재해석 상한을 우회하지 않는다.

원격 예약이 authoritative하며 봇의 카운터는 표시/사전 점검용이다. 전송 전 원자 예약, SDK/HTTP retry0, 취소·응답유실·재시작 불명 시 재전송/환불 금지 원칙을 유지한다. 확인 후 실행은 모델0회이고 같은 root/멱등성 키를 유지한다. slash·구조화 제어는 추론이 없어도 자체 실행 검증/멱등성을 가진다.

현재 epoch/profile·기존3000 Jev 호출 누계는 유지한다. 프로토콜 버전 전환에 새 config/profile 식별자가 필요해도 **누적 할당량의 계보와 사용량을 승계**한다. GPT는 별도 유한 금액·토큰 한도와 공통 요청당 한도를 동시에 적용한다. 금액이 지정되지 않았거나 사용량 불명·최악 예상 지출을 감당할 수 없으면 유료 평가를 시작하지 않는다. 이번 계획은 기존 예산의 증액 결정이 아니다.

## 상태와 데이터 분리

파서는 한 개의 미검증 `CommandDraft`를 만들고 공통 검증기가 `ValidatedCommand`로 바꾼다. 모델이 만든 confirmed/permission/객체ID는 승인 근거가 아니다. rewrite를 거친 쓰기는 마지막 선택자가 Jev여도 LLM 관여 확인 정책을 유지한다. 실행 결과 불명은 재해석해서 재실행하지 않는다.

업무 DB에 이미 있는 `command_requests`는 실행 중복 방지 기록이다. 명세15의 동명 trace 테이블을 이 DB에 생성/덮어쓰거나7일 purge하지 않는다. 별도 trace DB의 부모 요청과 model_calls/events만 최초 수신+7일에 만료한다. 원문이 필요한 업무상 결과(예: 사용자가 저장한 목록명)와 관측 사본의 보관 목적도 구분한다. 비용/예산·멱등성 tombstone은 내용을 최소화하여 기존 유효 수명을 유지하고, 원문/응답 캐시는7일을 넘기지 않는다.

## 설정·비밀값·공식 API 확인

`LLM_FALLBACK=gpt-5-nano`와 실제 API model ID는 분리한다. 요청 시작 시 모델/프로필/어댑터/프롬프트/스키마를 고정한다. `disabled`는 키 없이 두 LLM 작업을 끄며, 오타·빈 값·미구현 Gemini/Luna·구형 통합 timeout 설정은 오류다. YAML과 env는 하나의 유효 설정으로 합치고 config hash에 비밀값을 넣지 않는다.

사용자가 지정한 `.private/gpt-5-nano-info`에 자격정보가 있음을 확인했다. 파일명으로 모델 접근권을 추정하지 않으며 계정·키 인증·요금·한도는 아직 시험하지 않았다. 이 파일은 실행용 환경 파일로 shell-source하지 않는다. 구현 시 로컬 입력/원격 비밀 파일의 접근권한을 점검하고 root0600 주입 경로로 옮기며, 공개 계획·argv·trace·예외에 내용이 들어가지 않게 한다.

2026-09-28 공식 OpenAI documentation 확인 범위:

- GPT-5 nano는 Structured Outputs를 지원한다. 계정별 실호출 가능성은 별도 LXC 검증 대상이다. [모델 문서](https://developers.openai.com/api/docs/models/gpt-5-nano)
- Responses의 구조화 결과는 엄격 JSON Schema와 거절/미완료 처리를 함께 사용한다. 생성 형식이 맞아도 원문·권한 검증은 필수다. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- `store=false`를 계획하지만 자체7일 trace 정책과 공급자 보관은 별개다. 이 설정만으로 공급자 모든 로그의7일 삭제/Zero Data Retention을 보장한다고 쓰지 않는다. [데이터 보관 문서](https://developers.openai.com/api/docs/guides/your-data)
- nano 스냅샷 `gpt-5-nano-2025-08-07`의 종료 예정은2026-12-11이며 권장 교체는 `gpt-5.6-luna`다. 내부 전환 목표2026-12-01은 프로젝트 계획이고 자동 모델 교체는 하지 않는다. 초기 모델은 사용자 지정 nano를 유지한다. [종료 공지](https://developers.openai.com/api/docs/deprecations)

[목차](README.md) · [05 예산](05_gateway_budget_and_api_migration.md) · [10 보관](10_structured_logs_and_retention.md) · [12 전환](12_discord_rollout_and_model_lifecycle.md)
