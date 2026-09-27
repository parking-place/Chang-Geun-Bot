# 0.3.0 — 허용 소스·DAVE·음성 gate

| 항목 | 내용 |
| --- | --- |
| 상태 | IN_PROGRESS — 부분 구현·LXC 시험; 전체 인수 전 |
| 선행 버전 | [0.2.0](../0.2.0/README.md) 구조화 Discord·fixture 목록 봇 |
| 검증 호스트 | DiscordBotLXC |
| 명세 | [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md) §4.2·5.2·6.1·11·18.1 |

메타데이터 취득·검색·가져오기·오디오 전송을 분리한다. 실제 전송 권한이 확인된 별도 음원으로 DAVE 실재생을 검증할 수 있지만 이 결과를 유튜브 직접 재생 구현 완료로 표시하지 않는다. 로컬은 코드·문서 작성과 읽기 검토만 하며 모든 설치·lint·타입검사·시험·build·음성 실행은 DiscordBotLXC에서 수행한다.

## 공통 기준

- [환경과 실행 경계](../ENVIRONMENT.md)
- [시험 추적표](../TEST_MATRIX.md)
- [검증 증거 템플릿](../EVIDENCE_TEMPLATE.md)

## 5단계 순서

1. [01 메타데이터·재생 소스 적합성 결정](01_source_decisions.md)
1. [02 외부 URL 검증·메타데이터와 검색 경계](02_metadata_provider.md)
1. [03 DAVE·음성 의존성과 실재생 기술 검증](03_dave_voice_probe.md)
1. [04 입장·퇴장과 채널 선택 정책](04_voice_channel_policy.md)
1. [05 소스·음성 활성화 인수와 재생 gate](05_source_voice_gate.md)

## 추론 프로필 적용

[Jev API 전용 계약](../INFERENCE_PROFILES.md)을 따른다. 실제 자연어 판단은 `jev-api`만 사용하며 봇과 TLS 중계·영속 원장은 DiscordBotLXC에서 별도 계정으로 실행한다. 현재 배치는 [환경 계약](../ENVIRONMENT.md)을 따른다. `mock`은 지정 LXC의 격리 회귀 전용이다. 구조화 명령은 추론 없이 실행하고, API 장애가 기존 재생·슬래시·버튼을 막지 않게 한다.

## 범위

- 소스별 플랫폼 정책·콘텐츠 전송 권한·기술 검증 근거.
- 실제 MetadataProvider·URL 선택/검증·source 상태·캐시/할당량.
- DAVE 지원 의존성·UDP 왕복·허용 음원 실재생 probe.
- /입장·/퇴장·ID 기반 채널 선택·최소 권한·원격 제어 정책.

## 범위 밖과 후속

- 제품 /재생·대기열·현재곡 제어는 0.4.0이다. probe 성공을 제품 완성으로 표시하지 않는다.
- 미검증 유튜브 직접 오디오 경로는 youtube_audio_enabled=false를 유지한다.
- 외부 목록 전체 가져오기·부분 실패 반영·파일 내보내기/가져오기는 0.7.0에서 완성한다.
- hosted Jev API와 자연어는 0.5.0~0.6.0의 독립 gate를 따르며 음성 검증을 대신하지 않는다. 어느 추론 프로필 선택도 source/DAVE 활성화 조건을 바꾸지 않는다.

## 버전 종료 게이트

허용 소스 1개 이상, 실제 DAVE 전송/수신·재연결, 채널 정책/T-12의 LXC 증거가 있어야 0.4.0 실재생 기능을 활성화한다. 정책·권한·기술 중 미확정 항목이 있으면 해당 경로는 비활성이다. 소스 대안이 최종 제품 요구를 충족하는지는 명시적인 결정 기록으로 관리한다. 현재 상태는 계획 / 미구현 / 미검증이다.


## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
