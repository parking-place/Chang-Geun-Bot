# 1.1.3 개발 후보 실행 기록 — 2026-09-28

상태: **개발 후보 적용·부분 LXC 시험 PASS, P113 전체 인수/정식 출시 미완료**. [계획](../../Plans/1.PatchPhase/1.1.3/README.md)과 [시험표](../../Plans/1.PatchPhase/TEST_MATRIX.md)를 따른다.

| 항목 | 결과와 범위 |
| --- | --- |
| 고정 후보 | 봇 `patch113b`, wheel SHA256 `f45674b45ed0f11f3292cad4273e1a5a80583c3ccf4043c70ec2dee1871b7b37`, LXC source manifest `363d7a48f2c586eb6c13e572207bb46d6ca15a0e98c3e2a636ca2db822ffc3b8`. 중계는 `patch111g`와 고정 profile/config/epoch 유지. |
| LXC 회귀 | 소스 `pytest tests` **384 PASS**, `patch113a`/`patch113b` 설치 wheel 각각 **384 PASS**, bot/inference mypy **40파일 PASS**, ruff PASS. 26개 목록·27개 제안 페이지, 타인 버튼/변경 snapshot 거절, 같은 곡의 두 큐 entry 중 지정 ID만 재승인, 잘못된 entry 거절, 현재곡 기본 상태를 포함. |
| 실제 Jev 개발 평가 | `patch113b` 합성37문장 **37/37**, 명확25/25, 위험 계획0, 신규 dispatch29. 요청 p50 217ms/p95 264ms/max 727ms. 제한 원본은 LXC `patch113b-20260928`의 `korean-development-3eb8042bc9274cd3bd82ba2673e8234d.json`; 독립/Discord 시험이 아니다. |
| 미디어 첫 PCM | `patch113b` 설치 wheel에서 공개 영상 `aqz-KE-bpKQ`의 첫 PCM 3840바이트 PASS, 준비 2.958초. 단일 영상/1회이며 20×5·Discord 청취를 대신하지 않는다. |
| 적용·원장 | 봇 run `patch113b-20260928` 기동·TLS binding PASS. `patch113a` 평가 후 예약152/3000, `patch113b` 신규29 → **181/3000**. 중계 run `single-lxc-20260928` 원장·tombstone·예산 유지. |

F-02는 일반 목록·검색·대기열·제안함을 최대10건씩 요청자 결합 ephemeral 페이지로 보여준다. 버튼 때 최신 역할/채널과 결과 fingerprint를 다시 확인하며 바뀌면 새 조회를 요구한다. 검색/제안의 25건 제한은 제거했고 긴 결과 파일/JSON 내보내기는 다른 경로에서 유지한다. 이 페이지는 현재 슬래시 조회에 적용했다. Prefix 조회는 기존 응답/파일 경로로 남아 있으며 계획의 prefix 페이지 조건은 아직 미완료다.

F-03은 대기열 화면의 만료 항목을 페이지 내에서 단건 선택하게 하고, 선택 entry ID와 현재 큐 버전을 기존 `TRACK_PLAY` 승인/권한/음성 규칙에 전달한다. 지정 항목이 사라지거나 같은 곡의 다른 entry이면 거절한다. 동일 곡 중 지정 entry만 재승인하고 큐 복제를 하지 않는 DB 회귀를 통과했다. 실제 음성 청취·중복 버튼/주시 끄기 경합은 남아 있다.

F-05는 `/현재곡`에 준비/재생/일시정지 등의 세션 상태, 볼륨, 반복, 다음 승인 곡, 안전한 YouTube 원본 참조 또는 승인 음원 표시와 수동 새로고침을 추가했다. 미디어 경과시간이나 주기 갱신은 추가하지 않았다.

**남은 인수:** 실제 Discord 다중 페이지·만료 선택·음성/현재곡 사용자 확인, 길이 제한/긴 한글·동시 편집·버튼 중복/주시 회수 전건, prefix 페이지, 이전 후보/DB 복귀가 필요하다. `VERSION`·태그·`DONE`은 변경하지 않는다.

**후속 수정:** `patch113a`까지 사용한 `/opt/changgeun-dev/runtime/`(단수) Node 경로는 격리 YouTube 작업자의 `/opt/changgeun-dev/runtimes/` 허용 조건을 만족하지 않았다. 기동/Jev 시험은 유효하지만 미디어 준비 근거가 아니며, `patch113b`의 허용 경로와 첫 PCM 시험으로 교체했다. 배포 준비에도 같은 경로 검사를 추가했다. 공식 Node v22.23.3 tarball을 공식 `SHASUMS256.txt`와 대조해 설치했고 이전 후보·바이너리는 보존했다.
