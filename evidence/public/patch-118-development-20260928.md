# 1.1.8 소스 개발 및 LXC 개발 시험

상태: **IN_PROGRESS — 소스 후보 검증, 실제 봇 미적용, 전수·독립·Discord 인수 전**. 이 문서의 값은 정식 `VERSION` 또는 출시 판정이 아니다.

| 항목 | 확인한 범위 |
| --- | --- |
| 실행 위치 | DiscordBotLXC에서만 제품 lint·타입·unit/mock·Jev API 판단을 실행했다. 로컬에서는 문서/코드/Git 및 저장소 파일 검사만 수행했다. OpenJevLXC에는 작업하지 않았다. |
| 구현 | C01~C47 공통 ID 등록부(C39는 진입점), 제한 후보 Jev 선택, 구조화 별칭, 주요 인자 추출·기존 Action/관리 서비스 연결. 접두어 텍스트 취소, 관리자/개인 조회 결과 버튼, 동적 주시 채널의 버튼 출처 세대 검사. |
| 소스·wheel 회귀 | 공개 소스 manifest SHA256 `e9769c1c5d57f19d8f3ceb72d93788113a437f6286fc399d90e3f6271568724e`. 봇 source-first 및 새 설치 wheel `patch118a`에서 각각 단위·통합·안전 **369 PASS**, 관련 Ruff/mypy PASS. 새 wheel SHA256 `a40c4e5cb6572bdf41ebe56538b5b4ac438a5598b3450b75445e9e57edd56be0`; 빌드와 설치 의존성 검사는 LXC에서 성공했다. 이는 활성 봇/실제 Discord 성적이 아니다. 중계 소스 안전 회귀44 PASS; 활성 wheel `patch116g`에 최신 소스 테스트를 연결한 전체 contract는 collection 오류(`COMPACT_INSTRUCTIONS` 없음)로 PASS 아님. |
| 실제 Jev 개발 예문 | [전수 대응표](../../Plans/1.PatchPhase/1.1.8/COMMAND_COVERAGE.md)의 C39 제외46개 대표 문장 의도 ID **45/46**, 여섯 관리 문장은 명시한 구조화 경로로0호출, 나머지40문장 중39개가 Jev 경로에서 선택됐다. 공유 원장574→618/3000, 실제44 dispatch. C34의 “이 제안을 승인”은 대상 번호/답장 문맥이 없어 `clarify`였고, 완성 실행의 오답으로 바꾸어 세지 않는다. |
| 교란 개발 문장 | 이미 결과를 보며 작성한20문장 중 기대 선택18개, 나머지2개는 안전한 거절이었다. 그 두 개는 인용 제목 검색과 링크 없이 등록 요청이므로 기능 성공으로 계산하지 않는다. 기대하지 않은 위험 ID 선택은 이 선택기 표본에서0. 원장618→639/3000, 실제21 dispatch. |
| 활성 서비스 | `changgeun-dev-bot`와 `changgeun-jev-api` 모두 active였으며 기존 bot `patch117b`/gateway `patch116g`를 유지했다. 이 1.1.8 소스는 활성 서비스의 설치 wheel이 아니다. |

개발 예문은 구현하면서 후보 설명·threshold 경로를 조정한 **훈련/회귀 자료**다. 의도 ID만 채점했으며 올바른 목록/곡/채널 ID, 옵션, 확인/페이지, 실제 Discord 응답과 청취까지 점검하지 않았다. 이45/46을 P118-01의 전수 동등성이나 P118-02의 신규 독립221문장·명확141문장95% 기준에 넣지 않는다. 마지막 원장 읽기에서639/3000이었고 새 시험 전에는 다시 조회한다. 내부 forward/가격은 unavailable/unknown으로 남는다.

현재 미완료 핵심은 단회60초 typed continuation과 원래 추론 기한 분리, I01/I04~I08의 자연어 후속 조작 전수, 모든 공개 옵션·역할/채널/음성의 실행 회귀, 독립 평가와 비용·지연 시험, 동일 후보의 실제 Discord 전건 인수다. 따라서 새 봇을 배포하지 않고 기존 동작을 유지했다. 기존1.1.6 독립 FAIL, 1.1.7 PCM94/100 FAIL와 사용자 지정 백업 검증 SKIPPED도 유지한다.

재현 도구는 `scripts/probe_natural_selection.py`, `scripts/probe_natural_coverage.py`이며 제한 설정 경로를 인자로 받는다. 둘 다 실제 Jev 호출을 소비하므로 고정 원장 잔여량을 먼저 확인한다. 전수 대응표 문장은 개발 자료로만 사용한다.
