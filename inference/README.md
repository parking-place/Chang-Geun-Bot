# Jev API 판단 게이트웨이

현재 DiscordBotLXC의 별도 `changgeun-gateway` 계정에서 Jev API 전용 TLS/Bearer API1.2·영속 호출 원장을 운영한다. 실제 제공자는 jev-api 하나이고 mock은 명시 LXC 시험 전용이다. 로컬 모델 어댑터·snapshot 인자·local 설정은 지원하지 않는다. torch/transformers/OpenJev 설치·모델 가중치가 필요하지 않다.

공식 고정 HTTPS endpoint로 재시도/redirect 없이 단일 전송한다. 외부 키는 gateway만 읽는다. 최대3단계/3dispatch·전체12초/단계4초·후보 제한·원자 예산·중복 합류·불명 재실행 금지를 유지한다. 내부 forward와 미공개 model revision은 null/unavailable로 기록한다.

후보 변경은 준비·정상 종료/drain·TLS ready·재시작으로 수행하며 run 원장과 공유 tombstone을 보존한다. smoke 한도20, 명시 평가 목적의 eval 프로필만 최대3000을 허용한다. 최종 품질·성능·8시간·복구 인수는 아직 완료 전이다.

[전용 결정](../docs/decisions/0005-jev-api-only.md) · [현재 배치](../docs/decisions/0008-single-lxc-jev-api.md) · [계약](../Plans/0.DevPhase/INFERENCE_PROFILES.md) · [원격 도구](../docs/REMOTE_DEVELOPMENT.md)
