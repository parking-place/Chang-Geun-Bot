# 1.0.3 주시 채널 관리 구현·검증

- 날짜: 2026-09-28
- 범위: 사용자 요청한 1.0.3 구현과 GitHub 업로드. 정식 출시 VERSION/태그/DONE은 만들지 않는다.
- 상태: **개발 봇 적용·LXC 자동 회귀 PASS / 관리 동작 사용자 부분 인수 PASS**. 전체 W 인수·정식 출시는 미완료다.

## 구현

`/주시 추가·제거·목록·켜기·끄기·점검`을 guild 전용 Manage Guild 기본 권한 그룹으로 구현했다. 실행·확인·페이지/자동완성에서 최신 소유자/서버 관리 권한과 호출 위치를 확인하며 모든 관리 응답은 개인 응답이다. DJ 단독 권한은 관리 권한이 아니다. 관리 명령은 Jev에 연결하지 않는다.

추가는 생략 시 현재 채널, 점검은 생략 시 등록 목록 전체다. 제거는 저장된 목록 자동완성/ID/정확한 멘션으로 삭제된 항목도 처리한다. 제거/끄기는 요청자에게60초 확인을 받으며 기대 revision이 바뀌면 다시 요청해야 한다. 중복/no-op은 revision과 진행 요청을 바꾸지 않는다. 예상 영향과 실제 취소 수를 구분한다. 서버당20채널, 페이지10채널, 관리자 사용자2초 간격, 점검 동시1개/서버·네트워크 작업 최대4개·명령 처리15초를 적용했다.

`0006_watch_channels.sql`은 기존0001~0005를 변경하지 않는 additive migration이다. 초기 제한 목록은 실제 guild/일반 텍스트/봇 권한을 검증한 뒤1회 이관한다. 이관 실패에서는 변경을 막고 목록/점검만 가능하다. DB의 빈 목록/꺼짐을 옛 파일로 되살리지 않는다. 주시 설정은 일반 settings JSON과 별도이며 감사90일·기존 요청/중복 식별·세대 tombstone을 보존한다.

일반 슬래시/멘션 정책과 prefix 정책을 분리했다. 신규 prefix 권한은 `request_sources`와 메시지 원장에 결합한 서버 기록으로만 인정한다. origin 문자열 자체로 우회할 수 없다. 최초/후속 판단·확인·자식 등록·DB 커밋·미디어 준비/실제 `voice.play`에서 최신 세대/승인을 재검사한다. 설정 변경과 실제 음성 시작은 await 없는 SQLite 쓰기 트랜잭션 경계로 직렬화한다.

제거/끄기/채널 권한 상실은 해당 출처만 취소한다. 이미 시작한 현재곡/같은 스트림의 일시정지·계속은 유지한다. 아직 시작하지 않은 곡은 순서와 함께 `승인 만료`로 남고 자동 다음곡에서 제외한다. 만료를 미디어 오류로 세지 않으며 새 DJ의 명시 재생으로 기존 항목을 재승인한다. 재등록/켜기는 옛 승인·확인을 살리지 않는다. Gateway 연결 해제는 이전 prefix 세대를 무효화하고 재연결 후 새 요청을 받는다.

진단은 채널별 권한 부족을 결과로 표시하며 설정/메시지를 바꾸지 않는다. 한 채널 실패는 다른 정상 채널을 막지 않는다. 운영자 기능 허용과 DB의 켜짐, Gateway 준비를 구분한다. Portal 상태를 직접 읽거나 바꾼다고 주장하지 않는다.

## 지정 LXC 자동 검증

| 실행 | 결과 | 한계 |
| --- | --- | --- |
| DiscordBotLXC 소스 회귀 | **328 PASS** | 단위/SQLite/mock 어댑터·합성 actor; 실제 사용자 조작/청취 아님 |
| DiscordBotLXC 고정 wheel 회귀 | **328 PASS** | 아래 k의 설치 패키지로 같은 회귀; source import 대신 후보 사용 |
| 신규 `test_watch.py` | **45 PASS** | 위328에 포함; 별도 추가 합산하지 않음 |
| DiscordBotLXC 설치 gateway 회귀 | **41 PASS** | 아래l의 설치 패키지로 격리 mock/원장/복원/예산; 유료 판단0 |
| bot mypy | **32 소스 파일 PASS** | 정적 타입 검사 |
| bot/tests/scripts ruff | **PASS** | 지정 LXC 실행 |

경합100회는 두 스레드의 격리 DB 설정 제거/명령 커밋 순서를 대조했다. 실제 Discord100회 부하가 아니다. 음성 준비 전·후·`voice.play` 직전 무효화는 mock voice/resolver로 검증했다. 설치 wheel에서 기존 명령·YouTube 주소·권한·큐·백업 회귀도 함께 실행했다. Discord 내부 `re.sub` 인자 사용의 DeprecationWarning6건은 남아 있으며 기능 실패는0건이다.

## W 추적

| 범위 | 이번 부분 증거 | 남은 전체 인수 |
| --- | --- | --- |
| W-01~04 | 실제6명령 등록/기본 권한·사용자 목록/점검·개인 응답·미등록 위치 관리·최신 권한·확인/유형·삭제 항목 제거 | 실제 서버의 노출/선택/역할 조합 |
| W-05~08 | 최초 이관/재시작/빈 목록·CAS/동시 관리자/no-op/재전송·커밋 실패 원자성·guild/20채널·기존 SQL/승인 출처 | 실제 후보 교체/고장 주입 전체 |
| W-09~12 | 원장 기반 동적 prefix·가짜 origin/ID 차단·늦은 Jev 결과·자식/확인 차단·준비/시작 경합·현재곡/반복/다른 출처 | 실제 채널 삭제/권한 이벤트·Gateway 재연결·실제 음성 |
| W-13~16 | 예상/실제 영향·확인 도중 추가 요청·만료/충돌 버튼·진단 생략/권한 부족·운영자off·cooldown | 실제11~20채널 페이지/403/429/Intent 장애·보존 만료 전체 |
| W-17~20 | 설치 wheel·100회 합성 경합·기존 회귀·실제 적용/2채널 이관·사용자 끄기/켜기/접두어 부분 인수 | 실제 주시2/미주시1·관리6명령·청취·재시작·별도 복원/이전 묶음 rollback·장시간 |

모든 W의 전체 조건이 PASS라는 뜻은 아니다. 앞선 Y/C/품질200문장·미디어95%·8시간 등 미완료 출시 게이트도 유지한다.

## 고정 후보와 실제 적용

- 봇 candidate: **dev20260928k**, 개발 wheel 버전`0.0.0.dev0`.
- source manifest SHA256: `28dacf27e04a4b469442a230358ed8fef626c8d622f30e9ccb33d71fb9090809`.
- bot wheel SHA256: `bc54aeea8b1887b67fe041a60348ebc897564ed2504403b9097ccc4fe9d83b37`.
- gateway candidate: **dev20260928l**.
- gateway source manifest SHA256: `c2c485b6032ae4f91c0d826d9f3199e0537a595fc0ec06366fa8709437e207e7`.
- gateway wheel SHA256: `2d62abd5715f29706a7c66c0d071a375ac51c06a9244cacaa52e6c3b030dcd9e`.
- 프로필: `eval-jev-api-single-lxc-v1` / prompt `korean-candidates-dev-v5`, confidence0.8/margin0.1.
- gateway config hash: `0896e404d95e2cedb05656e517615197459073b2154b03226b9deaac2d33253d`.
- 활성 봇 run: `watch-single-lxc-v1-20260928`; 중계 epoch: `single-lxc-20260928`.
- Node22.23.3·yt-dlp2026.8.19·EJS0.8.0·FFmpeg7.1.5은 이전 검증 핀을 유지했다.
- `prepare_candidate.py`는 build 전/후 모든 source manifest 해시를 대조하고 변경된 소스를 거절한다.
- 앞서 만든j 후보는 포맷 후 manifest 재동기화 전 준비돼 적용하지 않았다. 폐기/덮어쓰기 없이 기록을 보존하고 k를 새로 만들었다.

전환 전 실제 봇 DB를 읽어 큐32항목·출처를 입증할 수 없는 기존 admission0건·기존 일반 명령 채널2개를 확인했다. 새 설정에도 기존 일반 슬래시/멘션 정책을 유지하며 동적 주시 등록으로 이를 확장하지 않는다. 출처 입증이 안 되는 다른 데이터는 migration의 `legacy_unknown`으로 보존하고 새 DJ 승인을 요구한다.

### 현재 한 LXC 배치

최초 준비 `watch-v1-20260928`은 이전 중계 TLS readiness가 실패해 기존 봇을 정지하지 않았다. 이후 사용자는 OpenJevLXC를 더 이상 사용하지 않는다고 명시했다. [결정0008](../../docs/decisions/0008-single-lxc-jev-api.md)에 따라 별도 계정의 hosted Jev API 중계를 DiscordBotLXC에 준비했고, 새 readiness 통과 뒤 봇k를 적용했다. 이전 서버의 연결 복구를 현재 적용 조건으로 남기지 않는다.

중계 unit은 `changgeun-jev-api.service`, 계정은 `changgeun-gateway`, loopback TLS8443만 수신한다. 봇 unit은 `changgeun-dev-bot.service`/`changgeun-dev`다. hosted 키는 root0600 환경 파일을 systemd가 중계에만 제공하고 **봇 계정의 키 파일 읽기 거절을 실제 확인**했다. 내부 토큰은 별도다. 메모리 상한은 봇900MiB/중계384MiB이며 개발 unit은 부팅 자동 시작으로 활성화하지 않았다. 새 개발 인증서는30일 유효다. 인증서 갱신/운영 PKI·privileged 잔여 위험은 출시 인수 전이다.

offline 이전 서버의 원본 DB·원장·예산·서비스·후보를 수정하거나 삭제하지 않았다. 인증된 역사 암호화 백업을 별도 경로에 복원했고3개 보존 파일과 tombstone을 이어받았다. **최신 이전 원장 전체 이관은 확인되지 않았다.** 새 프로필/hash/token/고정 epoch는 과거 run과 분리하며 이전 예산을 덮어쓰지 않는다. 개발 한도3000 dispatch의 새 영속 원장은 재시작·봇 전환 때 재생성하지 않는다. 계정 전체 과거 누계/비용은 unknown이며 한도 우회를 위한 새 run 반복/원장 삭제는 금지한다.

중계와 봇의 배포 사전 상태/TLS binding을 통과한 후 stopped 이전 bot DB를 새 run에 일관성 복사했다. 기존 DB/바이너리·초기 실패 준비 경로는 보존했다. 이전 바이너리에는 이전 DB 묶음을 사용하고 migration6 DB를 연결하지 않는다. 전체 장애 주입/rollback 인수는 미완료다.

### 실제 서비스·Discord·Jev 검증

| 검증 | 결과 | 범위 |
| --- | --- | --- |
| 실제 Discord 관리 명령 | **PASS** | `/주시`에 추가·제거·목록·켜기·끄기·점검6개, Manage Guild 기본 권한 확인 |
| DB 초기 이관/입력 준비 | **PASS** | 등록2/켜짐/seed_applied/ready, 출처 불명 기존 승인0, 검사 시 진행 요청0 |
| 실제 새 중계 TLS/hosted API | **PASS** | 합성3단계3dispatch, 단계458/259/264ms; 단일 전송 측정이며 성능 benchmark 아님 |
| 같은 요청 캐시 재사용 | **PASS** | 신규 paid dispatch 없이 캐시 재사용; 내부 forward는 null/unavailable |
| 현재 `test_profile status` | **READY** | 새 프로필/hash/TLS와 서비스 확인, provider 호출0 |
| 현재 `test_profile contract` | **328 + 41 PASS** | 같은 LXC에서 설치 봇k/중계l 각각 선택, 실제 제공자 품질 시험 아님 |

사용자 시험 후 읽기 전용 재확인에서는 등록1/켜짐/seed_applied/ready를 확인했다. 최초 이관2와 다른 시점의 저장 상태이며 사용자가 바꾼 DB 값을 초기 파일로 덮어쓰지 않았다.

위 읽기 전용 명령 등록/DB probe는 설정을 변경하거나 Jev를 호출하지 않았다. 관리 명령 자체도 판단0회다. 실제 사용자 prefix 명령의 hosted 판단은 별도 영속 예산에 기록된다. 설치 wheel의 build manifest와 이후 배포 도구/문서 수정의 Git 소스를 구분한다. 도구/문서 동기화가 실행 wheel을 바꾸지는 않는다.

최종 상태 재확인에서 봇/중계 unit은 모두 active/running이었다. 중계 고정 원장의 예약 호출은4/3000이었다. 이는 해당 시각 새 epoch의 snapshot이며 과거 계정 전체 호출 수가 아니다.

### 사용자 부분 인수

2026-09-28 사용자에게 `/주시 목록`·`/주시 점검` → `/주시 끄기` 확인 버튼 → `!!창근아 목록 보여줘`에 무응답 → `/주시 켜기` → 다시 목록 요청에 응답하는 시험을 요청했고 사용자는 **“정상”**으로 확인했다. 이 요청한 범위의 사용자 인수를 PASS로 기록한다.

추가/제거·20채널/페이지·미주시 채널·권한 회수/삭제·재시작/rollback·현재곡 보존·실제 음성·장시간 전체 시험을 이 답변으로 완료 처리하지 않는다. 이전 후보의 청취/YouTube 결과도 이번 후보의 전체 인수로 합산하지 않는다. W 전체와 이전 미완료 게이트는 계속 IN_PROGRESS다.

## 공식 계약

기본 명령 노출 권한과 실제 앱 권한 검사를 함께 사용한다. `default_permissions`는 앱의 실행 검사를 대신하지 않는다. [discord.py Group](https://discordpy.readthedocs.io/en/stable/interactions/api.html#discord.app_commands.Group), [Discord Application Commands](https://docs.discord.com/developers/interactions/application-commands)를2026-09-28 확인했다.

비공개 인증값·실제 서버/채널/사용자 ID·주소·원문·DB/원장·signed media URL은 이 공개 보고서에 넣지 않는다.
