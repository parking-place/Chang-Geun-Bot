# ReconstructionPhase — 자연어 해석 구조 재구성

사용자가 제공한 [해석기 설계서 v1.3](changgeun_jev_llm_fallback_command_parser_spec_v1.3.md)를 기준으로, 기존 기능과 데이터를 유지하면서 자연어 명령 처리 계층을 재구성한다.

| 버전 | 목표 | 단계 | 상태 |
| --- | --- | --- | --- |
| [1.2.0](1.2.0/README.md) | 보수적 정규화 → Jev → LLM rewrite → Jev 재해석 → LLM full fallback, 공통 검증·7일 로그 | 12 | PLANNED |

초기 LLM 프로필은 `gpt-5-nano`다. 이번 변경은 계획 문서 작성이며 구현·API 호출·LXC 적용·제품 VERSION/태그 변경이 아니다. 현재 Jev API 전용 실행과 요청당3회 계약은 실제 전환 전까지 유지한다. 새 설계의 공급자·호출 상한은 [결정0010](../../docs/decisions/0010-reconstruction-parser-plan.md)과 [1.2.0 아키텍처](1.2.0/ARCHITECTURE.md)에서 구분한다.

원본 명세는 수정하지 않는다. 계획에서 구체화한 저장소 배치·이관 계약·인수 기준은 명세의 참조 코드가 이미 구현됐다는 뜻이 아니다. 이전 [PatchPhase 상태](../1.PatchPhase/STATUS.md)와 실패·미완료·SKIPPED 기록은 계속 보존한다.
