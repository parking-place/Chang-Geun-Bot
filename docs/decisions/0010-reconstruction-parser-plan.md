# 0010 — 1.2.0 Jev·LLM 해석기 재구성과 실제 목록 전달

- 날짜: 2026-09-28
- 상태: **사용자 지정 아키텍처의 계획 확정 / 구현·실행 전 PLANNED**
- 근거: 사용자가 ReconstructionPhase 명세로 재구성할1.2.0 단계 계획을 요청하고, 이어 실제 목록을 만들 수 있는 인수는 후보 생성 대신 목록 전달을 요청했다.

## 결정

[설계서 v1.3](../../Plans/2.%20ReconstructionPhase/changgeun_jev_llm_fallback_command_parser_spec_v1.3.md)와 [1.2.0의12단계 계획](../../Plans/2.%20ReconstructionPhase/1.2.0/README.md)을 적용한다. 원본 설계서 파일은 변경하지 않고 아래 보완을 함께 읽는다.

1. 정규화 → Jev 최초 패스 → LLM rewrite → Jev 재해석 → LLM full_parse의 유한 경로로 재구성한다. 성공하면 공통 검증으로 조기 종료하고 실제 누락·권한·서비스 오류는 모델로 우회하지 않는다.
2. 초기 LLM은 `gpt-5-nano`이며 공급자 독립 계약과 `disabled`를 둔다. 실행·권한·DB 변경은 코드만 한다. 외부 키는 현재처럼 DiscordBotLXC gateway 계정에 한정한다.
3. 재생목록·곡/entry·채널 등 열거 가능한 인수는 권한과 명시 범위의 실제 목록을 전달한다. 언어 추정·유사도 top-k로 목록을 대체하지 않는다. 새 이름·검색어만 원문에서 추출한다. 목록 크기/불완전/변경은 범위 질문·UI·최신 검증으로 해결한다.
4. 신규 `parser-api-v2`는 패스별Jev3·Jev합6·LLM각1·전체8회 계약이다. 기존 API1.2의 단일질문·요청당3회와 구분하여 gateway/client/domain/원장을 함께 이관한다. 기존 epoch·예산·tombstone을 초기화하지 않는다.
5. 업무DB의 기존 `command_requests`와 별도 trace DB를 둔다. 관측 원문과 하위 로그/캐시는 최초수신+7일에 만료하고 실행 중복 방지·비용/예산 기록은 별도 보존한다.

## 기존 결정과의 관계

[0005 Jev 전용](0005-jev-api-only.md)은 실제 활성1.1.x의 계약으로 유지한다. 이번 사용자 지시는 **향후1.2.0에 명시적 LLM fallback을 추가**하는 범위 변경이며, 과거 계약을 소급 수정하거나 계획만으로 GPT를 활성화하지 않는다. 로컬 OpenJev 사용 종료와 [0008 단일LXC 배치](0008-single-lxc-jev-api.md)는 계속 유지한다.

[0009 전체 자연어](0009-all-command-natural-language-plan.md)의 C01~C47·I01~I08·개인/관리 응답·주시 복구 목표는 유지한다. 새 계약에서 슬롯 후속60초·실행 확인300초를 구분하고 모델 예산을 재개하지 않는다. 원본 명세의 최대8회/35초는 신규 경로의 시작 설정이며 기존 실행 한도를 몰래 늘리지 않는다.

## 검증 경계

이번 산출물은 문서다. API 인증/지출·LXC 제품시험·봇 전환·VERSION/태그 변경은 수행하지 않는다. 구현 이후 [시험표](../../Plans/2.%20ReconstructionPhase/1.2.0/TEST_MATRIX.md)의33개 시험 묶음과 실제 Discord 인수로 판정한다. 기존 품질/미디어FAIL·부분 인수·백업검증SKIPPED는 [새 상태표](../../Plans/2.%20ReconstructionPhase/1.2.0/STATUS.md)에 연결하며 성공으로 바꾸지 않는다.
