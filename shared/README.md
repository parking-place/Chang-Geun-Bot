# 공통 계약

[API 1.2 명세](../Plans/CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md#s09)의 공개 계약:

- [판단 요청 JSON Schema](schemas/decision-request-1.2.json)
- [판단 응답 JSON Schema](schemas/decision-response-1.2.json)

엄격한 Pydantic 계약에서 지정 LXC의 `scripts/export_schemas.py`로 생성한다. 필드 간 단계/task 관계, 후보 집합·확률, 누적 예산·프로필 결합은 JSON Schema에 더해 런타임 검사로 강제한다. 스키마 파일 생성은 실제 제공자 품질·전체 API 인수를 의미하지 않는다.

[0.5.0 API 계약 단계](../Plans/0.DevPhase/0.5.0/01_api_contract.md)
