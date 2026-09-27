# 2026-09-28 — YouTube·접두어 개발 후보 검증

사용자 요청에 따라 1.0.1/1.0.2를 구현하고 지정 LXC 개발 봇에 적용했다. 두 버전과 각5단계는 IN_PROGRESS이며 전체 필수 인수·정식 출시·VERSION/태그·Git 업로드는 완료하지 않았다. 기존 1.0.0 범위와 과거 결과는 유지한다.

## 범위와 구현

- 실제 제공자는 Jev API Only다. API1.2·최대3dispatch·전체12초/단계4초·호출 예산·영속 request tombstone을 유지한다. gateway에는 영상·봇 DB·YouTube 키를 보내지 않는다.
- `/재생 곡:<영상 URL>`과 `/재생 검색어:<제목>`의 최대5개 공식 검색결과에서 요청자가 선택한 영상, 저장 목록의 YouTube 항목을 공통 실행기로 연결했다. 구조화 경로는 Jev0회다. 자연어의 명시 YouTube URL은 등록 목록보다 우선하는 닫힌 단일곡 후보가 된다.
- yt-dlp worker가 한 곡의 임시 HTTPS 미디어 주소를 해석하고 FFmpeg pipe로 PCM을 보낸다. 주소/헤더는 worker 메모리에만 존재한다. DNS·호스트·공인주소·redirect·FFmpeg protocol을 제한하고 쿠키/브라우저/프록시 전환/사용자 plugin·자동 업데이트를 사용하지 않는다.
- 기본 off, 유한 길이30분 이하, 준비 동시1/대기4, 총25초/해석15초/첫PCM10초, 숨은 extractor/HTTP 재시도0을 적용한다. 그룹 종료·출력 pipe 배출·wait와 강한 task 소유권을 추가했다. 중간 실패의 자동 재접속은 하지 않고 실패한 항목을 진행하며3곡 연속 실패는 정지한다.
- literal `!!창근아`·ASCII 구분자·1~500자 본문·새 일반 길드 텍스트 메시지만 접수한다. 지정 guild/channel을 먼저 확인하고 봇/웹훅/DM/스레드/공지·미호출 대화는 추론하지 않는다.
- 0004 메시지 요청 원장과 0005 항목별 재생 승인 migration을 추가했다. 원문 대신 hash·opaque request·응답 상태를 기록한다. 수정/삭제/중복·재시작·응답 유실이 새 실행을 만들지 않으며 위험 작업은 기존 확인/권한을 유지한다.
- 사용자가 Portal Message Content Intent를 켰고 `일반`, `discord-bot-test`를 선택했다. 실제 IDs는 제한 파일에만 보관한다. 사용자별 활성1·서버 사용자 cooldown2초·전체 활성/대기5, 공개 응답1개 갱신·멘션 차단을 구현했다. 설정 변경 명령은 사용자 요청대로 후속 backlog다.

## 후보 추적

현재 활성 개발 후보는 **dev20260928i**, run은 **youtube-prefix-v2-20260928**이다. 프로필은 `eval-jev-api-v5`, prompt `korean-candidates-dev-v5`, threshold0.80/margin0.10이며 gateway config SHA256은 `6e163bf85e60d2adde628bc8f5e9f342466e1385ec5597c70cb18ff7d7feadab`다. 양쪽 wheel은 아직 개발 버전 `0.0.0.dev0`이고 제품 버전 승격을 뜻하지 않는다.

| 후보 | run | source manifest SHA256 | bot wheel SHA256 | gateway wheel SHA256 |
| --- | --- | --- | --- | --- |
| dev20260928e | prefix-v1-20260928 | 060f280d9b8cd1c2fb3bf283d82e8cd5acc19cfe52dc47ab3a085a18e84a8a7d | 79a32ba949c4d1cfad45c1098982bc5577940f3b8ac99076ac4911ac70c434b0 | 1c521df8269115309b360233bc558938ba27fcae335b7a8b389307642d61fea7 |
| dev20260928f | youtube-prefix-v1-20260928 | abbddb80c539124f5f3b8ef18be00443c0803b0d88c40d5b655ae0916b387233 | ad2c6803f472bda73101bbc6fda60e25dad8b43fdb75bfc22c5d11a41dff5b6f | fa3daebac1c191b6bb743387d988d25611c21dc087f1019b16d943de5bd7e4a7 |
| dev20260928g | youtube-prefix-v2-20260928 | 42b7442d0fd4fa68592bb2052c617f198d7f81df3ee06025bef12077dc733273 | 1013d6897fd6c4dceeb3486880e24ef5632a4f35c220a8d54e92ac619b83a173 | db30e269fba935aeb742f6a1e556d81670833be93253e20cf474ed11b74ce901 |
| dev20260928h | youtube-prefix-v2-20260928 | ffc33741ee6612535132e9f730be44f05b884744c0af90902a50eab327635e05 | 6cb1c3939efbb2feb1aad37154d954d4fb5051ef733c31bca40ea2881e4cc43f | 30fc351c51677a1a8575e5488bef5432d0443bc861db53b6f81c6cc2d07481ca |
| dev20260928i | youtube-prefix-v2-20260928 | 3234c132d0d7c63bdb6cbb01447174114fbdfddeb7f2bc0e421d850eda3b51a1 | 5be5cfdbdcd14c575d3f2e0560d4a96adb60c9f6e279b043c9a8bc812e6c0d5f | fbd6ee367008be75a89a13db6c93d3c1f6cf393d8d15de4401498998a6338cd1 |

후보/이전 run DB·호출 원장·tombstone·예산·실패 보고서를 삭제하거나 덮어쓰지 않았다. g 신규 run은 f 활성 DB를 일관성 백업으로 이어받았고 h/i는 같은 run의 DB/원장/예산을 그대로 재사용했다. 제한 원장의 조회 시점별 예약 호출 수는 f run35, h 적용 직후 g/h run3, i 평가 준비 직전8이었다. i의 개발 평가111회 최대 예산 사전 산정과 남은3000회 한도 검사를 통과했다. 평가·최종 상태 확인 뒤 같은 run의 누적 예약 호출은39회였고 양쪽 서비스 active/NRestarts0·prefix ready2를 확인했다. 수정 후보 적용을 이유로 새 예산을 만들지 않았다. 기존 확인·진행 요청은 재시작 시 무효화하고 음성은 자동 재생하지 않는다. 서비스는 비root 개발 계정이며 운영 enable은 하지 않았다.

봇 LXC의 미디어 runtime은 yt-dlp2026.8.19/EJS0.8.0, Node22.23.3, Debian FFmpeg7.1.5다. g의 Node archive SHA256은 `df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de`, binary SHA256은 `fde6a4bf8d0562f7751d1a2d6cb9b417c4cfe107bbcb0aa3e9a24e125e348f48`, FFmpeg binary SHA256은 `e8a8d46f5225f3062cec7c07fb145d58ae73c603cb740dcd5bad34bfb54e455a`다. 공식 Node archive checksum을 확인하고 별도 root 관리 경로에 설치해 기존 Node20과 이전 후보를 보존했다.

## 실행 증거와 한계

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| g source 봇 회귀 | 257 PASS | 단위/DB/mock/pipeline/client; 실제 청취 아님 |
| 정지 후 동일 영상 재요청 보충 회귀 | 봇259 PASS | 기존 큐 항목 재사용·신규 요청자 승인 갱신·중복효과0 포함 |
| gateway 회귀 | 41 PASS | 원장/복원/예산; 실제 모델 품질 아님 |
| lint·타입 | PASS | bot30 source files/gateway7 source files; LXC에서만 실행 |
| f 실제 Jev 개발 평가 | 37/37·명확25/25·unsafe0 | 합성 development, 독립 held-out 아님 |
| g 지정 URL 판단 | 3/3·명확1/1·unsafe0 | 실제 Jev, 올바른 URL track.play/부정/잘못된 host; 실제 실행 없음 |
| f 첫 PCM 단일 probe | PASS·2.38초 | 실제 YouTube 해석/PCM; Discord 청취 아님 |
| g 첫 PCM 단일 probe | PASS·2.279초 | 새 Node/종료 처리·고정 wheel; Discord 청취 아님 |
| f20영상×5 첫 PCM | 93/100·p95성공3.005초·FAIL | 95% 목표 미달, 실제 Discord 전환/8시간 아님 |
| g20영상×5 첫 PCM | 93/100·p95성공4.382초·FAIL | 같은95% 목표 미달; 종료 경고 없음; f 실패 결과 보존 |
| g 적용 ready | PASS | TLS·binding·prefix ready/2채널·DB quick_check ok·메시지 요청19개 보존 |
| h 고정 wheel 결함 회귀 | PASS | 정지/미연결2상태·기존 큐 보존·지정곡 우선·새 승인·중복효과0; 격리 DB |
| h 첫 PCM | PASS·2.512초 | 고정 wheel; 실제 청취 아님 |
| h 실제 상태 | PASS | 양쪽 active/NRestarts0·prefix ready2·DB quick_check ok·원장22건/관측2채널 |
| i source 회귀 | 봇283 PASS·타입/lint PASS | 주소 형식·ID 보존·복수URL·슬래시 경로 포함 |
| i 실제 Jev 개발 평가 | 37/37·명확25/25·unsafe0 | 새 pipeline 영향 회귀; 독립 held-out 아님 |
| i 주소 형식 실제 Jev | 6/6·명확3/3·unsafe0 | 생략주소/짧은주소/이전목록 포함 링크의 action·video ID 정확; 부정/복수/잘못된 host 안전 거절 |
| i 요청 영상 첫 PCM | PASS·2.351초 | GD_rjpO7CIQ·3840bytes·고정 wheel; 실제 Discord 청취 아님 |
| i 활성화 | PASS | 동일 run/예산 재사용·TLS/binding·prefix ready2 |

bot 회귀의1경고는 Discord 의존성 내부 positional `count` deprecation이다. 잘못된 gateway 시험 경로의 첫 실행은0건으로 실패했고 올바른 경로에서41건을 실행했다. 0건 실행을 PASS로 세지 않는다. f 반복 시험에는 worker task 종료 경고가 있어 pipe 배출/회수·resolver 종료를 수정했다. g에서는 종료 경고가 재발하지 않았으나 준비 실패7건이 남아 성공률 게이트는 계속 미통과다. 실패한 영상 index는 회차마다 다르고 같은 영상의 다른 회차는 성공하여 고정 영상만 제외해 성적을 올리지 않는다. 세부 upstream 원인은 아직 분류 전이다. g와 h의 youtube_audio/youtube_worker/network_guard는 설치 파일 SHA256이 각각 같아 이 미디어 실패 결과는 h에서도 미통과 입력으로 유지한다. executor 수정만으로 미디어95% 게이트를 승격하지 않았다.

사용자에게 e의 접두어/제어를 요청했고 “확인 완료” 답변을 받았다. 당시 서버 원장과 응답에는 한 채널의 목록 조회/음성 연결만 확인되어 두 채널·전체 음성 제어 PASS로 확대하지 않았다. h 적용 후 영속 원장에는 서로 다른2채널의 입력이 관측됐다. 이는 두 채널 접수를 확인한 기록이며 각 채널의 기대 응답·음성 청취/전체 제어 인수를 대신하지 않는다. 이전 승인 시험음 청취 성공은 이전1.0.0 경로의 증거다.

f의 실제 URL 재생 요청 뒤 사용자는 “틀어줘가 들어가면 현재 선택한 재생목록만 틀어주네”라고 보고했다. 새 단일곡이 보존된 예전 대기열 뒤에 추가되어 먼저 재생되는 결함을 확인했다. g는 정지/미연결 상태의 지정곡을 앞에 두며 재생 중 추가는 대기열 추가임을 응답한다. h의 보충 수정은 정지 후 같은 영상을 다시 요청하면 기존 큐 entry를 재사용하고 요청자 승인을 갱신한다. 미디어 준비 실패를 요청곡 재생 성공으로 응답하지 않도록 현재곡을 확인한다. h 적용 후 사용자는 지정 영상이 재생된다고 확인했다. 일시정지·계속·정지 전체 성공은 새 확인 전이다. 이어 사용자는 `https://` 없는 `youtube.com/watch?v=GD_rjpO7CIQ`가 명확화 응답을 받는다고 보고했다. URL 파서와 자연어/슬래시 경로를 보완하고 대소문자·목록과의 우선순위·부정·복수URL·잘못된 host 회귀를 추가했다.

## 미통과 게이트

Y/C 전체 인수는 완료 전이다. 재생 불가 항목의 목록 미리보기·확인 후 부분추가(Y-12), 개별 장애사유 전체 분류, 실제 Discord 시작/전환100회와 사용자 청취(Y-17), 신규소스8시간·최소권한·기능off/rollback/복원(Y-18/C-18), 독립200문장·명확95%(C-17), 앞선0.9.0/1.0.0 출시 게이트와 재현 lock/manifest는 남아 있다. 개발 평가와 첫 PCM만으로 해당 게이트를 대체하지 않는다. 기술 전달 증거와 소스 운영 채택 판정은 [결정0006](../../docs/decisions/0006-youtube-and-prefix-roadmap.md)에 따라 구분한다.

원본 보고서·DB·실제 IDs·키·연결값·서비스 로그는 해당 LXC의 제한 run 경로에 보관한다. 이 문서는 검토한 공개 요약만 포함한다. [진행 현황](../../Plans/0.DevPhase/STATUS.md)·[원격 절차](../../docs/REMOTE_DEVELOPMENT.md)·[후속 시험](../../Plans/0.DevPhase/TEST_MATRIX.md)을 따른다.

## 주소 형식 보충 회귀

새 주소 형식 수정은 봇283건 PASS·mypy30파일·lint PASS다. `youtube.com/watch`, `www/m.youtube.com`, `youtu.be`, Shorts/embed의 scheme 생략을 지원하고 실제 fetch는 안정 video ID에서 고정 HTTPS 주소만 만든다. 명시 HTTP·다른 host·인증/port·잘못된 IPv6 주소는 파서가 거절한다. 영상ID 대소문자를 보존한다. 여러 영상 URL이면 기존 저장 목록으로 fallback하지 않고 명확화한다.
