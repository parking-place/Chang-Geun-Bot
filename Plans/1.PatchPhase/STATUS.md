# 1.1 계열 진행 현황

2026-09-28 사용자 요청으로1.1.0~1.1.7 계획을 작성했다. **8개 버전·40단계·26개 제안** 중 1.1.0·1.1.1 개발 후보가 진행 중이고, 1.1.2~1.1.7은 PLANNED다. [1.1.0](../../evidence/public/patch-110-development-20260928.md)·[1.1.1](../../evidence/public/patch-111-development-20260928.md) 부분 실행은 전체 인수/출시 PASS가 아니다. 기존1.0.3 개발 후보·과거 시험 상태는 [DevPhase STATUS](../0.DevPhase/STATUS.md)에 유지한다.

## 버전 상태

| 버전 | 전체 책임 ID | 상태 | VERIFIED/DONE 단계 | 새 제품 실행 |
| --- | --- | --- | --- | --- |
| [1.1.0](1.1.0/README.md) | R-01, J-01, R-08, F-01 | IN_PROGRESS | 0 / 5 | [소스/wheel373 PASS·개발37/37·적용](../../evidence/public/patch-110-development-20260928.md); 실제 전건 인수 전 |
| [1.1.1](1.1.1/README.md) | J-02, J-03, J-08 | IN_PROGRESS | 0 / 5 | [소스/wheel378 PASS·중계42 PASS·개발37/37·적용](../../evidence/public/patch-111-development-20260928.md); 실제 전건 인수 전 |
| [1.1.2](1.1.2/README.md) | J-04, J-05, J-06, F-06 | PLANNED | 0 / 5 | NOT_RUN |
| [1.1.3](1.1.3/README.md) | F-02, F-03, F-05 | PLANNED | 0 / 5 | NOT_RUN |
| [1.1.4](1.1.4/README.md) | R-02, F-04, F-09 | PLANNED | 0 / 5 | NOT_RUN |
| [1.1.5](1.1.5/README.md) | F-07, F-08, R-03 | PLANNED | 0 / 5 | NOT_RUN |
| [1.1.6](1.1.6/README.md) | J-07, J-09, R-04 | PLANNED | 0 / 5 | NOT_RUN |
| [1.1.7](1.1.7/README.md) | R-05, R-06, R-07 | PLANNED | 0 / 5 | NOT_RUN |

## 단계 상태

각 버전 README의5단계와 같은 순서를 사용한다. 실제 단계별 증거가 생기면 해당 칸의 상태와 보고서 링크를 함께 갱신한다.

| 버전 | 01 설계 | 02 구현 | 03 안전 회귀 | 04 LXC 검증 | 05 개발 인수·복귀 |
| --- | --- | --- | --- | --- | --- |
| [1.1.0](1.1.0/README.md) | IN_PROGRESS | IN_PROGRESS | IN_PROGRESS | IN_PROGRESS | PLANNED |
| [1.1.1](1.1.1/README.md) | IN_PROGRESS | IN_PROGRESS | IN_PROGRESS | IN_PROGRESS | PLANNED |
| [1.1.2](1.1.2/README.md) | PLANNED | PLANNED | PLANNED | PLANNED | PLANNED |
| [1.1.3](1.1.3/README.md) | PLANNED | PLANNED | PLANNED | PLANNED | PLANNED |
| [1.1.4](1.1.4/README.md) | PLANNED | PLANNED | PLANNED | PLANNED | PLANNED |
| [1.1.5](1.1.5/README.md) | PLANNED | PLANNED | PLANNED | PLANNED | PLANNED |
| [1.1.6](1.1.6/README.md) | PLANNED | PLANNED | PLANNED | PLANNED | PLANNED |
| [1.1.7](1.1.7/README.md) | PLANNED | PLANNED | PLANNED | PLANNED | PLANNED |

## 판정 규칙

기존 [상태 정의](../0.DevPhase/STATUS.md)를 따른다. 작업 착수 시 IN_PROGRESS, 소스 준비 후 지정 LXC 검증 전에는 CODE_READY로 표시할 수 있다. 계획만 작성한 현재 상태는 PLANNED다.

VERIFIED는 해당 단계 필수 LXC 증거가 있을 때만, DONE은 버전의 필수 게이트까지 충족했을 때만 사용한다. FAIL/SKIPPED/NOT_RUN은 실행 결과로 구분한다. 자동시험·실제 API·사람의 조작/청취를 합쳐 하나의 PASS로 표시하지 않는다.

최적화 비교가 실제로 완료됐지만 채택 이득이 없으면 결과란에 `검토 완료·기준 유지`와 근거를 기록한다. 이를 적용 성공 또는 미실행의 대체 판정으로 쓰지 않는다. 신규 기능의 제외/버전 이동은 [배정표](ITEM_COVERAGE.md)와 사유를 함께 갱신한다.

## 현재 남은 선행 조건

- R-01 격리 다후보 재현·수정 뒤 조건부3단계/실제 역할·취소 경로 인수
- 1.1.0 계측의 실제 Discord·장애 분모와 비교 기준, 개발/독립 데이터 분리
- 당시 미디어93/100 FAIL의 원인 분류, 전체 W·한국어·실제 음성/8시간·복구 인수
- 현재 배포의 제한 설정/인증서/원장 잔여예산 재확인 — 실제 착수 시 수행

위 항목은 지금 새로 실패하거나 장애가 발생했다고 확인한 결과가 아니라 기존 기록과 새 계획의 미실행 작업이다.

[로드맵](README.md) · [공통 계약](EXECUTION_RULES.md) · [전체 배정](ITEM_COVERAGE.md) · [시험 추적](TEST_MATRIX.md)
