# 1.2.0 재개 기록 — 사용자 요청으로 중단

> 2026-09-28 사용자 “이어서 해줘” 지시로 작업을 재개했다. 아래 내용은 당시 중단 시점의 스냅샷으로 보존한다. 이후 진행은 [STATUS](STATUS.md)와 [실행 기록](../../../evidence/public/reconstruction-120-progress.md)에 기록한다.

- 중단일: 2026-09-28.
- 사용자 지시: **“멈추고 어디까지 했는지 저장해”**. 추가 구현·제품 시험·API 호출·배포·GitHub push를 중단했다. 이 파일과 STATUS의 중단 기록만 로컬에 저장한다.
- 현재 브랜치: `codex/reconstruction-1.2`.
- 현재 HEAD: `10aff49858dd7179ddb6eec7f4958e1c1579e1fc`.
- 재개 위치: **p3 원문 보존·정규화 구현 전**. p1/p2는 개발 체크포인트이며 전체 단계 인수/정식 출시 완료가 아니다.

## GitHub에 올라간 체크포인트

| 단계 | 커밋 | 태그 | 실제 산출물과 검증 |
| --- | --- | --- | --- |
| p1 | `83b6646104999cf70f3498d31e4d659ee5c13bc2` | [v1.2.0-p1](https://github.com/parking-place/Chang-Geun-Bot/tree/v1.2.0-p1) | 계획 전체·parser-api-v2 계약·공급자 독립 파서 포트·JSON Schema. LXC 계약시험3 PASS, Ruff PASS |
| p2 | `10aff49858dd7179ddb6eec7f4958e1c1579e1fc` | [v1.2.0-p2](https://github.com/parking-place/Chang-Geun-Bot/tree/v1.2.0-p2) | 실제47개 slash 정의 기반 typed registry·공통 CommandService. 신규등록부+기존어댑터/자연어 회귀45 PASS, 신규파일 Ruff/mypy PASS |

두 태그와 브랜치 push는 성공했다. PR·GitHub Release·정식 제품 VERSION은 만들지 않았다. 중단 기록 작성 직전 작업 트리는 깨끗했다. 이전 계획 변경은 `stash@{0}`의 `pre-reconstruction-1.2.0-plans-20260928`에 보존했고 새 브랜치에 복원/커밋했다. 이 stash는 삭제하지 않았다.

## 현재 코드

- `inference/src/changgeun_inference/contracts_v2.py`: API1.2와 별도인 root/call/question/response/usage 계약. 두 패스·묶음 질문·Choice255·전체35초 계약의 타입 검증. **새 endpoint/영속8회 원장은 아직 없다.**
- `shared/schemas/parser-request-v2.json`, `parser-response-v2.json`: 위 계약에서 지정 LXC로 생성한 schema.
- `bot/src/changgeun/parser/contracts.py`: CommandDraft/ParserOutcome/Evidence/ModelPort/TracePort. 실제 파서 실행기는 아직 없다.
- `bot/src/changgeun/parser/registry.py`: 인수 타입/기본값/범위/source/권한·위험도 규격.
- `bot/src/changgeun/discord_adapter/registry.py`: 실제 slash 정의에서47개 명령과 모든 옵션을 읽고 고정 callback으로 연결. 실제 목록 resolver 종류를 선언했지만 목록 조회/선택 구현은 p4에 남아 있다.
- `bot/src/changgeun/application/commands.py`: 닫힌 handler 호출·권한·인수 검증. client 초기화에 등록부를 연결했으며 새 자연어 경로에서의 실제 사용은 p9에 남아 있다.
- 새 시험: `tests/safety/test_parser_v2_contracts.py`, `tests/integration/test_parser_registry.py`.

## 실행 환경과 예산

- 중단 전 확인한 활성 봇: **patch117b**, 실제 systemd gateway: **patch116g**. 이번 작업에서 활성 서비스를 교체하지 않았다. 새 코드는 지정 LXC의 개발 source에만 동기화/시험했다.
- 제한 runtime metadata에는 과거 gateway `dev20260928l` Python 경로가 남아 있었다. 실제 unit과 다르므로 다음 검증에서 metadata만으로 interpreter를 선택하지 않는다.
- 기존 내부 TLS readiness PASS·해당 점검 provider calls0. 마지막 실제 읽은 Jev 예약 **640/3000**, 고정 epoch `single-lxc-20260928`. 기존 원장·업무DB·tombstone을 그대로 유지했다.
- 사용자 지정 **GPT-5 nano 실호출 검증 누적 지출 상한 US$1**. 이번 작업의 GPT 실호출/과금은0. 새 영속 금액 예약/상한 구현과 gateway 키 주입·인증은 아직 하지 않았다. 상한은 단계/재시작마다 새로 주는 금액이 아니다.
- 제품 설치·lint·타입·unit/mock·DB/API/Discord 검증은 **DiscordBotLXC에서만**. 로컬은 작성·Git·저장소 파일 검사만 수행한다. OpenJevLXC를 사용하지 않는다.

## 남은 순서와 재개 시 주의

1. 이 문서와 [STATUS](STATUS.md), [단계 계획](README.md), [실행 기록](../../../evidence/public/reconstruction-120-progress.md)을 읽고 현재 Git/LXC/잔여 예산을 다시 확인한다. 사용자 재개 지시 전에는 구현을 이어가지 않는다.
2. p3 원문/보호구간/NFC/source map, p4 실제 목록 전달과 새 값 추출을 구현한다. 기존 재생목록/곡/채널은 실제 범위 전체 목록을 전달하고 top-k/임의 잘림으로 대체하지 않는다.
3. p5 신규 gateway/API·공통 영속8회/하위상한·기한·취소 및 기존 누적 예산 보존, p6 Jev 두 패스/묶음 질문, p7 GPT 두 작업/disabled·US$1 금액원장을 구현한다.
4. p8 rewrite/재해석/full_parse 전이, p9 원문/객체/권한 검증·단회60초후속·300초확인·실제 공통서비스 연결, p10 별도trace DB·마스킹·usage·최초수신+7일 만료를 구현한다.
5. p11 같은 source/wheel의 전수 회귀·새 잠금221문장·명령+전체인수·경로별 성능/비용·이관/복귀, p12 제한된 실제 Discord 인수·전환·모델 수명을 검증한다. 필요한 사람 조작/청취는 자동시험으로 대체하지 않는다.
6. 각 후속 단계 결과를 커밋하고 `v1.2.0-p3`부터 태그/push한다. 한 단계의 일부 검증만으로 전체 기능 DONE이나 정식출시를 표시하지 않는다.

p1의 명령/서비스 전수 대응은 p2 등록부로 진전됐지만 p9의 실행 동등성까지 완료된 것은 아니다. p2의45시험은 전체 명령·옵션의 의미 품질 인수가 아니다. 기존1.1.6 독립평가FAIL,1.1.7 미디어/장시간 미완료,1.1.8 미적용/미완료, 사용자 지정 백업검증SKIPPED는 계속 보존한다.

## 마지막 저장소 검사

p2 커밋 전 공개파일320개·문서링크1715개·ignore/비밀값 패턴 및 staged diff 검사가 통과했다. 이는 저장소 검사이며 제품 인수 성적과 별개다. 이 중단 문서를 저장하기 위해 추가 제품시험·API 호출·배포를 수행하지 않았다.
