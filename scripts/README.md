# 저장소·원격 개발 도구

`check_repository.py`는 Git 후보·ignore·공개 비밀값 패턴·Markdown 링크·TOML/JSON만 검사한다. 제품 import나 실행을 하지 않으며 로컬과 저장소 CI에서 실행할 수 있다.

```bash
python3 scripts/check_repository.py
```

| 도구 | 실행 위치와 역할 |
| --- | --- |
| `remote.py` | 로컬 제어; 공개 소스/manifest 전달과 명시 LXC 명령 실행 |
| `test_profile.py` | 로컬 제어; Jev API 고정·봇 전용 후보 배포·상태·실제 전송·계약 회귀 |
| `deploy_watch_candidate.py` | 로컬 stdlib 제어; 한 LXC 중계/예산을 유지하며 봇만 전환 |
| `install_single_lxc_gateway.py` | DiscordBotLXC 배포 계정; 별도 중계 계정·loopback TLS·고정 epoch/예산 준비, 제한 stdin 입력 |
| `switch_single_lxc_gateway.py` | DiscordBotLXC root; 중계 wheel만 교체하고 동일 프로필·원장·예산·TLS binding 확인, 실패 시 이전 unit 자동 복귀 |
| `probe_watch.py` | DiscordBotLXC; 실제6명령/기본 권한·DB 이관·prefix 상태 읽기 전용 검사 |
| `profile_control.py` | 지정 LXC 배포 계정; 제한 설정·run별 DB/원장·tombstone·이전 unit 복구 |
| `prepare_candidate.py` | 지정 LXC 배포 계정; 고정 wheel과 분리 runtime 준비·의존성 검사 |
| `probe_inference.py` | DiscordBotLXC; 별도 원장의 단일 합성 실제 판단 |
| `probe_transport.py` | DiscordBotLXC; 실제 TLS 3단계·계측·캐시; 음악 DB 변경 없음 |
| `probe_pipeline.py` | DiscordBotLXC; 격리 DB의 개발 3문장/명시 dataset·단계별 선택 결과; held-out 인수 아님 |
| `probe_youtube.py` | DiscordBotLXC; 공식 검색·길이·사용자 목록 페이지 조회; 키/URL 출력 없음 |
| `probe_youtube_audio.py` | DiscordBotLXC; 실제 영상 첫 PCM·정리만 검사, Discord 청취 인수 아님 |
| `probe_media_evaluation.py` | DiscordBotLXC; 공개20영상×5 첫 PCM, 임시 URL/미디어 저장 없음; 실제 음성/soak 아님 |
| `probe_import.py` | DiscordBotLXC; 실제 조회 snapshot을 격리 DB에서 확인·import/export·순서 회귀 |
| `backup_crypto.py` | 지정 LXC 배포 계정; RSA recovery key·CMS AES256-GCM 암호화/인증 복호화 |
| `backup_runtime.py` | 지정 LXC; Online Backup API·checksum/binding·새 경로 복원·요청 무효화 |
| `export_schemas.py` | DiscordBotLXC; 엄격 계약에서 공개 API 1.2 JSON Schema 생성 |
| `probe_discord.py` | DiscordBotLXC; DAVE 시험음 전송·퇴장; 사람의 청취 인수와 구분 |
| `seed_fixture.py` | DiscordBotLXC; 실제 DJ 역할 확인 후 승인 합성 음원 fixture 등록 |

현재 제품 실행은 DiscordBotLXC만 사용하며 OpenJevLXC에 새 작업을 수행하지 않는다. [배치 결정](../docs/decisions/0008-single-lxc-jev-api.md)을 따른다.

지원하는 `test_profile.py` suite는 `contract`, `activate`, `status`, `transport`, `korean-eval`이다. 실제 프로필은 `jev-api`, 격리 회귀용은 `mock`이며 mock을 실제 Discord 서비스로 활성화하지 않는다. `transport`는 실제 판단 최대 3회를 사용한다. `status`와 `--dry-run`은 유료 판단을 호출하지 않는다. `korean-eval`은 명시 eval 목적/남은 예산을 검사한 개발37문장 전용이다. 최종held-out·soak·주기 운영백업 runner는 아직 인수 전이다.

[검증한 사용법](../docs/REMOTE_DEVELOPMENT.md) · [증거](../evidence/public/execution-20260927.md) · [원격 루프 계획](../Plans/0.DevPhase/0.0.0/02_repository_and_remote_workflow.md)
