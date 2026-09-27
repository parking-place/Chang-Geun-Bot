# 제품 시험 디렉터리

| 경로 | 작성할 시험 |
| --- | --- |
| `unit/` | 도메인·권한·확인·후보/문맥·실행기 단위시험 |
| `integration/` | SQLite·봇/게이트웨이 계약·Discord/음성 연결 |
| `safety/` | 단계/호출 예산·중복·취소·기한·권한/상태 경쟁 |
| `fixtures/` | 합성·익명 카탈로그/후보/오류 fixture |
| `nlp_eval/` | 개발용/held-out 한국어 평가 세트와 채점기 |

현재 unit·SQLite/핸들러·API/원장·권한/확인·YouTube metadata·규칙 생성·편집 undo·복원 시험과 합성 한국어 개발 세트를 작성하고 지정 LXC에서 실행 중입니다. 실제 개인정보·운영 DB·키·접속 정보를 fixture로 커밋하지 않습니다.

모든 제품 시험은 지정 LXC에서 수행합니다. Jev API 실제 판단과 mock 증거를 별도로 기록하고 시험 run의 DB/큐·원장을 분리합니다. 과거 로컬 결과는 현재 출시 점수로 합산하지 않습니다. 개발 세트와 held-out 세트는 섞지 않습니다.

[시험 추적표](../Plans/0.DevPhase/TEST_MATRIX.md) · [증거 양식](../Plans/0.DevPhase/EVIDENCE_TEMPLATE.md) · [환경 계약](../Plans/0.DevPhase/ENVIRONMENT.md)
