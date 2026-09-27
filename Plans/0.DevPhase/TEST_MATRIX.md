# 시험 책임과 요구사항 추적표

상태: 부분 구현·시험 진행 중; 개별 전건 인수 전. 기준은 [명세 §17](../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md#s17)이다. T/N 번호와 의미를 유지하고, 명세 번호가 없는 환경·P1·운영 시험은 이 계획의 E/P/O/B 보충 ID로 구분한다. 2026-09-28 후속 범위에 1.0.1의 Y·1.0.2의 C·1.0.3의 W 시험을 연결했다. Y/C는 아래 공개 기록의 부분 회귀와 전체 인수를 구분하며, W-01~20은 자동 회귀의 부분 증거와 전체 실제 인수를 구분한다.

표의 버전은 최초 책임 버전이다. 실제 판정은 [STATUS](STATUS.md)와 LXC 보고를 따른다. 도메인/mock·실제 Discord·Jev API 품질 증거를 구분한다. [전용 계약](INFERENCE_PROFILES.md)에 따라 실제 자연어 제공자는 jev-api 하나이며 gateway/원장은 현재 DiscordBotLXC의 별도 중계 계정에 둔다. [배치 결정0008](../../docs/decisions/0008-single-lxc-jev-api.md)을 적용하며 과거 두 서버 결과는 당시 증거로 보존한다. 내부 forward는 null/unavailable이다. B 번호는 유지하면서 2026-09-27 전용 범위로 기대 동작을 개정했다.

## 환경 선행 시험 E

| ID | 기대 동작 | 최초 책임 버전 / 단계 | 검증 서버 |
| --- | --- | --- | --- |
| E-01 | 소스revision/manifest 일치, 비밀·DB·캐시 동기화 제외 | [0.0.0](0.0.0/README.md) / 02·05 | DiscordBotLXC(봇·중계) |
| E-02 | 원격 runner만 실행, 잘못된 호스트 거절·로컬fallback 없음 | [0.0.0](0.0.0/README.md) / 02·05 | DiscordBotLXC(봇·중계) |
| E-03 | OS/자원/시간/비root 서비스계정·쓰기경로 실측 | [0.0.0](0.0.0/README.md) / 03 | DiscordBotLXC(봇·중계) |
| E-04 | 테스트/운영 토큰·DB·원장·채널·서비스 분리 | [0.0.0](0.0.0/README.md) / 03 | DiscordBotLXC(봇·중계) |
| E-05 | DAVE·UDP·승인음원 초기탐색, 정식소스 인수는0.3.0 | [0.0.0](0.0.0/README.md) / 04 | DiscordBotLXC |
| E-06 | Jev API 연결·한국어 탐색·단일dispatch/forward 미관측; 정식API 인수는0.5.0 | [0.0.0](0.0.0/README.md) / 04 | DiscordBotLXC(중계) |

## 제공자 선택·전환 보충 시험 B

아래 표는 기대 동작이며 부분 결과는 실행 기록을 따른다. 0.0.0은 계약·mock/기술 탐색만 담당하고 0.5.0 이후 실제 Jev API 인수로 완성한다. 재시작·한도·오류 주입은 격리된 LXC 시험에서 수행한다.

| ID | 기대 동작 | 최초 책임 버전 / 단계 | 적용 |
| --- | --- | --- | --- |
| B-01 | jev-api만 실제 활성화·mock은명시회귀전용; 비지원provider/선택누락거절·dry-run호출0·fallback0 | 0.0.0/02 설계; 0.5.0/01·05 인수 | Jev API + 지정 LXC 회귀 |
| B-02 | Jev API 필수값검사·local/혼용설정거절·내부/외부키분리·누락은호출전거절·secret출력0 | 0.0.0/03; 0.5.0/01 | Jev API + 지정 LXC 회귀 |
| B-03 | Jev API candidate에 torch/transformers/OpenJev·가중치 없이 설치/기동; 모델 준비 불필요 | 0.0.0/04 탐색; 0.5.0/02 | Jev API + 지정 LXC 회귀 |
| B-04 | API1.2 provider/profile/config 일치, 후보·확률·스키마 정규화, 잘못된 응답 미실행 | 0.5.0/01·02·05 | DiscordBotLXC(봇·중계) |
| B-05 | 3단계·질문3·dispatch≤3·Jev API forward 두 값=null/source=unavailable | 0.5.0/02·03 | Jev API + 지정 LXC 회귀 |
| B-06 | SDK/HTTP retry0, 429/5xx/응답유실 뒤 새전송0, 원장중복/크래시불명 재실행0 | 0.5.0/02·03·05 | DiscordBotLXC(봇·중계) + 주입 |
| B-07 | 동일deadline·timeout/취소/후발결과미실행·transport종료전슬롯유지·외부계산취소미보장 | 0.5.0/04; 0.8.0/01 | Jev API + 지정 LXC 회귀 |
| B-08 | 요청중설정변경/mismatch거절·후보배포drain/새세대·이전ID/확인재사용0·복원/rollback tombstone보존 | 0.5.0/03·05; 0.8.0/02·03·05 | Jev API + 지정 LXC 회귀 |
| B-09 | run별DB/큐/원장/logs/evidence격리·fixture/snapshot독립복제·실제Discord중복변경0 | 0.0.0/02·03 설계; 0.5.0/05·0.6.0/05 | Jev API + 지정 LXC 회귀 |
| B-10 | Jev API readiness·health유료호출0·미기동/인증/한도장애에도구조화/재생유지 | 0.5.0/05; 0.8.0/05 | Jev API + 지정 LXC 회귀 |
| B-11 | 합성/익명최소입력·키/ID미송신·HTTPS/redirect통제·run한도원자예약·준비/실패포함·초과차단 | 0.5.0/02·05; 0.8.0/04 | Jev API + 지정 LXC 회귀 |
| B-12 | 고정Jev API 후보의개발/held-out/성능/manifest분리·미공개revision표시·mock/과거local점수합산0 | 0.6.0/05; 0.9.0/01·03·04; 1.0.0/01·04 | Jev API + 지정 LXC 회귀 |

## 명세 핵심 기능 시험 T

| ID | 기대 동작 | 최초 책임 버전 / 단계 | 검증 서버 |
| --- | --- | --- | --- |
| T-01 | 빈 목록 생성 후 재시작 복원 | [0.2.0](0.2.0/README.md) | DiscordBotLXC |
| T-02 | 곡3개 추가·이동·1개 제거의 정확한 결과 | [0.2.0](0.2.0/README.md) | DiscordBotLXC |
| T-03 | 비DJ 슬래시 추가 거절·변경 없음 | [0.2.0](0.2.0/README.md) | DiscordBotLXC |
| T-04 | 비DJ 자연어 제거 거절·실행 없음 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| T-05 | 비DJ DJ용 공개버튼 클릭 거절 | [0.2.0](0.2.0/README.md) | DiscordBotLXC |
| T-06 | 기본중복 거절·명시허용에서만 새entry | [0.2.0](0.2.0/README.md); 큐[0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-07 | 큐 셔플 뒤 저장목록 순서 불변 | [0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-08 | 저장목록 제거가 이미복사된큐/현재곡에 영향없음 | [0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-09 | 대기열 저장의 현재곡 포함/제외 범위 | [0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-10 | 이름충돌 자동덮어쓰기 금지 | [0.2.0](0.2.0/README.md); 큐저장[0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-11 | 요청자 채널에서 /재생 실제 입장·음성 | [0.4.0](0.4.0/README.md); 소스선행[0.3.0](0.3.0/README.md) | DiscordBotLXC |
| T-12 | 요청자채널/명시채널 없으면 임의입장 금지 | [0.3.0](0.3.0/README.md) | DiscordBotLXC |
| T-13 | 재생중 다른채널 이동은 중단안내·확인 | [0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-14 | 정지→계속, 중복 없이 항목 처음부터 | [0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-15 | 퇴장 뒤 늦은 검색결과 재입장/재생 없음 | [0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-16 | 한곡반복에서 수동스킵한 항목 즉시반복 없음 | [0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-17 | 자동퇴장 직전 청취자 입장시 타이머 취소 | [0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-18 | 3곡연속 실패시 무한스킵 없이 중단 | [0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-19 | 관리자 강제퇴장 후 자동재입장 없음 | [0.4.0](0.4.0/README.md) | DiscordBotLXC |
| T-20 | 재시작 복원·확인무효화·자동음성재개 없음 | [0.4.0](0.4.0/README.md); DB선행[0.1.0](0.1.0/README.md)/[0.2.0](0.2.0/README.md) | DiscordBotLXC |

## 명세 자연어·안전 회귀 N

| ID | 기대 동작 | 최초 책임 버전 / 단계 | 검증 서버 |
| --- | --- | --- | --- |
| N-01 | 등록 노동요 목록 재생, 실제권한 적용 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-02 | 실제 현재곡ID를 실제목록에 추가 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-03 | 스냅샷3번째 큐entry 제거 미리보기·확인 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-04 | 이 곡 빼지 마 → 제거 없음 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-05 | 삭제하지 말고 맨 뒤로 → 이동만 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-06 | 틀지 말고 목록만 → 조회만 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-07 | 감상문에서 스킵·제거 없음 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-08 | 문맥만료된 아까 그거 → 대상확인 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-09 | 다른사용자의 직전문맥 혼합 없음 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-10 | 같은별칭 두곡은 선택메뉴 | [0.6.0](0.6.0/README.md); 별칭확장[0.7.0](0.7.0/README.md) | DiscordBotLXC(봇·중계) |
| N-11 | DJ라고 주장해도 실제역할로 거절 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-12 | 제목/문맥 프롬프트주입은 데이터 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-13 | 지원밖 복합명령은 확인/분리안내 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-14 | 3단계 불명확 뒤 네번째추론 없음 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-15 | 긴입력 끝의 부정어를 잘라 실행하지 않음 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-16 | 후보밖ID·NaN·깨진응답 안전실패 | [0.5.0](0.5.0/README.md); 봇실행[0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-17 | Jev 꺼짐/지연/OOM에도 기존재생·슬래시 유지 | [0.6.0](0.6.0/README.md); 장애심화[0.8.0](0.8.0/README.md) | DiscordBotLXC(봇·중계) |
| N-18 | 중복수신은 변경1회·모델단계 재실행 없음 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-19 | 추론중 DJ해임 뒤 실행거절 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-20 | 추론/확인중 큐변경 후 다른번호 항목 오수정 없음 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-21 | 1단계+규칙 확정은 모델1회만 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-22 | 2단계 확정은 모델2회만 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-23 | 유효문맥 근거의 남은범위만 조건부3단계 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-24 | 1/2단계 clarify 뒤 추가추론 없음 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-25 | 사용자근거 없으면3단계 추측 대신 메뉴 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-26 | stage0/4·stage/task불일치 모델전 400/422 | [0.5.0](0.5.0/README.md) | DiscordBotLXC(중계) |
| N-27 | 같은3단계 중복은 기존결과/진행합류·provider누계≤3 | [0.5.0](0.5.0/README.md) | DiscordBotLXC(중계) |
| N-28 | 3단계 시작 잔여시간 부족하면 미호출 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-29 | 3단계 기한초과·늦은 결과 미실행 | [0.5.0](0.5.0/README.md); 봇실행[0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-30 | 3단계 뒤 DJ/현재곡/대상버전 재검증 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-31 | 고점수3단계 삭제도 확인필수 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-32 | 앞행동 충돌/후보외3단계 결과 미실행 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-33 | 1→3 건너뛰기/병렬후속의 원자순서·예산차단 | [0.5.0](0.5.0/README.md) | DiscordBotLXC(중계) |
| N-34 | 3단계 뒤 UI선택은 추가모델 없이 재검증 | [0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |
| N-35 | 재시작 뒤 실행불명 요청 재실행 금지 | [0.5.0](0.5.0/README.md) | DiscordBotLXC(중계) |
| N-36 | 숨은번역/검수/다중질문·추가dispatch는 readiness/출시차단 | [0.5.0](0.5.0/README.md); 통합[0.6.0](0.6.0/README.md) | DiscordBotLXC(봇·중계) |

## 편의 기능 보충 시험 P

| ID | 기대 동작 | 최초 책임 버전 / 단계 | 검증 서버 |
| --- | --- | --- | --- |
| P-01 | 원문보존·검색정규화·태그/별칭guild격리 | [0.7.0](0.7.0/README.md) / 01 | DiscordBotLXC |
| P-02 | 동명별칭 메뉴·비DJ 분류변경 차단 | [0.7.0](0.7.0/README.md) / 01 | DiscordBotLXC(봇·중계) |
| P-03 | 동일seed/snapshot 선택재현·영상중복/태그/최근/길이필터 | [0.7.0](0.7.0/README.md) / 02 | DiscordBotLXC |
| P-04 | 후보부족·20곡확인·100곡생성상한·최신버전 | [0.7.0](0.7.0/README.md) / 02 | DiscordBotLXC(봇·중계) |
| P-05 | 일반제안은큐/목록불변·DJ승인만추가 | [0.7.0](0.7.0/README.md) / 03 | DiscordBotLXC |
| P-06 | 동시/재전송 승인1회·DJ해제/대상삭제시거절 | [0.7.0](0.7.0/README.md) / 03 | DiscordBotLXC |
| P-07 | 가져오기페이지·부분실패·500상한·미리보기 | [0.7.0](0.7.0/README.md) / 04 | DiscordBotLXC |
| P-08 | JSON왕복·복사독립·secret제외·덮어쓰기확인 | [0.7.0](0.7.0/README.md) / 04 | DiscordBotLXC |
| P-09 | undo 기대version·충돌거절·역변경1회 | [0.7.0](0.7.0/README.md) / 05 | DiscordBotLXC |
| P-10 | 삭제목록 복원명충돌·30일/삭제의무 우선 | [0.7.0](0.7.0/README.md) / 05 | DiscordBotLXC |
| P-11 | 불가곡점검해도목록보존·실제최근재생제외 | [0.7.0](0.7.0/README.md) / 05 | DiscordBotLXC |
| P-12 | 새action의 슬래시/버튼/NL 동일권한·확인·≤3 | [0.7.0](0.7.0/README.md) / 05 | DiscordBotLXC(봇·중계) |

## 운영 보충 시험 O

| ID | 기대 동작 | 최초 책임 버전 / 단계 | 검증 서버 |
| --- | --- | --- | --- |
| O-01 | systemd 비root·쓰기제한·정상종료·재시작제한 | [0.8.0](0.8.0/README.md) | DiscordBotLXC(봇·중계) |
| O-02 | 로그/오류/export secret·원문·서명URL 제거 및보존삭제 | [0.8.0](0.8.0/README.md) | DiscordBotLXC(봇·중계) |
| O-03 | Jev/API/음성네트워크 단절·OOM/강제종료 격리 | [0.8.0](0.8.0/README.md) | DiscordBotLXC(봇·중계) |
| O-04 | 테스트DB 디스크부족·쓰기실패 원자복구 | [0.8.0](0.8.0/README.md) | DiscordBotLXC |
| O-05 | 일관성온라인백업·일일7/주간4·노드밖사본 | [0.8.0](0.8.0/README.md) | DiscordBotLXC |
| O-06 | 격리실제복원·무결성/순서/권한/중복·자동재생없음 | [0.8.0](0.8.0/README.md); RC0.9.0 | DiscordBotLXC(봇·중계) |
| O-07 | 호환성확인된 앱/DB/모델 롤백, 검증없는역마이그레이션금지 | [0.8.0](0.8.0/README.md); 출시[1.0.0](1.0.0/README.md) | DiscordBotLXC(봇·중계) |
| O-08 | URL/redirect/DNS·인자배열·TLS/인증/출발지제한·privileged잔여위험 | [0.8.0](0.8.0/README.md); 소스/API선행[0.3.0](0.3.0/README.md)/[0.5.0](0.5.0/README.md) | DiscordBotLXC(봇·중계) |

## 공통 최종 회귀와 평가

- 0.9.0에서 T-01~20, N-01~36, P-01~12, O-01~08, B-01~12 전체를 동일 출시 후보로 확인한다. E는 환경/revision 변경 시 재확인한다.
- Jev API의 한국어 최종 평가 최소200문장과 경로별100회 성능, 최소8시간 혼합재생, 백업/복원은 별도 실행 보고서로 관리한다. N 시험만 통과했다고 한국어95%를 달성한 것으로 세지 않는다.
- 1.0.0 배포 후 실제 지원 핵심경로의 smoke와 후보 manifest 일치를 확인한다. 변경이 발생하면 영향을 받은 시험과 필요한 장시간시험을 다시 수행한다.
- 목표·표본·시간 조건은 [출시 기준](RELEASE_CRITERIA.md)을 사용한다. 각 시나리오에 [실행 증거](EVIDENCE_TEMPLATE.md)가 있어야 하며 skip·미실행은 PASS가 아니다.


## 후속 1.0.1 YouTube 직접 재생 Y

상태: 공개 기록의 부분 구현/회귀가 있으며 개별 전건 인수는 완료 전이다. 버전 계획의 세부 표본·오류·기한 조건을 함께 적용한다.

| ID | 기대 동작 | 최초 책임 버전 / 단계 | 검증 서버 |
| --- | --- | --- | --- |
| Y-01 | 승인 매핑 없는 지원 공개 영상의 실제 오디오 획득·DAVE 청취, 기술/운영 채택 증거 구분 | [1.0.1](1.0.1/README.md) / 01 | DiscordBotLXC |
| Y-02 | 메타데이터와 실제 재생 가능 상태 구분·지원 제한/오류 안내 | [1.0.1](1.0.1/README.md) / 01 | DiscordBotLXC |
| Y-03 | extractor/FFmpeg/JS/EJS 고정 버전·hash·격리 의존성·사용 조건 | [1.0.1](1.0.1/README.md) / 01 | DiscordBotLXC |
| Y-04 | YouTube URL 정규화·잘못된 주소 거절·list 포함 영상URL 단일곡 처리 | [1.0.1](1.0.1/README.md) / 02 | DiscordBotLXC |
| Y-05 | DNS/redirect/manifest/후속CDN까지 egress·사설주소·임의프로토콜 차단 | [1.0.1](1.0.1/README.md) / 02 | DiscordBotLXC |
| Y-06 | 동시1/대기4·준비총25초·누적해석15초/시작10초·취소/자원회수 | [1.0.1](1.0.1/README.md) / 02 | DiscordBotLXC |
| Y-07 | signed URL/헤더/비밀의 메모리수명·DB/로그/argv/백업 비노출 | [1.0.1](1.0.1/README.md) / 02 | DiscordBotLXC |
| Y-08 | 고정후보 재현·무쿠키/무자동업데이트·승인음원 resolver 회귀 | [1.0.1](1.0.1/README.md) / 02 | DiscordBotLXC |
| Y-09 | 링크/공식검색 사용자선택/저장목록 실제재생·구조화 Jev0회 | [1.0.1](1.0.1/README.md) / 03 | DiscordBotLXC |
| Y-10 | 혼합큐·순서·pause/resume/stop/skip/repeat/leave·저장목록 불변 | [1.0.1](1.0.1/README.md) / 03 | DiscordBotLXC |
| Y-11 | DJ/동일음성/역할해임/타인버튼/낡은확인·큐경쟁에서 무단실행0 | [1.0.1](1.0.1/README.md) / 03 | DiscordBotLXC |
| Y-12 | 목록URL·대량확인·불가항목미리보기/부분추가확인·취소0변경·참조보존 | [1.0.1](1.0.1/README.md) / 03 | DiscordBotLXC |
| Y-13 | 만료/403/429/5xx/유실·추가시도≤1·영구오류0retry·3연속실패 중단 | [1.0.1](1.0.1/README.md) / 04 | DiscordBotLXC |
| Y-14 | 해석/재생중 취소·skip/퇴장/해임·늦은결과와 고아프로세스0 | [1.0.1](1.0.1/README.md) / 04 | DiscordBotLXC |
| Y-15 | entry소유권/큐/확인·재시작/복원/기능off/rollback·자동재생0 | [1.0.1](1.0.1/README.md) / 04 | DiscordBotLXC |
| Y-16 | 부하·자원부족·gateway장애·로그/비밀 회귀·기존조작 유지 | [1.0.1](1.0.1/README.md) / 04 | DiscordBotLXC(봇·중계) |
| Y-17 | 영상≥20개·시작/전환≥100회·준비5·성공≥95%·첫오디오p95≤10초·실제청취 | [1.0.1](1.0.1/README.md) / 05 | DiscordBotLXC |
| Y-18 | 신규소스 연속8시간·혼합부하·고정후보 배포/smoke/off/rollback | [1.0.1](1.0.1/README.md) / 05 | DiscordBotLXC(봇·중계) |

## 후속 1.0.2 지정 채널 접두어 명령 C

상태: 공개 기록의 부분 구현/회귀가 있으며 개별 전건 인수는 완료 전이다. 버전 계획의 세부 표본·오류·기한 조건을 함께 적용한다.

| ID | 기대 동작 | 최초 책임 버전 / 단계 | 검증 서버 |
| --- | --- | --- | --- |
| C-01 | prefix 설정·공통채널부분집합·비활성기본·잘못된/변경채널·세대 | [1.0.2](1.0.2/README.md) / 01 | DiscordBotLXC(봇·중계) |
| C-02 | 실제 멘션없는 Message Content Intent·Portal/코드·실패진단/기존기능복구 | [1.0.2](1.0.2/README.md) / 01 | DiscordBotLXC(봇·중계) |
| C-03 | 정확한 선두호출어·ASCII구분자·Unicode/인용/개행·혼합호출 문법 | [1.0.2](1.0.2/README.md) / 02 | DiscordBotLXC(봇·중계) |
| C-04 | 빈본문/1/500/501자·부정어보존·빈/초과입력 Jev0회 | [1.0.2](1.0.2/README.md) / 02 | DiscordBotLXC(봇·중계) |
| C-05 | guild/channel/thread/DM/bot/webhook/system 필터·거절Jev0/DB변경0 | [1.0.2](1.0.2/README.md) / 01·02 | DiscordBotLXC(봇·중계) |
| C-06 | 수정/삭제/bulkdelete·관측된커밋전취소·재해석/커밋후자동undo0 | [1.0.2](1.0.2/README.md) / 02 | DiscordBotLXC(봇·중계) |
| C-07 | 영속message→request결합·동시중복/Resume/재시작/복원·효과1회 | [1.0.2](1.0.2/README.md) / 02 | DiscordBotLXC(봇·중계) |
| C-08 | 슬래시/멘션/prefix 분리·혼합입력 이중라우팅0·기존입력회귀 | [1.0.2](1.0.2/README.md) / 02 | DiscordBotLXC(봇·중계) |
| C-09 | 최소본문/익명후보 외부전송·비허용대화 미저장·TTL/보존/복원 | [1.0.2](1.0.2/README.md) / 04 | DiscordBotLXC(봇·중계) |
| C-10 | 실제 DJ/역할해임/음성/채널·대상버전·실행직전재검증 | [1.0.2](1.0.2/README.md) / 03 | DiscordBotLXC(봇·중계) |
| C-11 | 공개확인·타인/중복/만료버튼·원문삭제·확인60초·위험실행0 | [1.0.2](1.0.2/README.md) / 03 | DiscordBotLXC(봇·중계) |
| C-12 | 고정필수 한국어행동표·정답action/대상/인자·미지원분리안내 | [1.0.2](1.0.2/README.md) / 03 | DiscordBotLXC(봇·중계) |
| C-13 | guild/channel/user 문맥격리·120초TTL·대상변경·근거있는참조 | [1.0.2](1.0.2/README.md) / 03 | DiscordBotLXC(봇·중계) |
| C-14 | Jev3단계/3dispatch·12초/4초·조기종료·취소/예산·늦은결과0 | [1.0.2](1.0.2/README.md) / 03 | DiscordBotLXC(봇·중계) |
| C-15 | 복수채널 사용자cooldown/동시성/대기상한·음성부하·429/비용한도 | [1.0.2](1.0.2/README.md) / 04 | DiscordBotLXC(봇·중계) |
| C-16 | 공개응답1개갱신·ephemeral오인0·전송불명/삭제/권한회수·재실행0 | [1.0.2](1.0.2/README.md) / 04 | DiscordBotLXC(봇·중계) |
| C-17 | 독립≥200문장·명확≥120/95%·안전실패0·개발세트분리·경로성능 | [1.0.2](1.0.2/README.md) / 05 | DiscordBotLXC(봇·중계) |
| C-18 | 실제허용채널≥2/미허용1·DJ/nonDJ·소스연계·연속8시간·배포/rollback | [1.0.2](1.0.2/README.md) / 05 | DiscordBotLXC(봇·중계) |

## 후속 구현의 검증 범위

[Y/C 개발 후보 증거](../../evidence/public/youtube-prefix-20260928.md)에 단위/mock·실제 Jev·첫 PCM·실제 채팅을 구분해 기록한다. Y-04~11/14와 C-01~08/10~16에 대한 부분 회귀가 있으나 각각의 전체 필수 조건 PASS를 뜻하지 않는다. Y-12 부분목록 미리보기·Y-17 실제 Discord 100회/청취·Y-18 신규소스8시간, C-17 독립200문장·C-18 두 채널의 전체 사용자 인수/rollback은 완료 전이다. 이전 후보의 93/100 미디어 결과는 실패 기록으로 유지한다.

## 1.0.3 주시 채널 관리 W

상태: **IN_PROGRESS — 개발 적용·자동 회귀·관리 동작 사용자 부분 PASS, 전체 W 인수 미완료**. [새 증거](../../evidence/public/watch-channels-20260928.md)의 W 매핑과 미실행 범위를 따른다. 단위/mock 통과를 실제 사용자·청취·장시간 시험 PASS로 승격하지 않는다.

| ID | 기대 동작 | 최초 책임 버전 / 단계 | 검증 서버 |
| --- | --- | --- | --- |
| W-01 | 관리6명령·채널 선택/생략·no-op·길드 전용·개인 응답·Jev0 | [1.0.3](1.0.3/README.md) / 01 | DiscordBotLXC + 원장 대조 |
| W-02 | 소유자/Manage Guild·DJ 단독 거절·최신 권한/확인·조회 실패/해임 거절 | [1.0.3](1.0.3/README.md) / 01 | DiscordBotLXC |
| W-03 | 미주시/공통 목록 밖 관리 복구·일반 슬래시/멘션 권한 확대0 | [1.0.3](1.0.3/README.md) / 01 | DiscordBotLXC |
| W-04 | 일반 텍스트/동일 이름 ID·유형/guild 거절·삭제된 등록 채널 제거 | [1.0.3](1.0.3/README.md) / 01 | DiscordBotLXC |
| W-05 | 초기1회 이관·빈 목록/꺼짐·재시작/후보 변경·기존 SQL 보존 | [1.0.3](1.0.3/README.md) / 02 | DiscordBotLXC |
| W-06 | 관리자 동시성·revision/확인 충돌·no-op·중복 interaction 변경1회 | [1.0.3](1.0.3/README.md) / 02 | DiscordBotLXC |
| W-07 | 커밋 전/후 crash·응답 유실·DB/캐시/이관 실패·이관 전 변경 차단 일관성 | [1.0.3](1.0.3/README.md) / 02 | DiscordBotLXC |
| W-08 | guild·20개 한도·제거/재등록 세대·기존 승인 출처/재승인·다른 설정과 독립·과거 승인 부활0 | [1.0.3](1.0.3/README.md) / 02 | DiscordBotLXC |
| W-09 | prefix 전용 동적 정책·원장 출처·가짜 origin/자식 요청 권한 우회0 | [1.0.3](1.0.3/README.md) / 03 | DiscordBotLXC |
| W-10 | dispatch/확인/등록/커밋 경합·제거/끄기 후 미커밋 효과0·추가 호출0 | [1.0.3](1.0.3/README.md) / 03 | DiscordBotLXC(봇·중계) |
| W-11 | 미디어 준비/시작 경합·만료 큐 보존/제외·현재곡·반복·다른 출처 보존 | [1.0.3](1.0.3/README.md) / 03 | DiscordBotLXC |
| W-12 | 삭제/권한/재등록/켜기/재연결/복원·낡은 정책 실행0·일반 조작 유지 | [1.0.3](1.0.3/README.md) / 03 | DiscordBotLXC |
| W-13 | 개인 응답·예상/실제 영향 수·확인 중 새 요청·마지막 제거·꺼짐 중 추가·오래된 버튼/페이지 | [1.0.3](1.0.3/README.md) / 04 | DiscordBotLXC |
| W-14 | 점검 생략/권한 부족·채널별 상태/실패 격리·역할/재접속·운영자 off/Intent 장애·Portal 우회0 | [1.0.3](1.0.3/README.md) / 04 | DiscordBotLXC |
| W-15 | Jev 장애/예산0에서 관리·dispatch0·원문/키/토큰 비노출·감사 보존 | [1.0.3](1.0.3/README.md) / 04 | DiscordBotLXC(봇·중계) |
| W-16 | 20/21개·페이지·cooldown·점검 상한·403/429/유실·중복 변경0 | [1.0.3](1.0.3/README.md) / 04 | DiscordBotLXC |
| W-17 | 실제 주시2/미주시1·관리자/DJ/일반·6명령·반응 설정 전후 | [1.0.3](1.0.3/README.md) / 05 | DiscordBotLXC + 실제 사용자 |
| W-18 | 고정 후보 재시작/교체·영속 상태/세대·음성/권한 영향 회귀 | [1.0.3](1.0.3/README.md) / 05 | DiscordBotLXC(봇·중계) |
| W-19 | 별도 DB 복원·이전 바이너리/DB 묶음 rollback·원장/예산 보존 | [1.0.3](1.0.3/README.md) / 05 | DiscordBotLXC(봇·중계) |
| W-20 | 합성 경합≥100·실제 부하/장시간 영향·도움말/문서·앞선 필수 게이트 | [1.0.3](1.0.3/README.md) / 05 | DiscordBotLXC(봇·중계) |
