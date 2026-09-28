# 1.1.7 인증서 사전 점검과 미디어 준비 — 2026-09-28

상태: **개발 부분 검증; 1.1.7 통합 인수·출시 미완료**. [계획](../../Plans/1.PatchPhase/1.1.7/README.md), [시험표](../../Plans/1.PatchPhase/TEST_MATRIX.md)를 따른다. 서버 외부 백업·복원 검증은 사용자 지시로 SKIPPED이며 PASS가 아니다.

| 항목 | 고정 조건과 관찰 |
| --- | --- |
| 대상 | DiscordBotLXC, Jev API Only, 현 봇 `patch117b` wheel SHA256 `637506bdd9c63e13d34358b18c86ccfbf86a623cdacf2e2ce2149023128abb43`, 불변 gateway `patch116g` wheel SHA256 `cf3d49bad3dd6ba2ba1835f2257b20cc2f8a4fc4198c9a61ffca85001557937a`. `patch117b`는 진단 후 새 오류 코드의 사용자 안내만 보완했다. 고정 gateway 설정·원장·예산은 유지했다. |
| 도구 전달/회귀 | 최종 wheel 빌드 시 공개 소스 manifest SHA256 `3144638a95cc7178615d6840da57262d989de5e3e4f0838a6929d7830cf07f96`; 첫 진단 후보 `patch117a`는 `b3bdfeadf17caa5df02f63f8a835a3a35357ab01abbac5ea7ae12d25259d3c1e`. 최종 LXC 소스·설치 wheel 전체 각 **396 PASS**, mypy40파일·Ruff PASS. 새 [읽기 전용 점검 도구](../../scripts/check_gateway_lifetime.py)의 LXC `py_compile` PASS, 15/14/7/1/0일 임계값 시험 PASS. |
| 인증서/TLS | LXC root 실행 결과 `status=ok`, 인증서 만료 `2026-10-27T17:46:18Z`, 확인 시 약29.6일 잔여. 봇 CA로 loopback TLS의 `localhost` 호스트와 실제 인증서 일치 확인. 공개 인증서 SHA256 `62d52f1a953608c399981c617e9aec76a022087dedee0e0b9c4d34b8f40a003e`. |
| 계정/서비스 | 봇 계정이 gateway 개인 키·hosted 환경 파일을 읽지 못함을 확인. `changgeun-jev-api.service`와 `changgeun-dev-bot.service` 모두 active. `is-enabled`는 각각 `disabled`, `static`; 재부팅 자동 시작·갱신·경보 수신자 인수는 미완료. |
| 무료 readiness/예산 | `patch116a-20260928`/`eval-jev-api-single-lxc-v1` 설정의 `status`는 READY, 새 provider 호출0. `patch117a`와 최종 `patch117b-20260928` 적용 시 TLS/binding 확인·대기 drain·새 봇 active, gateway 무변경. 영속 원장 예약은 최종 전후 **446/3000**으로 재조회했다. |
| 변경 전 미디어 | `patch116a`/현재 공개20영상×5 첫 PCM **93/100**, 성공 p95 **4.393초**. 실패7건은 서로 다른7영상·2~5회차에 분산되고 모두 `youtube_first_pcm_failed`로 묶였다. 영상 제외·재시도 없이 목표95% 미달. 이를 개선 성공으로 재분류하지 않았다. |
| 진단 후보 미디어 | 같은 공개 목록의20영상×5, `patch117a` 첫 PCM **94/100**, 성공 시도의 p95 **3.811초**, 실패6건 전부 `youtube_stream_unavailable`(서명 미디어 URL HTTPS 응답 실패). 여섯 영상·2/4/5회차에 분산, 영상 제외·숨은 재시도 없음. 목표95% 미달 → **FAIL**. 제한 보고서 `/opt/changgeun-dev/runs/patch117a-20260928/jev-api/media-development-100.json` SHA256 `35b66f9d4ca2bfa95da86d0ff9307557fb02796eb9ca3b0afc47117d50e8f5c2`. 최종 `patch117b`는 안내 문구 매핑만 바꿨고 첫 PCM100회는 새 SHA에서 반복하지 않았다. |
| 백업 | **SKIPPED — 사용자 지정.** 외부 저장 대상이 없는 상태에서 새 암호화 백업·복원·RPO/RTO·rollback 시험을 실행하거나 PASS 처리하지 않았다. 기존 DB/원장/백업을 덮어쓰지 않았다. |

미디어 실패 원인 분리를 위해 worker가 추출 헤더 이후에도 첫 PCM 전에 `ready` 또는 고정 오류 코드만 내도록 프로토콜을 바꿨다. 서명된 URL·upstream 응답 본문은 봇/로그로 전달하지 않는다. `patch117a`는 94/100으로 목표에 실패했으며 성공으로 재분류하지 않는다. 이후 `patch117b`는 실패 안내만 보완했으므로 기존 미달 성적을 그대로 기록하고, 새 SHA의 PCM 인수를 했다고 주장하지 않는다. 미디어 준비 결과는 Discord 음성 시작·전환·사람의 청취와 분리한다. P117-01 전체, 자연어 경로별100·연속8시간·장애 주입, 인증서 실제 교체·재부팅·이전 바이너리/DB 복귀는 아직 확인되지 않았다. 특히 [1.1.6 첫 잠금 한국어 평가](patch-116-development-20260928.md)는 명확103/120·예상 밖 계획3으로 FAIL이어서 통합 후보의 독립 품질 선행 게이트가 막혀 있다. 이 증거로 `VERSION`·출시 태그·DONE을 변경하지 않는다.
