# Jev API 전용 프로필·실행 계약

현재 기준: [명세 1.3](../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md), [사용자 결정 0005](../../docs/decisions/0005-jev-api-only.md). 실제 제공자는 `jev-api`만 지원한다. 2026-09-28부터 [결정0008](../../docs/decisions/0008-single-lxc-jev-api.md)에 따라 봇과 별도 계정의 중계가 DiscordBotLXC에서 실행된다. OpenJevLXC에는 새 작업을 수행하지 않는다.

## 지원 구성

| 프로필 | 사용 | 준비·출시 범위 |
| --- | --- | --- |
| `jev-api` | 봇 → 내부 TLS 게이트웨이 → 공식 Jev API | 실제 자연어·품질·성능·장시간 인수 대상 |
| `mock` | 지정 LXC의 고정 응답·오류 주입 | 명시 test mode 전용; 실제 Discord 활성화 금지 |

로컬 제공자·모델 설정·snapshot 인자는 시작 전에 거절한다. torch/transformers/OpenJev 설치·모델 다운로드·GPU·CPU 모델 예열은 필요하지 않다. 다른 제공자로 fallback하거나 키 유무에 따라 제공자를 고르지 않는다.

## 계측·안전

- API schema1.2·provider/profile_id/config_hash·prompt/threshold는 요청 전체에 고정한다. 등록 후보만 선택하고 실행·권한 판단은 봇이 한다.
- 최대3단계·3질문·3 provider dispatch, 단계당1질문/1dispatch. 전체12초·단계 `min(4초, 잔여시간)`, 조건부3단계 시작 잔여≥1초. 조기 종료와 늦은 결과 폐기를 유지한다.
- `usage.provider_calls`는 단계별 신규 전송0~1, `request_provider_calls_total`은 원장 누계≤3이다. 캐시 재사용·진행 합류는 신규0이며 누계는 보존한다.
- `forward_passes`·`request_forward_passes_total`은 null, source=unavailable이다. 호출 수를 실제 forward로 표시하지 않는다. 미공개 model revision도 null/source=unavailable이며 반환 모델/API·adapter·측정 시각을 기록한다.
- dispatch 전에 영속 원장에 예산을 원자 예약한다. 오류·응답 유실·취소·재시작 불명은 예약을 환불하지 않고 재전송하지 않는다. 이전 request ID 소유권 tombstone은 복원·후보 변경에도 유지한다.
- 게이트웨이 worker1·활성dispatch1·대기최대4, 무료 authenticated health. 외부 계산 중단·내부 forward 수는 보장하지 않는다.

## 키·전송·호출 한도

내부 `JEV_API_TOKEN`과 외부 `JEV_HOSTED_API_KEY`를 분리한다. 외부 키는 DiscordBotLXC의 root0600 환경 파일에서 systemd가 중계 계정에만 제공한다. 봇 계정은 읽을 수 없다. 내부 전송은 loopback TLS다. 공식 고정 HTTPS endpoint·인증서 검증·redirect0·HTTP retry0·환경 proxy 미사용을 적용한다. 실제 Discord ID·권한·전체 대화·DB·키를 전송하지 않으며 필요한 요청 텍스트와 익명 후보만 전송한다.

smoke 프로필의 한도는20 dispatch다. 명시 `eval-` 프로필과 development-evaluation/release-evaluation 목적만 최대3000을 허용한다. 한도·목적을 config hash에 포함하고 예상 최대 단계·준비 호출이 남은 예산을 넘으면 평가를 시작하지 않는다. 새 run 반복 생성이나 원장 삭제로 예산을 초기화하지 않는다. 계정 한도·실제 비용·보존 정책은 확인한 값과 unknown을 구분한다.

## 후보 변경·복원

[현재 도구](../../docs/REMOTE_DEVELOPMENT.md)의 `activate`는 준비된 동일 LXC 중계를 유지하고 봇만 전환한다. 사전 TLS readiness → 봇 정지 → 이전 DB 복사/새 후보 시작 순서이며 고정 중계 원장/예산을 바꾸지 않는다. 중계 runtime 변경은 별도 명시 준비/검증을 요구한다. 설정/의존성 변경은 고정 config hash·candidate manifest와 영향 시험을 요구한다. 같은 run의 DB·원장·남은 예산은 재사용하고 확인 토큰/음성 실행 세대는 재시작 시 무효화한다. 자동 음성 재접속·재생은 하지 않는다. rollback은 이전 unit과 데이터/예산 소유권을 보존한다.

현재 프로필은 `eval-jev-api-single-lxc-v1`, 고정 중계 epoch는 `single-lxc-20260928`이다. 원장/호출 한도는3000으로 유지하며 재시작 때 새 epoch를 만들지 않는다. 이전 offline 원본과 별도 복원한 역사 백업을 보존했다. 최신 과거 원장 전체 이관·계정 전체 과거 누계는 확인되지 않았다. 새 프로필/token/binding은 이전 실행과 분리하며 과거 예산을 덮어쓰지 않는다.

## 버전별 게이트

| 버전 | 책임 |
| --- | --- |
| 0.0.0 | Jev API 연결·DAVE/승인 소스 타당성·LXC 격리·원격 실행 추적 |
| 0.1.0~0.4.0 | 제공자 없이 도메인·구조화·SQLite·재생 인수; mock/실제 구분 |
| 0.5.0 | Jev API 단일 전송·API1.2·원장·기한·오류·인증/클라이언트 |
| 0.6.0 | 한국어 개발 세트·지원 구문·안전 N 회귀·prompt/threshold 보정 |
| 0.7.0 | 조건부 목록·제안·가져오기·undo와 권한/확인 회귀 |
| 0.8.0 | 비root 서비스·전송/키·암호화 백업/복원·장애/후보 rollback |
| 0.9.0 | 독립 held-out≥200·명확한 요청≥95%·경로별≥100·실제음성≥8시간 |
| 1.0.0 | 같은 고정 Jev API 후보의 manifest·배포·smoke·지원/복구 인수 |
| [1.0.1](1.0.1/README.md) | 미디어는 봇 LXC에서 처리; 구조화 재생은 판단0회, Jev 장애와 기존 재생 분리 |
| [1.0.2](1.0.2/README.md) | 지정 채널/접두어 사전 필터·메시지 중복 원장·최소 한국어 본문·동일3회/기한 인수 |
| [1.0.3](1.0.3/README.md) | 주시 설정6명령은 Jev0회·provider 불필요; 제거/끄기의 취소/늦은 결과·원장/예산 보존 |

실제·mock·개발·held-out·과거 로컬 결과는 합산하지 않는다. [B-01~12](TEST_MATRIX.md)의 ID는 유지하되 기대 동작은 전용 범위로 개정했다. 필수 기능·보안·품질·성능·복구가 미실행/실패이면 해당 버전 전체 DONE을 선언하지 않는다.
