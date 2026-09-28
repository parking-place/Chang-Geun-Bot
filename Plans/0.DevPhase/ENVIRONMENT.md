# 개발·검증 환경 계약

현재 배치는 2026-09-28 사용자 지시를 기록한 [결정0008](../../docs/decisions/0008-single-lxc-jev-api.md)이 우선한다. 자연어 판단은 [Jev API Only](../../docs/decisions/0005-jev-api-only.md)다. OpenJevLXC 사용을 종료하며 새 접속·시험·서비스 변경을 수행하지 않는다. 비공개 연결값은 제한 파일에서만 읽고 공개 문서/argv에 넣지 않는다.

| 항목 | 현재 DiscordBotLXC |
| --- | --- |
| 역할 | Discord·SQLite·미디어, 별도 계정의 Jev API TLS 중계·영속 호출 원장 |
| 확인된 자원/런타임 | 2 vCPU / 2GiB / 20GiB, Debian13 / Python3.13.5 |
| 계정 | 봇 `changgeun-dev`, 중계 `changgeun-gateway`; unit은 root 소유 |
| 내부 전송 | loopback TLS `127.0.0.1:8443`, 별도 내부 토큰/개발 인증서 |
| 서비스 메모리 상한 | 봇900MiB / 중계384MiB; 미디어 하위 프로세스는 봇 범위 |
| 제품 검증 | 봇·중계 lint/타입/빌드/단위/mock/DB/API, 실제 Discord·음성 |

기존 privileged LXC를 보존하며 비root 실행만으로 잔여 위험을 해소했다고 주장하지 않는다. 컨테이너 재생성·호스트 변경은 하지 않는다. 외부 API 키는 root0600 환경 파일에서 systemd가 중계 계정에만 제공하고 봇 계정의 읽기 거절을 확인했다. 동일 서버 중계는 로컬 모델 실행이 아니다. torch/transformers/OpenJev·가중치·모델 캐시를 새 후보에 연결하지 않는다.

## 로컬 작업과 원격 실행

로컬은 코드·시험·문서·설정 작성/검토와 Git·stdlib 원격 제어만 수행한다. `scripts/check_repository.py`의 저장소 파일/ignore/링크 검사는 로컬과 GitHub CI에서 허용한다. 제품 import·설치·lint·타입·빌드·단위/mock·DB·API·음성 실행은 DiscordBotLXC에서만 수행한다. 원격 실패를 로컬 제품 실행으로 대체하지 않는다.

공개 소스/manifest만 현재 LXC에 전달한다. `.private`·키·DB·원장·venv·모델·로그·백업은 일반 동기화에 포함하지 않으며 목적지 삭제 동기화는 하지 않는다. 고정 candidate wheel은 소스 동기화만으로 바뀌지 않는다. 후보별 build manifest와 이후 문서/도구 수정의 Git 이력을 구분한다.

## 인증·시험 데이터와 예산

내부 토큰과 hosted 키, Discord/YouTube 키는 서로 분리한다. 비공개 원본을 shell-source하지 않는다. 실제 Discord 시험 서버·DJ역할·채널과 합성 시험음은 운영 데이터와 분리한다. 관리6명령은 Jev0회이며 실제 자연어만 hosted 판단을 사용한다. mock 회귀와 실제 Discord·제공자 인수를 합산하지 않는다.

새 중계 실행 `single-lxc-20260928`의 프로필/원장은 고정한다. 재시작·봇 전환 때 예산을 초기화하지 않는다. 이전 offline 서버의 원본·예산·후보와 인증 복원한 역사 백업을 보존했다. 과거 백업은 최신 원장 전체 이관 증거가 아니다. 계정 전체의 과거 누계/실제 비용·최종 품질/장시간/복구는 인수 전이다.

## 개발 후보

현재 개발 봇은 `patch117b`, 중계는 `patch116g`를 DiscordBotLXC에 적용했다. [1.1.7 기록](../../evidence/public/patch-117-development-20260928.md)에 해당 wheel/manifest와 부분 시험을 구분한다. 미디어는 봇에서만 처리한다. Node22.23.3·yt-dlp2026.8.19·EJS0.8.0·FFmpeg7.1.5 핀을 유지하며 원격 JS/runtime checksum을 후보 manifest에 결합한다. Portal Intent는 사용자가 켰으며 초기 `일반`, `discord-bot-test` 두 채널을 검증/DB 이관했다. 1.0.3부터 DB 주시 목록이 기준이고 일반 슬래시/멘션 허용 목록은 그대로 유지한다.

사용자는 목록·점검·끄기 확인 후 접두어 무응답·켜기 후 반응을 정상으로 확인했다. 자동 회귀와 남은 전체 W/음성/복구 인수는 [주시 실행 증거](../../evidence/public/watch-channels-20260928.md)를 따른다. 이전1.0.1/1.0.2 부분 미디어 인수는 [당시 실행 기록](../../evidence/public/youtube-prefix-20260928.md)에 보존한다.

## 과거 환경

[결정0002](../../docs/decisions/0002-lxc-runtime.md)의 두 LXC 구성은 당시 확인 기록이다. 이전 OpenJevLXC는8 vCPU/10GiB/32GiB/Debian13/Python3.13.5로 API 중계를 실행했으며 현재 사용 대상이 아니다. 당시 원본·키·DB·원장·캐시·후보·SSH/다른 서비스는 삭제/수정하지 않는다.

[현재 원격 도구](../../docs/REMOTE_DEVELOPMENT.md) · [프로필 계약](INFERENCE_PROFILES.md) · [진행 현황](STATUS.md) · [증거 양식](EVIDENCE_TEMPLATE.md)
