# 1.1.1 개발 후보 실행 기록 — 2026-09-28

상태: **부분 LXC 시험·개발 후보 적용 PASS, 전체 P111 인수·정식 출시 미완료**. [계획](../../Plans/1.PatchPhase/1.1.1/README.md)과 [상태](../../Plans/1.PatchPhase/STATUS.md)를 함께 본다.

| 항목 | 결과와 범위 |
| --- | --- |
| 기준 | 1.1.0 봇 `patch110a`, 중계 `dev20260928l`; 같은 개발37문장 37/37, 신규29호출, 요청 p50 257ms/p95 723ms/max 845ms. 동일 네트워크 조건을 통제한 인과 실험은 아니다. |
| 후보 소스 | LXC 고정 source manifest `0449634642d65737237c4051deaa09e1e6b5ebc776e244335d55385fa6168dbe`. 이후 배포 스크립트 서식만 고쳐 원격 공개 소스 manifest는 달라졌다. 후보 wheel의 코드·시험에는 영향이 없다. |
| 최종 후보 | 봇 `patch111d` wheel SHA256 `6ce1e87dcb91e56ff2d5329041d53bf8390b5e211dfc642a1644fb8f06becfb6`, run `patch111d-20260928`; 중계 `patch111g` wheel SHA256 `272c8605f302cb6fca69789a5cc2445b60b31db37e62aea016baadfc6e6cfa3c`. 중계 교체 전 단위 파일을 `/etc/systemd/system/changgeun-jev-api.service.before-patch111g`에 제한 보관했다. |
| LXC 회귀 | 소스 `pytest tests` **378 PASS**, 최종 설치 봇 wheel **378 PASS**, 중계 설치 wheel 관련 시험 **42 PASS**. `ruff` PASS, bot/inference `mypy` **39파일 PASS**. 동시 health 합류, 제한 초과 청크 조기 중단, 3연속 일시 장애 차단, 비일시 장애 streak 초기화, 종료 후 사용 거절을 포함한다. |
| 실제 Jev 개발 표본 | 최종 후보의 합성37문장 **37/37**, 명확25/25, 위험 계획0, 오류0, 신규 dispatch29. 요청 p50 229ms/p95 298ms/max 727ms. 기준 대비 관측 p50 -28ms/p95 -425ms이지만, 표본·네트워크 편차를 분리하지 못해 성능 개선 확정이 아니다. |
| 제한 원본 | LXC `patch111d-20260928` run의 `korean-development-3bf68a9fde6544019aa2027ae929bcea.json`. 원문·실제 ID·비밀은 공개하지 않는다. |
| 원장·접속 | 중계 교체 전후 예약33/3000 동일; transport3회 후36, 첫 1.1.1 개발 표본 후65, 최종 표본 후 **94/3000**. TLS health/profile/config binding PASS, transport 3단계/재사용 PASS. 같은 `single-lxc-20260928` 원장·tombstones·프로필 해시 유지. |

J-02는 봇/중계의 유한 연결 풀과 명시적 종료를, J-03은 같은 binding의 동시 health 합류·2초 캐시를, J-08은 수신 중 64KiB 경계·안전 오류 문구·3연속 일시 전송 실패 뒤 최대5초 신규 접수 차단을 구현했다. 유료 복구 탐침·자동 재시도·fallback은 추가하지 않았다. 기준 대비 실제 표본의 p50/p95 관측만으로 각각의 최적화 효과나 음성 부하 시 개선을 확정하지 않는다.

**실패·복구:** 중간 봇 후보 `patch111c`는 LXC의 기본 `/usr/bin/node`가 v20.19.2라서 `media_runtime_unsupported`로 기동 실패했다. 배포 스크립트의 즉시 ACTIVE 출력은 지속 기동 증거가 아니었다. [Node.js 공식 v22.23.3 배포물](https://nodejs.org/download/release/v22.23.3/)과 같은 디렉터리의 `SHASUMS256.txt`로 `linux-x64` tarball을 검증하고, LXC의 격리된 `/opt/changgeun-dev/runtime/node-v22.23.3-linux-x64/bin/node`를 새 고정 후보에 명시했다. `patch111d`는 지속 `systemctl active`와 Jev 재평가·readiness를 통과했다. 이전 `patch111c` 기동 실패는 PASS에 포함하지 않는다.

**후속 정정(1.1.3):** `patch111d`의 Node 경로는 YouTube 격리 작업자의 허용 목록인 `/opt/changgeun-dev/runtimes/`와 달랐다. 이 후보에서 첫 PCM/YouTube 재생은 검증되지 않았으며 실제로 준비 실패할 수 있었다. 1.1.3의 `patch113b`에서 허용 경로와 첫 PCM을 확인했다. 1.1.1의 Jev/HTTP 성적은 그대로이나 미디어 인수 근거로 사용하지 않는다.

**남은 인수:** P111의 idle 재연결·pool 포화/취소·429/인증/복구·음성 부하 A/B·실제 Discord 오류/슬래시 대안·봇/중계 이전 wheel 복귀 시험이 필요하다. 사람의 명령/청취 확인을 요청했으나 아직 결과를 받지 않았다. 후보의 정식 `VERSION`·태그·`DONE` 판정은 하지 않는다.
