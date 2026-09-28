# 1.2.0 진행 상태

- 전체: **IN_PROGRESS — p12h 개발 봇 v2 적용, 실제 Discord 사용자 인수와 전체 평가 진행 중**
- 재개 기록: [HANDOFF](HANDOFF.md). p1·p2 체크포인트 뒤 중단한 상태를 보존하고 재개했다.
- 제품 구현/검증: p1~p12h 후보 회귀, p12d/e gateway Jev·GPT 제한 합성호출, p12h 테스트 서버 봇 적용을 기록했다. 전체인수 미완료. GPT 실제 누적 US$0.000521/예약 US$0.002005, 검증 상한 US$1.
- 현재 산출물: 사용자 명세와 목록 전달 추가 지시를 반영한12단계 계획·아키텍처·요구 배정·시험표.
- 계획 작성 기준SHA: `474dad904466f0cce0817f7ac2527e4b86d9264c`.
- 원본 명세 SHA256: `70bc3e9b63fbbd3b6b52589289852a7aac123baa139e57487e0d58be071f3a2c`.

## 단계별 상태

| 단계 | 계획 | 상태 | 제품revision/실행증거 | 다음 게이트 |
| --- | --- | --- | --- | --- |
| 01 | [기준선·계약](01_baseline_and_contracts.md) | IN_PROGRESS | [p1 실행](../../../evidence/public/reconstruction-120-progress.md) | 계약3시험PASS; 전수대응은p2와연결 |
| 02 | [등록부·서비스](02_registry_and_command_service.md) | IN_PROGRESS | [p2 실행](../../../evidence/public/reconstruction-120-progress.md) |47개등록부·45회귀PASS, 신규연결p9 |
| 03 | [정규화·원문](03_normalizer_and_provenance.md) | IN_PROGRESS | [p3 실행](../../../evidence/public/reconstruction-120-progress.md) / LXC 단위10 PASS | 새 Discord 경로와 원문값 검증 연결은p4/p9 |
| 04 | [실제 목록·새 값](04_typed_candidates_and_resolution.md) | IN_PROGRESS | [p4·p12f 실행](../../../evidence/public/reconstruction-120-progress.md) / 첨부 실제목록/재검증 포함 | 전체 collection·복수선택/실제 Discord 인수 미완료 |
| 05 | [gateway·예산](05_gateway_budget_and_api_migration.md) | IN_PROGRESS | [p5 실행](../../../evidence/public/reconstruction-120-progress.md) / 관련 LXC 25 PASS | 실제 provider 비용상한·운영 연결·중단/원장장애 검증 |
| 06 | [Jev 두 패스](06_jev_interpreter.md) | IN_PROGRESS | [p6 실행](../../../evidence/public/reconstruction-120-progress.md) / LXC mock8 PASS | 실제Jev 품질·복수선택/전체인수 |
| 07 | [LLM 프로필](07_llm_provider_profiles.md) | IN_PROGRESS | [p7·p12e 실행](../../../evidence/public/reconstruction-120-progress.md) / LXC mock13 PASS·GPT 합성3호출 | 실제 rewrite/full_parse 제한계약·실비 확인; 전수품질/계정운영 미완료 |
| 08 | [복구 전이](08_rewrite_and_fallback_orchestration.md) | IN_PROGRESS | [p8·p12g 실행](../../../evidence/public/reconstruction-120-progress.md) / 무관 빈 목록 분리·실등록부 schema 검사 | 실제통합 전이·후보/의미 검증 |
| 09 | [검증·Discord](09_validation_dialogue_and_discord.md) | IN_PROGRESS | [p9·p12a/b/f 실행](../../../evidence/public/reconstruction-120-progress.md) / v2 읽기·한 인수 typed·단회확인·첨부 재검증 대역PASS | 다중/의존인수·전체명령/후속·실제권한/확인 미완료 |
| 10 | [로그·보관](10_structured_logs_and_retention.md) | IN_PROGRESS | [p10·p12c 실행](../../../evidence/public/reconstruction-120-progress.md) / v2 opt-in 최소관측 대역PASS | bounded writer·이관/보관사본·관리자 조회 미완료 |
| 11 | [LXC 평가·이관](11_lxc_evaluation_and_migration.md) | IN_PROGRESS | [p11·p12d~h 실행](../../../evidence/public/reconstruction-120-progress.md) / p12h source·새 bot wheel 각492 PASS; 실제 Jev/GPT 합성호출 | 독립221·전체옵션·격리이관/복귀 NOT_RUN |
| 12 | [실제 인수·전환](12_discord_rollout_and_model_lifecycle.md) | IN_PROGRESS | [p12h 적용](../../../evidence/public/reconstruction-120-progress.md) / bot v2·gateway v2/LLM disabled, Discord API 인증·명령등록 확인 | 사용자 실제 명령·전수·음성 인수 NOT_RUN/진행 중 |

## 보존할 기준선과 이전 미완료

아래는 기존 공개 증거를 읽은 기록이며 이번 계획에서 LXC를 새로 관측한 결과가 아니다. 구현 착수 때 최신 실제 상태를 확인하고 과거 결과를 덮어쓰지 않는다.

| 기존 항목 | 확인된 기록과 제한 | 1.2.0 처리 |
| --- | --- | --- |
| 활성 개발 후보 | bot `recon120p12hbot` / gateway `recon120p12egw` | 테스트 서버 한 곳에 bot v2/LLM disabled 적용; 이전 `patch117b` unit/DB 보존 |
| 1.1.8 patch118a | source/wheel 각369개시험, intent45/46, 미적용 | 이전 개발 근거로만 유지; 새 registry/parser 인수는11/12 |
| 전체 명령/옵션·I01~I08 | typed continuation·선택/페이지·전체 역할/응답·독립221 미완료 | 02/04/09/11/12에 책임 이관, 과거DONE 아님 |
| 1.1.6 | 독립 명확103/120 FAIL; 본 자료 개발용 전환 | 새 구조의 개발 회귀에 포함, 신규 잠금 정답 별도 |
| 1.1.7 | 첫 PCM94/100 FAIL; patch117b 새100회·실제음성100/8시간·운영수명 등 미완료 | 파서 정확도로 닫지 않음. 영향받는 항목과 전체출시 게이트12에서 분리 |
| 백업 검증 | 사용자 지정 SKIPPED | 그대로 유지. 신규 trace TTL/이관 시험을 백업PASS로 치환하지 않음 |
| Jev 예산 | p12e 합성 호출 뒤 예약645/3000, epoch single-lxc-20260928 | 동일원장/누계 보존, 추가 실호출은 별도 기록 |
| GPT 자료 | 지정 비공개 파일 자격정보로 제한 합성3호출 | 누적 예약2005·실제521 micro USD/US$1 상한. 시험 후 gateway disabled·LXC 임시 키 제거; 장기 운영·독립품질 미완료 |

[1.1.8 증거](../../../evidence/public/patch-118-development-20260928.md) · [1.1.6 증거](../../../evidence/public/patch-116-development-20260928.md) · [1.1.7 증거](../../../evidence/public/patch-117-development-20260928.md)

## 진행 규칙

계획 작성 후 로컬 저장소 파일 검사에서 공개 후보309개·문서 링크1712개와 ignore/비밀값 패턴 검사가 통과했다. 원본 명세 SHA256도 위 값과 동일하다. 이는 문서/저장소 점검이며 LXC 제품시험·GPT 인증 결과가 아니다.

문서/구조 점검과 제품시험은 따로 기록한다. 구현 시 단계별 시험ID·고정 후보manifest·결과/제약을 추가한다. 독립평가 실패·예산부족·환경장애를 숨겨서 DONE으로 이동하지 않는다. 개발후보 인수와 전체 기능/정식출시 상태는 별도로 판정한다. 실제 실행 증거 없는 모듈·설정·명령은 runbook의 검증된 사용법에 넣지 않는다.

[목차](README.md) · [시험표](TEST_MATRIX.md) · [이전계열 상태](../../1.PatchPhase/STATUS.md)
