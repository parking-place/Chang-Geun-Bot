# 1.0.2 — 지정 채팅 채널의 `!!창근아` 한국어 명령

| 항목 | 내용 |
| --- | --- |
| 상태 | IN_PROGRESS — 개발 후보·부분 시험; 전체 인수 전 |
| 작성 기준일 | 2026-09-28 |
| 사용자 목표 | 선택한 여러 채팅 채널에서 `!!창근아`로 시작하는 새 메시지의 뒤 문장을 한국어 명령으로 처리 |
| 기반 계약 | [명세 1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md), [후속 버전 범위 결정](../../../docs/decisions/0006-youtube-and-prefix-roadmap.md), [Jev API 전용](../INFERENCE_PROFILES.md) |
| 선행 조건 | 공통 실행기·권한·확인·자연어·원장의 필수 인수; 정식 승격은 1.0.0 → 1.0.1 → 1.0.2 |
| 시험 환경 | DiscordBotLXC 입력·DB·Discord·음성; DiscordBotLXC의 중계 Jev API·원장 |

예를 들어 지정 채널의 `!!창근아 노동요 목록 틀어줘`, `!!창근아 지금 곡을 새벽 목록에 넣어줘`, `!!창근아 대기열 세 번째 곡 빼줘`를 기존 한국어 판단과 공통 실행기에 연결한다. 해석 후 실제 동작의 DJ·동일 음성채널·확인 정책을 적용한다. 호출되지 않은 대화는 추론하지 않는다.

1.0.0은 아직 전체 인수 전이다. 1.0.2의 입력·권한·Jev 연결 개발은 승인 시험음으로 독립 진행할 수 있고, 1.0.1의 YouTube 재생 소스 확정 때문에 이 개발까지 기다릴 필요는 없다. 다만 YouTube 문장형 재생 인수는 1.0.1 소스 게이트 통과 후 수행하며, 1.0.1이 미완료라면 1.0.2를 정식 출시로 건너뛰지 않는다. 독립 개발 후보와 정식 버전 상태를 분리한다.

## 계획 작성 당시 구현과 변경 대상

아래 표는 2026-09-28 계획 작성 당시 기준선이며 현재 실행 상태는 아래 개발 기록을 따른다.

| 현재 소스 | 확인한 상태 | 1.0.2 작업 |
| --- | --- | --- |
| [client.py](../../../bot/src/changgeun/discord_adapter/client.py) | `on_message`는 선두 실제 봇 멘션을 받으며 Message Content Intent는 켜지 않음 | 정확한 접두어 라우터·본문 접근 진단·메시지 종류 필터 |
| [config.py](../../../bot/src/changgeun/config.py), [설정 예시](../../../deploy/config.example.yaml) | 공통 텍스트 채널 ID만 파싱; 예시의 일반 호출어 설정은 실제 입력 계약을 구현하지 않음 | 별도 활성화·접두어 채널 목록·설정 검증·안전한 비활성화 |
| [mention.py](../../../bot/src/changgeun/discord_adapter/mention.py) | 공개 reply가 interaction의 `defer`·`ephemeral` 인터페이스를 흉내 냄 | 일반 메시지 응답과 interaction 응답을 명시적으로 구분 |
| [pipeline.py](../../../bot/src/changgeun/nlp/pipeline.py) | 호출마다 새 UUID; 사용자·채널별 메모리 cooldown; 일부 동작 후보만 존재 | 메시지 ID에 묶인 영속 중복 방지·서버 단위 공정한 접수·지원 행동표 |
| [executor.py](../../../bot/src/changgeun/application/executor.py) | 권한·확인·버전·request ID 중복 제어 구현 | 접두어 경로도 동일 실행기와 동일 요청 신원 사용 |

## 입력 계약

- 접두어는 원문 첫 글자부터 정확히 `!!창근아`다. 접두어 다음은 ASCII 공백·탭·개행 또는 메시지 끝이어야 한다. 앞 공백, 전각 느낌표, 제로폭 문자, `!!창근아님`, `!!창근아노동요`는 실행하지 않는다. 일반 문장·인용·코드블록 안의 호출어를 검색해서 실행하지 않는다.
- 뒤 본문의 앞뒤 ASCII 공백·탭·개행만 제거하고 CRLF를 LF로 맞춘다. 본문 안의 줄바꿈·부정어·제목은 보존한다. 여러 줄이어도 한 요청이며 복합 변경은 분리 안내한다. 접두어를 뺀 본문은 1~500 Unicode 코드포인트다. 빈 본문은 짧은 사용 예, 초과 본문은 축약 안내만 보내며 Jev 호출은 0회다.
- 서버 ID와 실제 채널 ID를 모두 확인한다. 접두어 채널은 공통 명령 채널의 부분집합으로 명시 등록하며 이름·카테고리·부모 채널 권한에서 자동 확장하지 않는다. 1.0.2는 일반 길드 텍스트 채널만 지원한다. 스레드·포럼 게시물·공지·음성 채널의 채팅·DM은 기본 거절이며 스레드 지원 확장은 별도 범위다.
- 새 사용자 메시지 생성만 접수한다. 봇·자기 자신·웹훅·시스템 메시지는 무시한다. 수정은 새 명령이 아니며, 접수된 원문 수정·삭제가 실행 커밋 전에 관측되면 진행 요청과 확인을 무효화한다. 완료된 변경을 메시지 삭제만으로 되돌리지 않는다.

상세 문법·예시는 [2단계](02_prefix_router_and_lifecycle.md)에 둔다. 이 계약을 개발 후보에 구현했다. 실제 허용 채널은 제한 설정에서 선택하며 전체 인수 결과는 별도로 추적한다.

## 단계와 출구 기준

| 단계 | 문서 | 주요 산출물 | 시험 |
| --- | --- | --- | --- |
| 1 | [채널 설정·본문 접근](01_channel_configuration_and_intents.md) | 별도 채널 목록, Intent 진단, 최소 권한, 비활성화 계약 | C-01~02, C-05 |
| 2 | [접두어·요청 수명](02_prefix_router_and_lifecycle.md) | 정확한 파서, 중복 방지, 수정·삭제·재연결 처리 | C-03~08 |
| 3 | [한국어·공통 실행기](03_korean_commands_and_execution.md) | 지원 행동표, Jev 연결, 최신 권한·확인·문맥 | C-10~14 |
| 4 | [응답·부하·개인정보](04_responses_limits_and_privacy.md) | 공개 응답 수명, 동시성·예산, 최소 전송·보관 | C-09, C-15~16 |
| 5 | [품질·실제 채널 인수](05_acceptance_and_rollout.md) | 독립 200문장·명확 95%, 두 채널 실제 인수·rollback | C-17~18 및 전체 C 회귀 |

모든 단계는 IN_PROGRESS이며 아직 VERIFIED/DONE은 없다. 필수 C-01~18 및 영향 받는 T/N/B 회귀, 고정 후보의 독립 held-out 200문장 이상·명확한 지원 요청 95% 이상, 권한 우회·무확인 위험 실행·중복 실행 0건을 요구한다. 기존 개발 37문장 결과로 대신하지 않는다. 코드·LXC 단위/mock·실제 API·실제 Discord·사용자 청취 증거를 구분한다.

공식 문서 확인일은 2026-09-28이다. 일반 메시지의 본문 접근은 [Discord Gateway Message Content Intent](https://docs.discord.com/developers/events/gateway#message-content-intent), 채널 접근은 [Discord Permissions](https://docs.discord.com/developers/topics/permissions), 메시지 응답은 [Message Resource](https://docs.discord.com/developers/resources/message), 버튼 응답은 [Interactions](https://docs.discord.com/developers/interactions/receiving-and-responding)를 기준으로 구현 시 다시 확인한다.

[진행 현황](../STATUS.md) · [시험 매트릭스](../TEST_MATRIX.md) · [실행 환경](../ENVIRONMENT.md) · [증거 양식](../EVIDENCE_TEMPLATE.md)

## 2026-09-28 개발 기록

[고정 후보와 부분 실행 증거](../../../evidence/public/youtube-prefix-20260928.md)를 따른다. 단위/mock·실제 API·첫 PCM·Discord 사용자 청취를 구분하며 아래 필수 인수 조건은 유지한다. 부분 성공만으로 이 단계나 전체 버전을 VERIFIED/DONE으로 표시하지 않는다.

초기 허용 채널은 사용자가 선택한 `일반`, `discord-bot-test`다. 채널 설정을 바꾸는 명령은 [1.0.3 계획](../1.0.3/README.md)으로 구체화했으며, 현재 1.0.2는 제한 배포 설정으로 관리한다.
