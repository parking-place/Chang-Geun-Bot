# 원격 개발과 Jev API 전용 실행

2026-09-28 현재 개발 구성은 [결정0008](decisions/0008-single-lxc-jev-api.md)과 [환경 계약](../Plans/0.DevPhase/ENVIRONMENT.md)을 따른다. 제품 실행은 DiscordBotLXC에서만 수행한다. OpenJevLXC에 새 작업을 수행하지 않는다. 로컬은 파일/Git/stdlib 원격 제어와 저장소 검사만 처리한다. `.private/lxc-ssh.conf`는0600이며 공개 소스 동기화에서 제외한다.

## 현재 적용 상태

현재 개발 봇 `recon120p12jbot`(v2/LLM disabled)과 중계 `recon120p12egw`(v2/LLM disabled)를 테스트 서버에 적용했다. 봇 run은 `recon120p12j-20260928`, 중계 epoch는 보존한 `single-lxc-20260928`, 프로필은 `eval-jev-api-single-lxc-v1`이다. [1.2.0 실행 기록](../evidence/public/reconstruction-120-progress.md)과 [기존 사용자 부분 인수](../evidence/public/watch-channels-20260928.md)를 구분한다. 실제 자연어 사용자 인수·전체 출시 게이트는 미완료이며 정식 VERSION/태그는 만들지 않았다.

1.1.8의 [이전 `patch118a` 봇 wheel](../evidence/public/patch-118-development-20260928.md)은 격리 후보로 남겨 둔다. 현재 활성 `p12j` 후보는 LXC source/설치 wheel 각각496회귀를 통과했다. 공유 Jev 예약 마지막 확인 값은651/3000, GPT 예약/실제는2005/521 micro USD이며 다음 평가 전 재조회한다. GPT 키의 임시 LXC 사본은 제거했고 gateway는 disabled다.

`changgeun-dev-bot.service`는 봇 계정, `changgeun-jev-api.service`는 별도 `changgeun-gateway` 계정으로 실행한다. 중계는 loopback TLS8443만 받는다. 외부 API 키를 봇 계정에 제공하지 않는다. 두 개발 unit은 자동 부팅 시작으로 활성화하지 않았다.

## 상태·실제 전송·계약 회귀

```bash
python3 scripts/test_profile.py --ssh-config .private/lxc-ssh.conf --profile jev-api --suite status
python3 scripts/test_profile.py --ssh-config .private/lxc-ssh.conf --profile jev-api --suite transport
python3 scripts/test_profile.py --ssh-config .private/lxc-ssh.conf --profile mock --suite contract
```

`status`는 활성 서비스·설정 binding·내부 TLS/인증을 확인하고 유료 판단을 호출하지 않는다. `transport`는 최대3회 실제 합성 dispatch와 캐시 재사용을 시험하며 한국어 품질/성능 인수가 아니다. 내부 forward는 null/unavailable이다.

`contract`는 현재 봇/중계의 각각 설치된 wheel 경로를 선택해 동일 LXC에서 회귀를 실행한다. 소스 동기화는 실행 wheel을 바꾸지 않는다. `mock` 선택은 시험 표시이며 실제 Discord 제공자를 변경하지 않는다. `--dry-run`은 원격 실행/접속이 없는 계획 출력이다. 제품 PASS 증거가 아니다.

## 후보 소스와 wheel 준비

```bash
python3 scripts/remote.py --ssh-config .private/lxc-ssh.conf --host DiscordBotLXC --sync
```

공개 소스는 `/opt/changgeun-dev/source`에 전달하고 SHA256 manifest를 기록한다. `.private`·키·DB·원장·환경·로그·백업은 제외하며 목적지 삭제 동기화는 하지 않는다. 준비 도구는 build 전/후 manifest drift를 거절하고 새 이름에만 wheel/runtime/의존성 제약·바이너리 hash를 기록한다. 기존 후보는 덮어쓰지 않는다.

현재 준비한k/l은 재생성하지 않는다. 다음은 **새 이름에 사용하는** LXC 준비 형식이다. `NEW_BOT`/`NEW_GATEWAY`는 실제 새 이름으로 바꿔 지정 배포 계정에서 실행한다.

```bash
python3 /opt/changgeun-dev/source/scripts/prepare_candidate.py --candidate NEW_BOT --component bot --youtube-audio --youtube-runtime /opt/changgeun-dev/runtimes/node-v22.23.3-linux-x64/bin/node
python3 /opt/changgeun-dev/source/scripts/prepare_candidate.py --candidate NEW_GATEWAY --component gateway
```

미디어 의존성은 봇만 설치한다. 고정 Node22.23.3·yt-dlp2026.8.19/EJS0.8.0·FFmpeg7.1.5 핀과 checksum을 후보 manifest에서 검증한다. 중계에는 torch/transformers/OpenJev/가중치를 설치하지 않는다.

## 봇 후보 전환

현재 봇 전환 도구는 준비된 한 LXC 중계·프로필과 제한 binding을 사용한다. `NEW_BOT`, `NEW_RUN`은 준비한 새 후보/run으로 바꾼다. 동시에 여러 전환을 실행하지 않는다. 이전 `test_profile.py --suite activate` 경로는 v1이며, v2 전환에는 명시적 `--parser-v2`를 사용한다.

```bash
python3 scripts/test_profile.py --ssh-config .private/lxc-ssh.conf --profile jev-api --config-id eval-jev-api-single-lxc-v1 --suite activate --candidate NEW_BOT --run-id NEW_RUN --prefix-channels --youtube-audio
python3 scripts/deploy_watch_candidate.py --ssh-config .private/lxc-ssh.conf --candidate NEW_V2_BOT --run-id NEW_V2_RUN --parser-v2
```

첫 명령은 `deploy_watch_candidate.py`의 봇 전용 v1 전환을 호출한다. 둘째 명령은 gateway가 v2/LLM disabled일 때만 새 parser와 private trace를 켠다. 새 bot-config/unit 준비 → 중계 TLS readiness → 기존 봇 정지 → 기존 DB의 일관성 복사 → 새 봇 시작 순서다. 중계 원장/예산은 변경하지 않는다. 실패 시 이전 unit 복구를 구현했으며 전체 장애 주입 인수는 남아 있다. 전환은 현재곡을 중단하며 새 시작에서 자동 음성 입장/재생은 하지 않는다. 전환 후 새 DB에 변경이 생긴 경우 구 DB로 단순 복귀하면 변경이 누락되므로, 실제 rollback 전에는 변경분 보존/이관을 별도 검증한다.

이전 run/DB/바이너리를 보존한다. migration6 DB를 이전 바이너리에 연결하지 않으며 rollback은 이전 DB/바이너리 묶음을 사용한다. 새 DB/주시 설정/감사도 보존한다. 일반 슬래시/멘션 허용 채널은 기존 활성 설정에서 이어받으며 prefix 주시 등록으로 확장하지 않는다.

`--prefix-channels` 초기 목록은 제한 `prefix-channels.json`에서 읽고 실제 서버/권한 검증 뒤 최초1회 DB 이관한다. 이후 DB가 기준이다. 빈 목록/꺼짐을 예전 파일로 되살리지 않는다. 사용자는 Portal Message Content Intent를 켰고 초기 두 채널을 지정했다.

## 한 LXC 중계와 보존

`install_single_lxc_gateway.py`는 지정 LXC 배포 계정에서 stdin의 제한 JSON 입력으로 새 중계 계정·loopback TLS·고정 epoch/profile·root 소유 unit을 준비하는 개발 도구다. hosted 키는 argv/공개 파일에 넣지 않는다. 이미 존재하는 immutable 파일은 동일한 경우만 허용하며 run/원장을 지우거나 예산을 재설정하지 않는다. 봇 전환에서 이 도구를 반복 호출하지 않는다.

현재 중계 상태는 `/var/lib/changgeun-jev-api`, 역사 백업은 별도 `/var/lib/changgeun-dev/gateway-history-20260928`에 보존했다. offline 이전 서버 원본은 수정하지 않았고 과거 인증 복원 백업을 최신 전체 원장이라고 표시하지 않는다. 해당 백업 tombstone을 이어받고 새 token/profile/binding/epoch로 실행한다. 계정 전체의 과거 누계/비용은 unknown이다.

## 개발 평가와 읽기 전용 Discord 점검

```bash
python3 scripts/test_profile.py --ssh-config .private/lxc-ssh.conf --profile jev-api --suite korean-eval
```

`korean-eval`은 개발37문장 전용이다. 프로필/목적/config hash·고정 원장·잔여예산≥문장수×3을 사전 확인한다. 격리 음악 DB와 합성 actor를 사용하며 Discord 변경/음성은 실행하지 않는다. 결과는 새 제한 파일에 기록한다. 이전 개발 성적을 새 epoch나 최종 독립200문장·8시간 인수의 PASS로 복사하지 않는다.

정상 기동 뒤 봇 LXC의 후보 Python으로 `scripts/probe_watch.py --config <제한-config-경로> --token-env <제한-bot.env-경로>`를 실행해 실제 관리6명령·Manage Guild 기본 권한·DB 이관·prefix 준비를 읽기 전용으로 확인한다. 사람의 명령 조작/청취를 대신하지 않는다.

`probe_youtube_audio.py`/`probe_media_evaluation.py`는 첫 PCM 검증이며 실제 Discord 청취·제어·100회 전환·8시간 시험을 대신하지 않는다. 보고서를 덮어쓰지 않는다. 과거 두 서버 절차/실패 기록은 [초기 실행](../evidence/public/execution-20260927.md)·[전용 전환](../evidence/public/jev-api-only-20260928.md)·[YouTube/접두어](../evidence/public/youtube-prefix-20260928.md)에 당시 증거로 보존한다.

[운영 안내](OPERATIONS.md) · [프로필 계약](../Plans/0.DevPhase/INFERENCE_PROFILES.md) · [진행 상태](../Plans/0.DevPhase/STATUS.md)
