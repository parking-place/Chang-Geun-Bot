# 0.6.0 — 한국어 자연어 명령과 조건부 3단계 판단

| 항목 | 내용 |
| --- | --- |
| 상태 | IN_PROGRESS — 부분 구현·LXC 시험; 전체 인수 전 |
| 이전 버전 의존성 | [0.5.0](../0.5.0/README.md) 선택 프로필의 API 1.2·영속 원장·호출 예산·기한 안전 인수 |
| 선행 기능 의존성 | 0.1.0 공통 실행기·권한, 0.2.0 슬래시/버튼, 0.4.0 재생·generation |
| 주 시험 호스트 | DiscordBotLXC 해석·실행·UI; DiscordBotLXC의 중계 후보 판단·계측 |
| 기준 명세 | [개발 명세 1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) §§4,7,8,9,12,13,16,17 및 [추론 프로필](../INFERENCE_PROFILES.md) |

이 버전은 한국어 요청에서 실제 데이터 후보를 만들고, 1단계 의도·2단계 행동·조건부 3단계 문맥을 공통 명령 실행기에 연결한다. 1·2단계에서 명확하면 즉시 종료하고 부족한 정보는 사용자 UI로 받는다. 모델은 실행 권한·자유 인자·새 ID를 만들지 않는다.

자연어 요청당 최대 3단계·3질문·공급자 dispatch 3회와 단계당 질문/dispatch 1회는 Jev API 실제 프로필 모두 0.5.0 계약을 그대로 사용한다. `usage.provider_calls`는 단계별 신규 dispatch(0 또는 1), `usage.request_provider_calls_total`은 요청 누계(3 이하)이며 캐시/합류는 추가 호출 없이 누계를 유지한다. hosted 내부 forward 두 필드는 `null`, `forward_passes_source=unavailable`로 남긴다. 삭제·대량 변경·덮어쓰기 확인과 최신 권한·대상·버전 재검증은 판단 횟수나 높은 점수로 생략되지 않는다.

구현한 `scripts/test_profile.py --profile jev-api --suite korean-eval`은 실제 Jev API의 개발37문장을 평가한다. `--profile mock --suite contract`는 격리 회귀이며 실제 자연어 품질 증거가 아니다. SSH 설정·현재 고정 후보 활성화와 지원 suite는 [원격 runbook](../../../docs/REMOTE_DEVELOPMENT.md)을 따른다. 개발 평가용 DB는 격리 복사하고 run별 원장·결과를 보존한다. 후보/설정 변경은 정지·drain·tombstone·새 세션 절차를 따른다. prompt/threshold는 개발 세트에서 보정하며 독립 held-out·성능·8시간 시험은 별도 구현·인수한다.

로컬은 코드·문서·평가 데이터 작성과 읽기 검토만 한다. 단위/mock 시험·lint·타입 검사·설치·빌드·평가·벤치마크를 포함한 모든 실행은 DiscordBotLXC의 봇·중계에서 수행한다. 프롬프트 개발용 데이터와 0.9.0 최종 held-out 세트를 분리한다.

| 단계 | 문서 | 주요 결과 |
| --- | --- | --- |
| 1 | [전처리·후보·문맥](01_candidates_context.md) | 원문 보존·수사·동일 사용자 snapshot |
| 2 | [의도·행동과 조기 종료](02_intent_action.md) | 1/2단계 라우팅·clarify 즉시 UI |
| 3 | [조건부 최종 문맥 판단](03_conditional_stage_three.md) | 근거 있는 3단계·네 번째 호출 차단 |
| 4 | [실행 안전·확인·경쟁](04_execution_safety.md) | 공통 실행기·부정문·권한·대상 재검증 |
| 5 | [한국어 개발 평가와 인수](05_korean_evaluation.md) | 전체 N 회귀·개발 세트·경로별 계측 |

출구 기준은 Jev API에서의 N-01–36 안전 동작 통과, 명확한 1·2단계 요청의 불필요한 추가 호출 0건, 근거 없는 3단계·clarify 뒤 재추론·확인 우회·timeout/취소 뒤 실행 0건이다. 0.5.0 Jev API 안전 인수 후 후속 개발을 진행하며 필수 미실행/실패는 전체 DONE을 차단한다. 개발 평가의 명확한 지원 명령 해석 95% 목표와 최종 0.9.0 held-out 합격도 run별로 판정한다.

[시험 매트릭스](../TEST_MATRIX.md)의 B-09 동일 fixture/격리와 B-12 Jev API 프로필 품질·성능 분리 평가가 이 버전의 필수 인수 항목이다. B-04–08·B-10–11의 API·예산·전환·장애·전송 안전도 자연어 경로에서 회귀 검증하며 0.9.0 최종 성능/held-out 증거는 별도다.

0.7.0의 P1 태그 생성·제안함 등 기능이 아직 실행기에 없다면 해당 의도는 후보에서 제외하거나 미지원 안내로 종료한다. 향후 동작을 추측 실행하지 않는다. 정확도 부족 시 후보/별칭/지원 구문을 먼저 개선한다. 요청 도중 변경·자동 재시도·다른 공급자 fallback은 허용하지 않는다.

공통 문서: [추론 프로필](../INFERENCE_PROFILES.md), [실행 환경](../ENVIRONMENT.md), [시험 매트릭스](../TEST_MATRIX.md), [증거 양식](../EVIDENCE_TEMPLATE.md). 계획은 검증 증거가 아니며 profile ID·설정 해시·확인 가능한 모델/API·프롬프트·데이터·코드 revision별 결과와 미확인 항목을 기록한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
