# 디렉터리와 구현 상태

| 경로 | 역할 | 현재 상태 |
| --- | --- | --- |
| `Plans/` | 현재명세1.3·후속범위·14버전/70단계·시험/출시기준 | Jev API 전용 개정, 명세1.1/1.2는 과거 기록 |
| `bot/src/changgeun/` | Discord·권한/확인·SQLite·재생·NLP | 개발 구현·부분 LXC 시험, 전체 인수 전 |
| `inference/src/changgeun_inference/` | Jev API 전용 TLS gateway·원장·단일전송 | local 설정/모델 경로 제거·격리mock 유지 |
| `shared/schemas/` | API1.2 요청·응답 JSON Schema | 엄격 런타임 계약에서 생성, cross-field검증 추가 |
| `tests/` | 단위·통합·안전·한국어 개발평가 | LXC에서 실행; 실제held-out/soak와 구분 |
| `deploy/` | Jev API/격리mock·앱/환경/systemd | 비밀 없는 예시, 제한 설정은 LXC 별도 경로 |
| `scripts/` | 저장소검사·원격동기화·고정candidate·probe/backup | 평가/soak/주기백업의 최종 runner는 미완성 |
| `docs/decisions/` | 범위·런타임·평가예산 결정 | 결정0005 전용 범위·0006 YouTube/prefix·0007 주시 채널 관리 계획 |
| `evidence/public/` | 검토한 비밀 제거 Markdown 요약 | 실제 부분 실행·실패/제한 기록 |
| `.github/` | 저장소 파일 검사·이슈/PR양식 | 제품시험/배포 완료를 대신하지 않음 |
| `.private/` | 원본입력·derived비밀·이전local소스보관 | Git 제외·접근제한·내용 공개 금지 |

bot/inference는 독립 패키지이며 루트 pyproject는 공통 도구 설정이다. 새 고정 gateway candidate는 로컬 모델 패키지를 설치하지 않는다. 기존 LXC 모델 캐시와 데이터는 보존한다. 제품 VERSION·출시 태그는 전체 필수 검증 전에 만들지 않는다.

DB·원장·venv·로그·암호화 백업·실제 secret은 Git 밖 LXC 제한 경로에서 관리한다. 일반 소스 동기화는 데이터를 지우지 않으며 실제 접속값을 포함하지 않는다.

[개발 안내](../CONTRIBUTING.md) · [명세 구조](../Plans/CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md#s18)
