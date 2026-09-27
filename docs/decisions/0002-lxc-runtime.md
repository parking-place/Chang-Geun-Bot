# 0002 — 확인된 LXC 개발 런타임

> 현재 물리 배치는 2026-09-28 [결정0008](0008-single-lxc-jev-api.md)이 대체한다. 아래 두 서버 구성은 당시 기록이며 OpenJevLXC에 새 작업을 수행하지 않는다.

- 상태: 실제 환경 확인 및 개발 채택; 운영 승격은 별도 인수
- 확인일: 2026-09-27
- 대상: DiscordBotLXC, OpenJevLXC

두 지정 LXC는 Debian 13과 Python 3.13.5다. 계획의 Ubuntu 24.04/Python 3.12 기본안을 맞추려고 컨테이너를 재생성하거나 기존 서비스를 교체하지 않는다. 제품의 최소 Python 3.12 계약은 유지하며 현재 개발 증거는 실제 Python 3.13.5 환경에 한정한다. Python 3.12 실행을 시험한 것으로 표시하지 않는다.

DiscordBotLXC는 2 CPU/2 GiB, OpenJevLXC는 8 CPU/10 GiB로 확인했다. 비root `changgeun-dev`, `/opt/changgeun-dev`와 `/var/lib/changgeun-dev`를 사용하며 기존 SSH와 메일 서비스는 보존한다. 초기에는 hosted 환경과 CPU 모델 환경을 분리했다. 이후 [결정0005](0005-jev-api-only.md)에 따라 실제 실행은 Jev API 전용 gateway로 고정했다. 과거 CPU 모델 환경은 보관하며 새 후보에 연결하지 않는다.

TLS는 전용 개발 CA와 검증을 사용한다. 시스템 전역 신뢰 저장소는 바꾸지 않는다. Python 3.13의 엄격한 인증서 검증에 맞춰 CA/server keyUsage와 SAN을 구성했으며 검증을 끄지 않았다. 개발 인증서와 시험 systemd 서비스는 정식 운영 PKI·배포 완료를 의미하지 않는다.

시험·wheel·의존성·모델 핀과 실제 제한은 [개발 실행 기록](../../evidence/public/execution-20260927.md)에 남긴다. 새 런타임이나 운영 환경으로 승격할 때 해당 환경의 인수를 다시 수행한다.
