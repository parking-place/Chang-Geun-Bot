# 봇 패키지

DiscordBotLXC의 한국어 슬래시/버튼, DJ·채널 권한, 확인, SQLite 마이그레이션과 공통 실행기, 승인 음원 재생 상태·복구를 담당합니다. 진입점은 `python -m changgeun --config ... --token-env ...`이며 제한 파일을 사용합니다. 제품 실행은 지정 LXC에서만 수행합니다.

`/부탁`의 판단은 선택한 게이트웨이에 요청하고 실행은 권한·대상·버전·세대·확인을 다시 검사합니다. 1.0.0 기준선은 승인 음원과 공식 YouTube 메타데이터 관리입니다. 1.0.1/1.0.2 개발 후보에는 명시 플래그로 YouTube 비동기 PCM worker와 `!!창근아` 지정 채널 입력을 연결했습니다. 안정 영상 ID만 저장하고 임시 미디어 URL은 worker 메모리에 둡니다. [새 검증 범위](../evidence/public/youtube-prefix-20260928.md)를 따릅니다.

현재 구현은 개발 후보입니다. 제안·규칙 생성·확인 후 import/export·version을 검사하는 undo를 구현하고 LXC 회귀를 수행했습니다. 실제 목록 API 시험·전체 편의 기능·한국어 최종 품질과 Discord 사용자 인수는 [진행 현황](../Plans/0.DevPhase/STATUS.md)에 따라 완료해야 합니다. 단위/mock 성공을 실제 사용자 시험으로 표시하지 않습니다.

[명세](../Plans/CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) · [원격 실행](../docs/REMOTE_DEVELOPMENT.md) · [실행 증거](../evidence/public/execution-20260927.md)
