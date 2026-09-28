# 1.2.0 재구성 단계 실행 기록

사용자 요청으로12단계를 구현하며 각 단계 체크포인트를 `v1.2.0-p1`부터 GitHub에 올린다. 태그는 개발 단계 산출물 식별자이며 제품 전체/정식출시 PASS가 아니다. 기존1.1.x 실패·미완료·백업검증SKIPPED는 보존한다.

## p1 — 기준선과 신규 계약

- 시작 소스:474dad904466f0cce0817f7ac2527e4b86d9264c. 기존 계획 변경을 `pre-reconstruction-1.2.0-plans-20260928` stash로 보존하고 `codex/reconstruction-1.2`에 복원했다.
- DiscordBotLXC 실제 확인:bot patch117b / 실행 gateway patch116g. runtime metadata의 gateway 경로는 과거dev20260928l로 남아 있어 실행 unit 기준으로 구분했다. metadata만 보고 새시험 Python을 고르지 않는다.
- 기존 내부TLS readiness PASS, 실제 provider dispatch0. 고정epoch의 Jev 예약640/3000. 업무command_requests와 message_requests 등 기존DB 보존, 모델/API 실호출 없음.
- 새 parser-api-v2 root/call/question/usage 계약과 공급자 독립 봇 초안/결과/포트, 요청/응답 JSON Schema 추가. API1.2·기존서비스 활성값은 그대로 유지한다.
- LXC source 계약시험3 PASS:구버전 분리·35초/finite기한·pass/stage/operation 제약·묶음질문·255한도·usage null/부분집합. 신규파일 Ruff PASS.
- 원본 재구성명세SHA256은70bc3e9b63fbbd3b6b52589289852a7aac123baa139e57487e0d58be071f3a2c로 보존했다.
- 판정: p1 계약 코드/문서 검토·제한LXC 검증. 전체명령 전수/실제파서/과금API/Discord 인수는 후속단계다.

실제 실행: `scripts/remote.py`로 공개소스를 전송한 뒤 지정LXC에서 source PYTHONPATH의 `tests/safety/test_parser_v2_contracts.py`를 실행했다. 제품시험은 로컬에서 실행하지 않았다.
