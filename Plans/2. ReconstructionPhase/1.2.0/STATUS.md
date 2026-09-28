# 1.2.0 진행 상태

- 전체: **IN_PROGRESS — 사용자 재개 지시로 p3부터 진행**
- 재개 기록: [HANDOFF](HANDOFF.md). p1·p2 체크포인트 뒤 중단한 상태를 보존하고 재개했다.
- 제품 구현/검증: p1 계약3시험·p2 등록부/기존경로45회귀 LXC PASS, 전체인수 미완료. GPT 실호출0·검증 누적지출상한US$1.
- 현재 산출물: 사용자 명세와 목록 전달 추가 지시를 반영한12단계 계획·아키텍처·요구 배정·시험표.
- 계획 작성 기준SHA: `474dad904466f0cce0817f7ac2527e4b86d9264c`.
- 원본 명세 SHA256: `70bc3e9b63fbbd3b6b52589289852a7aac123baa139e57487e0d58be071f3a2c`.

## 단계별 상태

| 단계 | 계획 | 상태 | 제품revision/실행증거 | 다음 게이트 |
| --- | --- | --- | --- | --- |
| 01 | [기준선·계약](01_baseline_and_contracts.md) | IN_PROGRESS | [p1 실행](../../../evidence/public/reconstruction-120-progress.md) | 계약3시험PASS; 전수대응은p2와연결 |
| 02 | [등록부·서비스](02_registry_and_command_service.md) | IN_PROGRESS | [p2 실행](../../../evidence/public/reconstruction-120-progress.md) |47개등록부·45회귀PASS, 신규연결p9 |
| 03 | [정규화·원문](03_normalizer_and_provenance.md) | IN_PROGRESS | [p3 실행](../../../evidence/public/reconstruction-120-progress.md) / LXC 단위10 PASS | 새 Discord 경로와 원문값 검증 연결은p4/p9 |
| 04 | [실제 목록·새 값](04_typed_candidates_and_resolution.md) | PLANNED | — / NOT_RUN | 목록 완전성/소속·원문값 추출 |
| 05 | [gateway·예산](05_gateway_budget_and_api_migration.md) | PLANNED | — / NOT_RUN | 신규 계약·원자 예약·취소 |
| 06 | [Jev 두 패스](06_jev_interpreter.md) | PLANNED | — / NOT_RUN | 묶음질문·조회의존3차 |
| 07 | [LLM 프로필](07_llm_provider_profiles.md) | PLANNED | — / NOT_RUN | 두schema·adapter·disabled |
| 08 | [복구 전이](08_rewrite_and_fallback_orchestration.md) | PLANNED | — / NOT_RUN | 의미보존·분기/종료 |
| 09 | [검증·Discord](09_validation_dialogue_and_discord.md) | PLANNED | — / NOT_RUN | 단회후속·실제확인·권한 |
| 10 | [로그·보관](10_structured_logs_and_retention.md) | PLANNED | — / NOT_RUN |7일·usage·원장 분리 |
| 11 | [LXC 평가·이관](11_lxc_evaluation_and_migration.md) | PLANNED | — / NOT_RUN | 고정 후보의 독립 품질/복귀 |
| 12 | [실제 인수·전환](12_discord_rollout_and_model_lifecycle.md) | PLANNED | — / NOT_RUN | 동일 후보 Discord·수명·최종판정 |

## 보존할 기준선과 이전 미완료

아래는 기존 공개 증거를 읽은 기록이며 이번 계획에서 LXC를 새로 관측한 결과가 아니다. 구현 착수 때 최신 실제 상태를 확인하고 과거 결과를 덮어쓰지 않는다.

| 기존 항목 | 확인된 기록과 제한 | 1.2.0 처리 |
| --- | --- | --- |
| 활성 개발 후보 | 기록상 bot patch117b / gateway patch116g | 01에서 재확인,12 전환까지 기존 후보 보호 |
| 1.1.8 patch118a | source/wheel 각369개시험, intent45/46, 미적용 | 이전 개발 근거로만 유지; 새 registry/parser 인수는11/12 |
| 전체 명령/옵션·I01~I08 | typed continuation·선택/페이지·전체 역할/응답·독립221 미완료 | 02/04/09/11/12에 책임 이관, 과거DONE 아님 |
| 1.1.6 | 독립 명확103/120 FAIL; 본 자료 개발용 전환 | 새 구조의 개발 회귀에 포함, 신규 잠금 정답 별도 |
| 1.1.7 | 첫 PCM94/100 FAIL; patch117b 새100회·실제음성100/8시간·운영수명 등 미완료 | 파서 정확도로 닫지 않음. 영향받는 항목과 전체출시 게이트12에서 분리 |
| 백업 검증 | 사용자 지정 SKIPPED | 그대로 유지. 신규 trace TTL/이관 시험을 백업PASS로 치환하지 않음 |
| Jev 예산 | 마지막 공개기록639/3000, epoch single-lxc-20260928 | 현재잔여는 미조회. 동일원장/누계 보존,05/11에서 새 비용계획 |
| GPT 자료 | 지정 비공개 파일에 자격정보 존재 | 인증·model 접근·실비·보관계정정책 NOT_RUN, 키값 공개/복사 없음 |

[1.1.8 증거](../../../evidence/public/patch-118-development-20260928.md) · [1.1.6 증거](../../../evidence/public/patch-116-development-20260928.md) · [1.1.7 증거](../../../evidence/public/patch-117-development-20260928.md)

## 진행 규칙

계획 작성 후 로컬 저장소 파일 검사에서 공개 후보309개·문서 링크1712개와 ignore/비밀값 패턴 검사가 통과했다. 원본 명세 SHA256도 위 값과 동일하다. 이는 문서/저장소 점검이며 LXC 제품시험·GPT 인증 결과가 아니다.

문서/구조 점검과 제품시험은 따로 기록한다. 구현 시 단계별 시험ID·고정 후보manifest·결과/제약을 추가한다. 독립평가 실패·예산부족·환경장애를 숨겨서 DONE으로 이동하지 않는다. 개발후보 인수와 전체 기능/정식출시 상태는 별도로 판정한다. 실제 실행 증거 없는 모듈·설정·명령은 runbook의 검증된 사용법에 넣지 않는다.

[목차](README.md) · [시험표](TEST_MATRIX.md) · [이전계열 상태](../../1.PatchPhase/STATUS.md)
