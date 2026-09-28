# 1.1 계열 시험 추적표

- 상태: **1.1.0~1.1.7 부분 검증 중, 1.1.8 NOT_RUN**. 1.1.6 첫 독립 품질 FAIL, 1.1.7 백업 검증 사용자 지정 SKIPPED이며 전체 버전 인수는 미완료다. [계열 현황](STATUS.md)과 각 버전 실행 기록을 따른다.
- 범위: 9개 버전별7개, 총63개 시험. 단계/버전 상태는 [STATUS](STATUS.md), 포함 항목은 [ITEM_COVERAGE](ITEM_COVERAGE.md)에 기록한다.
- 아래 시험명은 추적용 요약이다. 상세 통과 조건과 하위 시나리오는 각 버전 README를 따른다. 대표 사례 하나의 성공으로 한 ID 전체를 PASS 처리하지 않는다.

## 실행과 증거

제품 단위/mock·DB·lint/타입·실제 API·Discord/음성 시험은 모두 **DiscordBotLXC**에서 한다. 로컬 문서 검사는 이 표의 PASS 근거가 아니다. 1.1.0~1.1.7 개발 후보의 소스/설치 회귀와 부분 실제 Jev/Discord 시험은 실행했으며 사람의 100회 조작/청취·8시간·전체 성능 인수는 남아 있다. 1.1.8은 전건 미실행이다.

각 ID에 실제 source/wheel/config/profile/schema·fixture hash, 실행 시각/환경, 자동/실제 구분, 전체 시도/실패/미실행 분모와 증거 경로를 연결한다. 유료 요청은 원장 전후 누계·예산과 결합하고 비밀 제거 요약만 공개한다. [공통 계약](EXECUTION_RULES.md)과 [증거 양식](../0.DevPhase/EVIDENCE_TEMPLATE.md)을 적용한다.

상태 칸은 NOT_RUN/PASS/FAIL/SKIPPED와 필요한 부분 결과로 관리한다. 과거 후보의328/41회귀·개발37문장·첫 PCM93/100·사용자 부분 인수를 새 후보의 통과로 복사하지 않는다. 최적화의 채택/기준 유지 결론은 실행 결과와 별도로 기록한다.

## 1.1.0

[버전 계획·상세 통과 조건](1.1.0/README.md)

권한/출처·오류·계측의 단위/mock/DB 회귀, 실제 Jev 기준 계측, 역할별 Discord 도움말과 동적 채널 조작을 구분한다.

| ID | 시험 시나리오 | 결과 | 새 실행 증거 |
| --- | --- | --- | --- |
| P110-01 | 정적 채널/신규 동적 채널에서1/2/3단계 | PARTIAL — 다후보2단계 mock PASS | [1.1.0 기록](../../evidence/public/patch-110-development-20260928.md) |
| P110-02 | 가짜 출처·슬래시/멘션·주시 제거/끄기·DJ 회수 | PARTIAL — 2단계 전 제거 PASS | [1.1.0 기록](../../evidence/public/patch-110-development-20260928.md) |
| P110-03 | 성공·모호함·권한 거절·timeout·예산 소진 | PARTIAL — 개발37/37 | [1.1.0 기록](../../evidence/public/patch-110-development-20260928.md) |
| P110-04 | 완료/실패/재사용/합류의 계측 | PARTIAL — 새 호출·지연 계측 | [1.1.0 기록](../../evidence/public/patch-110-development-20260928.md) |
| P110-05 | 일반 사용자/DJ/관리자의 주시·미주시 도움말 | PARTIAL — 역할/채널 mock PASS | [1.1.0 기록](../../evidence/public/patch-110-development-20260928.md) |
| P110-06 | 계측 예외·민감 입력·로그/보고서 검사 | PARTIAL — 안전 문구/유한 집계 mock PASS | [1.1.0 기록](../../evidence/public/patch-110-development-20260928.md) |
| P110-07 | 후보 재시작·복귀와 동일 요청 재전달 | PARTIAL — 전환/readiness PASS, 복귀 미실행 | [1.1.0 기록](../../evidence/public/patch-110-development-20260928.md) |

## 1.1.1

[버전 계획·상세 통과 조건](1.1.1/README.md)

제한된 HTTP transport/오류 주입·수명/슬롯 회귀, 동일 표본 실제 Jev 비교, Discord 장애 안내·슬래시 대안을 구분한다.

| ID | 시험 시나리오 | 결과 | 새 실행 증거 |
| --- | --- | --- | --- |
| P111-01 | 연속 판단·idle 만료·종료/재시작 | PARTIAL — client 재사용/close mock·서비스 재기동 | [1.1.1 기록](../../evidence/public/patch-111-development-20260928.md) |
| P111-02 | 동시 health·캐시 만료·profile/token/TLS 변경 | PARTIAL — 동일 binding 합류·변경 거절 mock | [1.1.1 기록](../../evidence/public/patch-111-development-20260928.md) |
| P111-03 | pool 포화·느린 청크·단계3 잔여 부족 | NOT_RUN | — |
| P111-04 | 정상/64KiB 경계·초과·깨진 JSON·수신 취소 | PARTIAL — 초과 청크 조기 중단 mock | [1.1.1 기록](../../evidence/public/patch-111-development-20260928.md) |
| P111-05 | 순간 요청·queue_full·외부429/인증 실패·지속 장애/복구 | PARTIAL — 3연속 일시 장애/비일시 reset mock | [1.1.1 기록](../../evidence/public/patch-111-development-20260928.md) |
| P111-06 | 기준/후보의 warm/cold·음성 부하 비교 | PARTIAL — 같은 개발37문장 관측; 음성 부하 미실행 | [1.1.1 기록](../../evidence/public/patch-111-development-20260928.md) |
| P111-07 | service drain·TLS 재준비·이전 wheel 복귀 | PARTIAL — 봇/중계 교체·원장 보존; 이전 wheel 복귀 미실행 | [1.1.1 기록](../../evidence/public/patch-111-development-20260928.md) |

## 1.1.2

[버전 계획·상세 통과 조건](1.1.2/README.md)

권한·DB·검색 fixture와 조회 계측, 개발 세트의 실제 판단 비교, Discord 자동완성·오래된 선택 조작을 구분한다.

| ID | 시험 시나리오 | 결과 | 새 실행 증거 |
| --- | --- | --- | --- |
| P112-01 | 단일 DJ 행동의 권한 부족·음성 불일치 | PARTIAL — DJ 거절 신규 dispatch0 mock | [1.1.2 기록](../../evidence/public/patch-112-development-20260928.md) |
| P112-02 | 혼합 권한 후보·신규 동적 채널·중간 권한/주시 취소 | NOT_RUN | — |
| P112-03 | 작은/큰 자료·긴 큐에서 단계별 조회 | PARTIAL — 후속 전체 snapshot 재조회0 mock, 대형 측정 미실행 | [1.1.2 기록](../../evidence/public/patch-112-development-20260928.md) |
| P112-04 | 조회 사이 목록/큐/현재곡·주시 세대 변경 | NOT_RUN | — |
| P112-05 | 정확명/별칭/짧은 이름·동명·후보10개 경계 | PARTIAL — 구체명 우선·11개 재질문 mock | [1.1.2 기록](../../evidence/public/patch-112-development-20260928.md) |
| P112-06 | 자동완성의 입력/빈 결과·서버 경계·삭제/이름 변경 | PARTIAL — 서버 격리·삭제 제외·별칭 mock; 실제 Discord 미확인 | [1.1.2 기록](../../evidence/public/patch-112-development-20260928.md) |
| P112-07 | 후보 고정·이관 여부·이전 바이너리/DB 복귀 | PARTIAL — wheel/manifest·개발37/37, 복귀 미실행 | [1.1.2 기록](../../evidence/public/patch-112-development-20260928.md) |

## 1.1.3

[버전 계획·상세 통과 조건](1.1.3/README.md)

snapshot/버튼/승인 회귀와 실제 Discord 페이지·단건 재승인·현재곡 상태 조작을 구분한다.

| ID | 시험 시나리오 | 결과 | 새 실행 증거 |
| --- | --- | --- | --- |
| P113-01 | 빈 목록·긴 한글 제목·25건 초과 제안·다중 페이지 | PARTIAL — 26목록·27제안 페이지 mock | [1.1.3 기록](../../evidence/public/patch-113-development-20260928.md) |
| P113-02 | 페이지 사이 삭제·이동·동명 곡·snapshot 만료 | PARTIAL — 삭제 snapshot 거절 mock | [1.1.3 기록](../../evidence/public/patch-113-development-20260928.md) |
| P113-03 | 타인 버튼·DJ 회수·정적/동적 채널·주시 제거 | PARTIAL — 타인 페이지 거절 mock | [1.1.3 기록](../../evidence/public/patch-113-development-20260928.md) |
| P113-04 | 만료 단건 재승인·동일 버튼 재전송·끄기/켜기 | PARTIAL — 1.1.3 실제 선택 FAIL, 1.1.4 수정 후 사용자 정상 확인; 경합 전 | [1.1.3 기록](../../evidence/public/patch-113-development-20260928.md) |
| P113-05 | 현재곡 준비/재생/일시정지·반복·다음 승인 만료 | PARTIAL — 연결 안 됨/볼륨 기본 상태 mock | [1.1.3 기록](../../evidence/public/patch-113-development-20260928.md) |
| P113-06 | 조회·버튼의 호출/개인정보, 준비 중 취소 경합 | NOT_RUN | — |
| P113-07 | 실제 Discord 조작과 후보 복귀 | PARTIAL — 사용자 4개 화면 정상, 만료 선택 처음 FAIL/수정 확인; 복귀 미실행 | [1.1.3 기록](../../evidence/public/patch-113-development-20260928.md) |

## 1.1.4

[버전 계획·상세 통과 조건](1.1.4/README.md)

오류 주입·완료 이력/조회 회귀, 고정20영상×5 첫 PCM, 사용자 안내·최근곡 실제 조작/청취를 각각 기록한다.

| ID | 시험 시나리오 | 결과 | 새 실행 증거 |
| --- | --- | --- | --- |
| P114-01 | 지원 제외·resolver/네트워크/FFmpeg/PCM/음성 실패 주입 | PARTIAL | [안전 문구/기본 분류 회귀](../../evidence/public/patch-114-development-20260928.md); 전 구간 오류 주입 전 |
| P114-02 | 같은 고정20영상×5 첫 PCM | PASS — 첫 PCM95/100, 성공p95 4.458초; 실제 음성 별도 | [1.1.4 고정 후보 기록](../../evidence/public/patch-114-development-20260928.md) |
| P114-03 | 실제 안내와 준비/재생/권한/승인 만료 상태 | PARTIAL | [안전 문구 회귀](../../evidence/public/patch-114-development-20260928.md); 실제 실패 안내 전 |
| P114-04 | 완료·중단·실패·넘기기·반복·늦은 완료 callback | PARTIAL | [이력 조회/실패 분류 회귀](../../evidence/public/patch-114-development-20260928.md); 모든 경합 전 |
| P114-05 | 최근30일/최대100건·페이지·동일 제목·삭제된 곡 | PARTIAL | [조회 범위 회귀](../../evidence/public/patch-114-development-20260928.md); 전체 변형 전 |
| P114-06 | 최근곡 재요청·기존 목록 추가/제안 안내·DJ/음성 회수·버튼 재전송 | PARTIAL | [선택 구조 구현](../../evidence/public/patch-114-development-20260928.md); 실제 선택/권한 경합 전 |
| P114-07 | 실제 사용자 핵심 청취/안내와 후보 복귀 | NOT_RUN | 완료 이력이 없어 실제 최근곡 재생 미실행; 만료곡 선택 수정만 사용자 확인 |

## 1.1.5

[버전 계획·상세 통과 조건](1.1.5/README.md)

집계/권한·최소100회 합성 경합, 실제 역할/채널·취소·현재곡 보존, 전체 W 하위 조건과 복귀를 추적한다.

| ID | 시험 시나리오 | 결과 | 새 실행 증거 |
| --- | --- | --- | --- |
| P115-01 | 이력/사용량 조회·페이지·관리자 회수·다른 서버 | PARTIAL — 서버 분리/90일 mock·관리자 화면 정상; 실제 전체 권한 전 | [1.1.5 기록](../../evidence/public/patch-115-development-20260928.md) |
| P115-02 | 집계 API·인증/TLS·누락값·예산 귀속·서비스 장애 | PARTIAL — 인증/TLS 실조회, 공유 run 구분; 장애 전 | [1.1.5 기록](../../evidence/public/patch-115-development-20260928.md) |
| P115-03 | 요청자/타인 취소·공개 prefix 버튼·완료 직전·결과 유실·재전송100회 경합 | PARTIAL — 취소/커밋100회 DB 경합·사용자 본인 취소 성공, Discord 재전송/유실 전 | [1.1.5 기록](../../evidence/public/patch-115-development-20260928.md) |
| P115-04 | 주시2/미주시1·관리6명령·관리자/DJ/일반 사용자 | NOT_RUN | — |
| P115-05 | 채널 삭제/권한 회수·재연결·준비 중 제거·다른 출처 | NOT_RUN | — |
| P115-06 | 빈 목록/꺼짐 재시작·후보 교체·별도 복원/rollback | NOT_RUN | — |
| P115-07 | 실제 신규 조회/취소·11~20채널 페이지·혼합 부하 | NOT_RUN | — |

## 1.1.6

[버전 계획·상세 통과 조건](1.1.6/README.md)

개발/독립 자료와 채점기 회귀, prompt/threshold 비교, 잠근 독립200문장의 실제 Jev 평가를 분리한다.

| ID | 시험 시나리오 | 결과 | 새 실행 증거 |
| --- | --- | --- | --- |
| P116-01 | 개발/held-out 분리와 잠금 변조 | PARTIAL — SHA·구성·중복 검사, 변조 주입 전 | [1.1.6 기록](../../evidence/public/patch-116-development-20260928.md) |
| P116-02 | prompt 축약 기준/후보 비교 | PASS — 개발37/37 유지·실측 입력 token7.8% 감소; 운영 적용 전 | [1.1.6 기록](../../evidence/public/patch-116-development-20260928.md) |
| P116-03 | confidence/margin 비교 | PASS — 대안 이득0, 0.80/0.10 기준 유지 | [1.1.6 기록](../../evidence/public/patch-116-development-20260928.md) |
| P116-04 | 독립 최소 200문장 Jev 평가 | FAIL — 첫 잠금 명확103/120, 목표114/120 미달 | [1.1.6 기록](../../evidence/public/patch-116-development-20260928.md) |
| P116-05 | 권한·부정·주입·상태 경합 안전 | FAIL/PARTIAL — 합성 교란20 중 예상 밖 계획3, 실제 권한 경합 전 | [1.1.6 기록](../../evidence/public/patch-116-development-20260928.md) |
| P116-06 | 단계·usage·누적 예산 | PARTIAL — 개발87+잠금115dispatch·원장446/3000, 3단계/장애 전 | [1.1.6 기록](../../evidence/public/patch-116-development-20260928.md) |
| P116-07 | 선택 결과 재현·후보 복귀 | PARTIAL — wheel/자료 SHA 고정, 복귀/운영 축약 적용 전 | [1.1.6 기록](../../evidence/public/patch-116-development-20260928.md) |

## 1.1.7

[버전 계획·상세 통과 조건](1.1.7/README.md)

고정 후보의 실제 음성100회·경로별 성능·연속8시간, 장애 주입, 외부 암호화 백업 복원·TLS/재부팅·복귀를 구분한다.

| ID | 시험 시나리오 | 결과 | 새 실행 증거 |
| --- | --- | --- | --- |
| P117-01 | 고정 ≥20영상·준비 5회·실제 시작/전환 ≥100회 | FAIL/PARTIAL — `patch117a` 첫 PCM94/100 <95%; 최종 `patch117b`와 Discord 시작/전환/청취 미실행 | [1.1.7 기록](../../evidence/public/patch-117-development-20260928.md) |
| P117-02 | 고정 후보의 자연어 경로별 ≥100요청·구조화 제어 | NOT_RUN | — |
| P117-03 | 연속 ≥8시간 실제 음성·혼합 부하 | NOT_RUN | — |
| P117-04 | 네트워크·중계/봇 종료·DB 부족 장애 | NOT_RUN | — |
| P117-05 | 서버 외부 암호화 사본·격리 복원 | SKIPPED — 사용자 지정; 복구 PASS 아님 | [1.1.7 기록](../../evidence/public/patch-117-development-20260928.md) |
| P117-06 | 인증서 갱신·키/서비스·재부팅 | PARTIAL — TLS·키 분리·활성 서비스·14/7/1일 점검 PASS; 갱신/재부팅/경보 전 | [1.1.7 기록](../../evidence/public/patch-117-development-20260928.md) |
| P117-07 | 이전 바이너리/봇 DB 복귀와 최종 manifest | PARTIAL — 후보 wheel/manifest·원장446 유지; 복귀 미실행 | [1.1.7 기록](../../evidence/public/patch-117-development-20260928.md) |

## 1.1.8

[버전 계획](1.1.8/README.md) · [상세 통과 조건](1.1.8/04_lxc_evaluation.md) · [명령 전수 대응](1.1.8/COMMAND_COVERAGE.md)

47개 공개 명령·8개 상호작용의 의미/옵션 동등성, 새 독립 한국어 최소221문장, 관리자 비공개 결과·주시 복구·제한 문맥, Jev 비용/기한과 실제 Discord 조작을 구분한다. 현재 결과는 소스 개발 시험 일부이며 독립/전건 판정은 유지한다.

| ID | 시험 시나리오 | 결과 | 새 실행 증거 |
| --- | --- | --- | --- |
| P118-01 | C01~47·I01~08·공개 옵션 등록부/서비스 전수, slash/prefix 동등성 | PARTIAL — ID 등록부·주요 서비스 연결, 옵션/버튼 전수 전 | [개발 기록](../../evidence/public/patch-118-development-20260928.md) |
| P118-02 | 후보 포함률·정확한 인자·부정/인용/URL·신규 독립 최소221문장 | PARTIAL — 개발 예문 의도45/46·교란18/20; 독립/인자 미실행 | [개발 기록](../../evidence/public/patch-118-development-20260928.md) |
| P118-03 | 역할·음성·주시 on/off·제한 관리 복구·최신 출처/권한 | PARTIAL — 동적 버튼 출처/관리 lane 단위 회귀, 실제 Discord 전 | [개발 기록](../../evidence/public/patch-118-development-20260928.md) |
| P118-04 | 빠진 값 보충·선택/확인·취소·60초·중복/재시작·100회 경합 | PARTIAL — 텍스트 취소 회귀, typed continuation/경합 전 | [개발 기록](../../evidence/public/patch-118-development-20260928.md) |
| P118-05 | 관리자 비공개 열기·타인 클릭·페이지/첨부·입력/출력 정보 경계 | PARTIAL — 비공개 결과 버튼 소스 회귀, 타인/실제 응답 전 | [개발 기록](../../evidence/public/patch-118-development-20260928.md) |
| P118-06 | 구조화0회·1/2/조건부3단계·Jev 장애·token/지연 비교·전체 예산 | PARTIAL — 0/1/2단계 개발 호출,3단계/성능/최종 예산 전 | [개발 기록](../../evidence/public/patch-118-development-20260928.md) |
| P118-07 | 고정 후보의 실제 Discord 전수 명령/옵션/역할 인수·적용/복귀 | NOT_RUN | — |

## 기존 시험과의 회귀 연결

[기존 TEST_MATRIX](../0.DevPhase/TEST_MATRIX.md)의 기대 동작/하위 조건과 최초 책임 버전은 보존한다. 아래는 새 변경의 최소 영향 추적이며, 다른 공유 경로를 바꾸면 범위를 추가한다. 기존 번호를 새 번호로 대체하거나 과거 결과를 자동 승계하지 않는다.

| 새 버전 | 기존 회귀 ID | 연결 이유 |
| --- | --- | --- |
| 1.1.0 | W-03/09/10/12/15, C-05/08/10/14/16, T-03/04, N-11/19/21~34, B-04~11, O-02 | 동적 출처·단계·최신 권한·오류/계측·도움말 정보 경계 |
| 1.1.1 | B-04~11, N-16/17/26~36, C-14~16, W-10/15, O-01~03/08 | binding·수신/기한·연결/활성 슬롯·한도/오류·종료 |
| 1.1.2 | T-03~06, N-01~16/19~34, P-01~04/12, C-10~14, W-09~12 | 사전 권한·검색/대상·최소 조회·자동완성과 오래된 선택 |
| 1.1.3 | T-02/05~10/14/16/20, N-20/30/31/34, P-05~10/12, C-11/16, W-08/11~13 | 페이지·큐/목록 분리·선택/재승인·버튼·내보내기·상태 |
| 1.1.4 | Y-01~18, T-11~20, P-03/11, C-10/14, W-11/12, O-02/03 | 미디어 실패·지원 범위·완료 이력·최근곡 재요청·음성 보존 |
| 1.1.5 | W-01~20, C-05~11/14~18, B-06~11, N-18/19/27~35, O-02/05~08 | 전체 주시 수명·개인 응답·관리 집계·취소/커밋·원장/복귀 |
| 1.1.6 | N-01~36, B-01~12, C-12~17, W-09~12, T-04 | 의미/대상·부정/공격·명확화·단계 상한·독립 품질 |
| 1.1.7 | T-01~20, N-01~36, P-01~12, O-01~08, B-01~12, Y-01~18, C-01~18, W-01~20; 환경 변경 시 E-01~06 | 누적 후보의 최종 기능·성능·음성·운영 게이트 대조 |
| 1.1.8 | N-01~36, C-01~18, W-01~20, B-01~12 및 명령별 영향 T/P/Y/O | 전수 의도/인자·동적 출처·관리 복구/비공개·후속 문맥·취소·호출/기한 |

같은 후보의 유효한 증거를 여러 요구사항에 연결할 수 있지만, 다른 SHA/설정의 성적을 연결만으로 새로 통과시킬 수는 없다. 실제 인수 전 변경 영향과 증거 유효성을 검토한다.

## 선행·최종 판정

- 1.1.5의 주시 핵심 권한·출처·취소·재시작 회귀는 후속 평가의 선행이다. W-20 장시간/상속 게이트는1.1.7에서 확인하며, 그전까지 R-03 전체는 미완료일 수 있다. 이를 후속 버전 착수 금지로 해석하지 않는다.
- P114의 첫 PCM100회와 P117의 실제 음성100회는 다른 증거다. 개발37문장·결과를 본1.1.6의200문장·1.1.8의새 독립221문장 이상도 분리한다. 중단된 구간을 합쳐 연속8시간으로 세지 않는다.
- 무단/중복/취소 후 실행, 권한/서버 정보 노출, 원장/예산 감소, 확인 생략, 자동 재시도, TLS 우회가 있으면 해당 후보 인수를 중단한다.
- 유료 상한은 준비·실패·비교·독립 평가·성능·8시간을 합산한다. 예산 부족·실제 조작/청취 미확인·표본 부족은 미완료이며 한도 초기화나 표본 축소로 PASS 처리하지 않는다.
- 모든 시험을 완료해도 정식 VERSION/태그는 해당 고정 후보의 필수 인수와 출시 절차를 따른다. 이 계획 표는 출시 승인이나 실행 기록이 아니다.

[계열 목차](README.md) · [단계 상태](STATUS.md) · [공통 계약](EXECUTION_RULES.md)
