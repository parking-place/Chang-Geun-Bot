# 개발 진행 현황

실행 시작: 2026-09-27. 두 LXC(Debian 13, Python 3.13)에 비root 개발 경로를 준비했다. 도메인·SQLite·권한/확인·공통 실행기·재생 상태·추론 API/원장을 구현하고 원격 시험을 진행 중이다. Discord DAVE 초기 연결/시험음 전송과 Jev API 단일 판단 probe가 통과했다. **전체 버전 인수·출시는 아직 완료하지 않았다.** 구체적 증거와 제한은 [실행 기록](../../evidence/public/execution-20260927.md)을 따른다.

## 상태 규칙

| 상태 | 의미 |
| --- | --- |
| PLANNED | 계획만 있음; 작업/검증 미시작 |
| IN_PROGRESS | 코드·설정·문서 작성 중 |
| CODE_READY | 코드/산출물 준비, 지정 LXC 검증 전 |
| REVIEWED | 문서 전용 0.0.0/01의 계약 검토 완료; 제품 시험 PASS를 의미하지 않음 |
| VERIFIED | 해당 단계 필수 LXC 시험의 PASS 증거 있음 |
| DONE | VERIFIED 증거와 버전 게이트 검토까지 완료 |
| BLOCKED | 환경·기술·입력 또는 실패로 진행 차단; 이유와 해제 조건 기록 |

FAIL/SKIPPED/NOT_RUN은 검증 실행 결과다. 미실행·skip을 VERIFIED/DONE으로 처리하지 않는다. DONE 단계의 코드·설정·의존성 변경 시 영향 시험을 다시 수행하고 증거를 새 revision에 연결한다.

## 버전 상태

| 버전 | 단계 수 | 상태 | VERIFIED/DONE | 증거 / 차단 사유 |
| --- | --- | --- | --- | --- |
| [0.0.0](0.0.0/README.md) | 5 | IN_PROGRESS | 0 / 5 | 초기 실행/개발 증거; 전체 인수 미완료 |
| [0.1.0](0.1.0/README.md) | 5 | IN_PROGRESS | 0 / 5 | 초기 실행/개발 증거; 전체 인수 미완료 |
| [0.2.0](0.2.0/README.md) | 5 | IN_PROGRESS | 0 / 5 | 초기 실행/개발 증거; 전체 인수 미완료 |
| [0.3.0](0.3.0/README.md) | 5 | IN_PROGRESS | 0 / 5 | 초기 실행/개발 증거; 전체 인수 미완료 |
| [0.4.0](0.4.0/README.md) | 5 | IN_PROGRESS | 0 / 5 | 초기 실행/개발 증거; 전체 인수 미완료 |
| [0.5.0](0.5.0/README.md) | 5 | IN_PROGRESS | 0 / 5 | 초기 실행/개발 증거; 전체 인수 미완료 |
| [0.6.0](0.6.0/README.md) | 5 | IN_PROGRESS | 0 / 5 | 부분 구현·시험; 전체 인수 전 |
| [0.7.0](0.7.0/README.md) | 5 | IN_PROGRESS | 0 / 5 | 부분 구현·시험; 전체 인수 전 |
| [0.8.0](0.8.0/README.md) | 5 | IN_PROGRESS | 0 / 5 | 부분 구현·시험; 전체 인수 전 |
| [0.9.0](0.9.0/README.md) | 5 | PLANNED | 0 / 5 | 실행 미수행 |
| [1.0.0](1.0.0/README.md) | 5 | PLANNED | 0 / 5 | 실행 미수행 |
| [1.0.1](1.0.1/README.md) | 5 | IN_PROGRESS | 0 / 5 | [개발 후보·부분 LXC 시험](../../evidence/public/youtube-prefix-20260928.md); 실제 청취·전체 인수 전 |
| [1.0.2](1.0.2/README.md) | 5 | IN_PROGRESS | 0 / 5 | [두 채널 설정·접두어 구현](../../evidence/public/youtube-prefix-20260928.md); 독립 품질·전체 인수 전 |
| [1.0.3](1.0.3/README.md) | 5 | IN_PROGRESS | 0 / 5 | [관리6명령·개발 적용·사용자 부분 인수](../../evidence/public/watch-channels-20260928.md); W 전체 인수 전 |

## 단계별 상태

| 버전 / 단계 | 계획 문서 | 상태 | 코드 revision | 실행 증거 | 차단 / 다음 작업 |
| --- | --- | --- | --- | --- | --- |
| 0.0.0 / 01 | [01_scope_and_contracts.md](0.0.0/01_scope_and_contracts.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.0.0 / 02 | [02_repository_and_remote_workflow.md](0.0.0/02_repository_and_remote_workflow.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.0.0 / 03 | [03_lxc_readiness_and_isolation.md](0.0.0/03_lxc_readiness_and_isolation.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.0.0 / 04 | [04_technical_feasibility.md](0.0.0/04_technical_feasibility.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.0.0 / 05 | [05_baseline_gate.md](0.0.0/05_baseline_gate.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.1.0 / 01 | [01_domain_contracts.md](0.1.0/01_domain_contracts.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.1.0 / 02 | [02_sqlite_storage.md](0.1.0/02_sqlite_storage.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.1.0 / 03 | [03_permission_confirmation.md](0.1.0/03_permission_confirmation.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.1.0 / 04 | [04_transaction_executor.md](0.1.0/04_transaction_executor.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.1.0 / 05 | [05_domain_acceptance.md](0.1.0/05_domain_acceptance.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.2.0 / 01 | [01_discord_entrypoints.md](0.2.0/01_discord_entrypoints.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.2.0 / 02 | [02_fixture_catalog.md](0.2.0/02_fixture_catalog.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.2.0 / 03 | [03_playlist_commands.md](0.2.0/03_playlist_commands.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.2.0 / 04 | [04_interaction_safety.md](0.2.0/04_interaction_safety.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.2.0 / 05 | [05_structured_acceptance.md](0.2.0/05_structured_acceptance.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 0.3.0 / 01 | [01_source_decisions.md](0.3.0/01_source_decisions.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.3.0 / 02 | [02_metadata_provider.md](0.3.0/02_metadata_provider.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.3.0 / 03 | [03_dave_voice_probe.md](0.3.0/03_dave_voice_probe.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.3.0 / 04 | [04_voice_channel_policy.md](0.3.0/04_voice_channel_policy.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 0.3.0 / 05 | [05_source_voice_gate.md](0.3.0/05_source_voice_gate.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 0.4.0 / 01 | [01_playback_state_machine.md](0.4.0/01_playback_state_machine.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.4.0 / 02 | [02_queue_commands.md](0.4.0/02_queue_commands.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.4.0 / 03 | [03_playback_controls.md](0.4.0/03_playback_controls.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.4.0 / 04 | [04_core_recovery.md](0.4.0/04_core_recovery.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.4.0 / 05 | [05_playback_acceptance.md](0.4.0/05_playback_acceptance.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 0.5.0 / 01 | [01_api_contract.md](0.5.0/01_api_contract.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.5.0 / 02 | [02_model_adapter.md](0.5.0/02_model_adapter.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.5.0 / 03 | [03_request_ledger.md](0.5.0/03_request_ledger.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.5.0 / 04 | [04_deadline_cancellation.md](0.5.0/04_deadline_cancellation.md) | IN_PROGRESS | 소스 manifest 추적 | 초기 원격 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.5.0 / 05 | [05_client_acceptance.md](0.5.0/05_client_acceptance.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 0.6.0 / 01 | [01_candidates_context.md](0.6.0/01_candidates_context.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.6.0 / 02 | [02_intent_action.md](0.6.0/02_intent_action.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.6.0 / 03 | [03_conditional_stage_three.md](0.6.0/03_conditional_stage_three.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.6.0 / 04 | [04_execution_safety.md](0.6.0/04_execution_safety.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.6.0 / 05 | [05_korean_evaluation.md](0.6.0/05_korean_evaluation.md) | IN_PROGRESS | 고정 후보 d / prompt v5 | Jev API 개발37문장 37/37·명확25/25·위험계획0 | 독립held-out·지원기능 확대 인수 |
| 0.7.0 / 01 | [01_aliases_tags_and_search.md](0.7.0/01_aliases_tags_and_search.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.7.0 / 02 | [02_rule_based_playlist_generation.md](0.7.0/02_rule_based_playlist_generation.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.7.0 / 03 | [03_member_proposals.md](0.7.0/03_member_proposals.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.7.0 / 04 | [04_import_copy_and_export.md](0.7.0/04_import_copy_and_export.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.7.0 / 05 | [05_undo_restore_and_convenience_gate.md](0.7.0/05_undo_restore_and_convenience_gate.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.8.0 / 01 | [01_failure_cancellation.md](0.8.0/01_failure_cancellation.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.8.0 / 02 | [02_systemd_lifecycle.md](0.8.0/02_systemd_lifecycle.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.8.0 / 03 | [03_backup_restore.md](0.8.0/03_backup_restore.md) | IN_PROGRESS | 소스 manifest 추적 | Jev API 봇 DB·원장 격리 복원/암호화 노드밖 사본 | 주기 보존·전체 RPO/RTO·manifest 인수 |
| 0.8.0 / 04 | [04_privacy_observability.md](0.8.0/04_privacy_observability.md) | IN_PROGRESS | 소스 manifest 추적 | 부분 LXC 증거 | 전체 필수 인수·검토 후 상태 확정 |
| 0.8.0 / 05 | [05_operations_drill.md](0.8.0/05_operations_drill.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 0.9.0 / 01 | [01_release_candidate.md](0.9.0/01_release_candidate.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 0.9.0 / 02 | [02_functional_security.md](0.9.0/02_functional_security.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 0.9.0 / 03 | [03_korean_acceptance.md](0.9.0/03_korean_acceptance.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 0.9.0 / 04 | [04_performance_soak.md](0.9.0/04_performance_soak.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 0.9.0 / 05 | [05_restore_signoff.md](0.9.0/05_restore_signoff.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 1.0.0 / 01 | [01_release_manifest.md](1.0.0/01_release_manifest.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 1.0.0 / 02 | [02_help_support_contract.md](1.0.0/02_help_support_contract.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 1.0.0 / 03 | [03_staged_deployment.md](1.0.0/03_staged_deployment.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 1.0.0 / 04 | [04_postdeployment_checks.md](1.0.0/04_postdeployment_checks.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 1.0.0 / 05 | [05_release_closure.md](1.0.0/05_release_closure.md) | PLANNED | — | 미실행 | 단계 문서의 선행 조건부터 확인 |
| 1.0.1 / 01 | [01_source_contract_and_feasibility.md](1.0.1/01_source_contract_and_feasibility.md) | IN_PROGRESS | 고정 candidate manifest | [부분 실행 증거](../../evidence/public/youtube-prefix-20260928.md) | 단계별 필수 인수·실제 청취·품질/soak 전 |
| 1.0.1 / 02 | [02_youtube_resolver.md](1.0.1/02_youtube_resolver.md) | IN_PROGRESS | 고정 candidate manifest | [부분 실행 증거](../../evidence/public/youtube-prefix-20260928.md) | 단계별 필수 인수·실제 청취·품질/soak 전 |
| 1.0.1 / 03 | [03_commands_queue_and_playback.md](1.0.1/03_commands_queue_and_playback.md) | IN_PROGRESS | 고정 candidate manifest | [부분 실행 증거](../../evidence/public/youtube-prefix-20260928.md) | 단계별 필수 인수·실제 청취·품질/soak 전 |
| 1.0.1 / 04 | [04_failure_security_and_recovery.md](1.0.1/04_failure_security_and_recovery.md) | IN_PROGRESS | 고정 candidate manifest | [부분 실행 증거](../../evidence/public/youtube-prefix-20260928.md) | 단계별 필수 인수·실제 청취·품질/soak 전 |
| 1.0.1 / 05 | [05_live_acceptance_and_release.md](1.0.1/05_live_acceptance_and_release.md) | IN_PROGRESS | 고정 candidate manifest | [부분 실행 증거](../../evidence/public/youtube-prefix-20260928.md) | 단계별 필수 인수·실제 청취·품질/soak 전 |
| 1.0.2 / 01 | [01_channel_configuration_and_intents.md](1.0.2/01_channel_configuration_and_intents.md) | IN_PROGRESS | 고정 candidate manifest | [부분 실행 증거](../../evidence/public/youtube-prefix-20260928.md) | 단계별 필수 인수·실제 청취·품질/soak 전 |
| 1.0.2 / 02 | [02_prefix_router_and_lifecycle.md](1.0.2/02_prefix_router_and_lifecycle.md) | IN_PROGRESS | 고정 candidate manifest | [부분 실행 증거](../../evidence/public/youtube-prefix-20260928.md) | 단계별 필수 인수·실제 청취·품질/soak 전 |
| 1.0.2 / 03 | [03_korean_commands_and_execution.md](1.0.2/03_korean_commands_and_execution.md) | IN_PROGRESS | 고정 candidate manifest | [부분 실행 증거](../../evidence/public/youtube-prefix-20260928.md) | 단계별 필수 인수·실제 청취·품질/soak 전 |
| 1.0.2 / 04 | [04_responses_limits_and_privacy.md](1.0.2/04_responses_limits_and_privacy.md) | IN_PROGRESS | 고정 candidate manifest | [부분 실행 증거](../../evidence/public/youtube-prefix-20260928.md) | 단계별 필수 인수·실제 청취·품질/soak 전 |
| 1.0.2 / 05 | [05_acceptance_and_rollout.md](1.0.2/05_acceptance_and_rollout.md) | IN_PROGRESS | 고정 candidate manifest | [부분 실행 증거](../../evidence/public/youtube-prefix-20260928.md) | 단계별 필수 인수·실제 청취·품질/soak 전 |
| 1.0.3 / 01 | [01_commands_and_permissions.md](1.0.3/01_commands_and_permissions.md) | IN_PROGRESS | dev20260928k manifest | [자동 회귀](../../evidence/public/watch-channels-20260928.md) | 해당 W 실제 인수·이전 버전 미완료 게이트 |
| 1.0.3 / 02 | [02_storage_and_migration.md](1.0.3/02_storage_and_migration.md) | IN_PROGRESS | dev20260928k manifest | [자동 회귀](../../evidence/public/watch-channels-20260928.md) | 해당 W 실제 인수·이전 버전 미완료 게이트 |
| 1.0.3 / 03 | [03_routing_and_lifecycle.md](1.0.3/03_routing_and_lifecycle.md) | IN_PROGRESS | dev20260928k manifest | [자동 회귀](../../evidence/public/watch-channels-20260928.md) | 해당 W 실제 인수·이전 버전 미완료 게이트 |
| 1.0.3 / 04 | [04_responses_and_diagnostics.md](1.0.3/04_responses_and_diagnostics.md) | IN_PROGRESS | dev20260928k manifest | [자동 회귀](../../evidence/public/watch-channels-20260928.md) | 해당 W 실제 인수·이전 버전 미완료 게이트 |
| 1.0.3 / 05 | [05_acceptance_and_rollout.md](1.0.3/05_acceptance_and_rollout.md) | IN_PROGRESS | dev20260928k manifest | [자동 회귀](../../evidence/public/watch-channels-20260928.md) | 해당 W 실제 인수·이전 버전 미완료 게이트 |

## 저장소 사전 준비

- bot/inference 패키지 영역·초기 pyproject, shared/tests/deploy/scripts/docs/evidence와 GitHub 양식을 작성했다. 제품 코드와 원격 source 동기화 runner를 작성했다. 의존성 lock·전체 인수는 진행 중이다.
- `.gitignore`, `.gitattributes`, `.editorconfig`, README·개발/운영 안내와 Jev API·격리mock 프로필/환경/systemd 템플릿을 작성했다.
- 로컬 Git 기본 브랜치 `main`·원격 `origin`을 준비했다. 공개 파일 후보를 점검 중이며 원격 업로드는 수행하지 않았다.
- [저장소 검사](../../scripts/README.md)는 비공개 입력을 읽지 않고 파일/문서만 검사한다. LXC 제품 증거를 대신하지 않는다.

## Jev API 전용 준비와 증거

2026-09-27 사용자가 Jev API Only로 범위를 변경했다. [결정0005](../../docs/decisions/0005-jev-api-only.md)에 따라 명세1.3·11버전/55단계·시험/출시 기준을 개정했다. 로컬 모델 품질/CPU 비교·양쪽 제공자 시험은 현재 게이트가 아니다. 이전 local 실패·원장·모델·복원 기록은 보존하며 PASS로 바꾸거나 삭제하지 않는다.

| 항목 | 상태 | 검증 범위 / 남은 작업 |
| --- | --- | --- |
| 전용 계약·코드·설정 | 부분 VERIFIED | jev-api만허용·local경로거절·무모델candidate d build/install·TLS전송; 전체B매트릭스 인수전 |
| Jev API 실제 연결 | 부분 PASS | 단일판단·TLS3단계/캐시·개발37문장37/37·명확25/25·위험계획0; 최종품질/계정한도/보존정책/soak 미인수 |
| 원격 후보 제어 | IN_PROGRESS | DB/원장/예산/tombstone/TLS 유지; 전체 장애주입·동시배포 차단 인수 전 |
| LXC 회귀 | 부분 PASS | 전용설정/클라이언트·domain/backup·복합문/최소context 회귀 봇198·gateway41 PASS |
| 백업/복원 | 부분 PASS | 격리 DB·원장 복원·암호화 노드밖 사본·변조거절; 주기/보존/RPO/RTO/candidate binding 인수 전 |
| B-01~12 | IN_PROGRESS | 전용 기대동작 개정·실제TLS/계측/무모델의존성 일부검증; 전체 전건 인수 전 |

각 단계 증거에는 source/candidate/profile/config hash/run ID를 기록한다. 제공자는 Jev API 하나지만 버전의 모든 기능·안전·품질·성능·복구 증거가 있어야 VERIFIED/DONE이다. mock·개발 소규모 결과와 최종 인수를 구분한다. 기존 단계 상태를 범위 변경만으로 승격하지 않았다.

[Jev API 전용 실제 실행 보고](../../evidence/public/jev-api-only-20260928.md)를 따른다. 개발 세트 성공을 최종 품질·전체 버전 완료로 표시하지 않는다.

## 1.0.1·1.0.2 개발 후보

후속10단계는 IN_PROGRESS다. 공개 YouTube 오디오 resolver·공통 단일곡 실행·검색 선택과 지정 채널 접두어·영속 요청 원장·취소를 구현했다. Portal Intent는 사용자가 활성화했고, `일반`, `discord-bot-test`를 제한 설정에 등록했다. 실제 개발 후보와 시험 결과, 이전 대기열 우선 재생 결함·수정, 미통과 게이트는 [새 실행 증거](../../evidence/public/youtube-prefix-20260928.md)에 기록한다. 기존 1.0.0 상태와 과거 실패/성적은 보존한다. 채널 설정 변경 명령은 사용자 요청대로 [1.0.3 계획](1.0.3/README.md)으로 구체화했으며 1.0.2에서는 제공하지 않는다.

## 1.0.3 구현과 지정 LXC 검증

2026-09-28 `/주시 추가·제거·목록·켜기·끄기·점검`의 명령·권한·영속 상태·원자적 변경·미디어 승인 수명과5단계 계획을 작성했다. [결정0007](../../docs/decisions/0007-watch-channel-management.md)·W-01~20·출시 조건에 연결했다. 사용자 구현 요청으로 새5단계는 IN_PROGRESS다. 관리 명령·별도 DB 설정·출처/세대 기반 공통 실행기·선별 취소·승인 만료 큐·진단을 구현했고 봇328/gateway41 자동 회귀가 통과했다. [새 실행 기록](../../evidence/public/watch-channels-20260928.md)에 후보와 전체 실제 인수의 차이를 기록한다. 사용자 지시로 OpenJevLXC 사용을 종료했고 [결정0008](../../docs/decisions/0008-single-lxc-jev-api.md)의 한 LXC 배치로 봇k/중계l을 적용했다. 실제6명령/2채널 이관·Jev3단계/캐시를 확인하고 사용자가 목록·점검·끄기·켜기/접두어 동작을 정상으로 확인했다. 전체 W·복구·음성/장시간 인수는 계속 남아 있다. 정식 VERSION/태그/DONE은 만들지 않았다.

## 갱신 절차

실제 작업을 시작한 단계만 상태를 변경한다. 원격 실행 뒤 [증거 양식](EVIDENCE_TEMPLATE.md)을 채운 보고서 링크와 코드 revision을 기록한다. 실패·미확정 입력에는 원인, 담당 기능, 다음 확인 행동, 진행 가능한 독립 작업을 남긴다. 버전별 5단계와 버전 통과 조건이 충족되어야 버전 상태를 DONE으로 바꾼다. 0.0.0/01은 문서 계약의 검토 기록으로 REVIEWED를 사용할 수 있으며, 02~05의 필수 LXC 증거와 구분한다. 0.0.0/01은 검토 기록을 확정한 뒤 REVIEWED로 갱신한다.

[전체 로드맵](README.md) · [환경](ENVIRONMENT.md) · [시험 추적](TEST_MATRIX.md) · [출시 기준](RELEASE_CRITERIA.md)
