# 0.9.0 Phase 2 — 기능·권한·보안 회귀

- 버전: `0.9.0`
- 단계: `2 / 5`
- 선행: [Phase 1](01_release_candidate.md) 후보·시험 환경 고정.
- 검증 호스트: `DiscordBotLXC`의 봇·별도 계정 중계
- 상태: **PLANNED — 필수 인수 전**
- 추론 계약: [프로필 선택·시험 실행](../INFERENCE_PROFILES.md), [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md), 내부 API schema `1.2`.

## 목표

- 입력 경로마다 같은 권한·확인·상태·취소 정책이 적용되는지 확인한다.
- API·음성·소스·URL·비밀값 방어를 출시 후보에서 최종 검증한다.

## 로컬 코드 작업

- T-01~T-20의 목록·중복·큐 복사·음성·퇴장·재시작 회귀 데이터를 준비한다.
- N-01~N-36의 부정문·권한·주입·예산·중복·원장·경쟁·취소를 Jev API에서 준비하고 B-01~B-12의 선택·격리·호출 제한·관측·전환 기대 결과를 연결한다. `mock`으로 준비한 오류 주입과 실제 제공자에서 확인한 범위를 구분한다.
- P-01~P-12의 별칭·태그·생성·제안·가져오기·복원·되돌리기 사례를 같은 후보로 재시험한다. O-01·02·08은 이 단계, O-03·04는 04단계, O-05~07은 05단계에 결과를 연결한다.
- 슬래시·멘션·버튼·선택 메뉴·확인의 비DJ 거절과 실행 직전 DJ 재검증을 연결한다.
- HTTPS 공급자 allowlist·리다이렉트·DNS 변경·내부 주소·등록 파일 ID 방어를 시험한다.
- 잘못된 내부 API 인증·TLS·후보 밖 ID·NaN·단계 순서·병렬 요청·provider/profile_id/config_hash 불일치의 안전 실패를 확인한다. hosted는 외부 401/429/5xx·네트워크·한도 실패에서 숨은 retry/자동 fallback이 없는지도 확인한다.

## 산출물

- run별 T/N/P/B 및 이 단계 O 시험의 입력·기대·실제 결과와 모든 입력 경로의 권한 커버리지. 동일 fixture·seed·초기 snapshot을 사용하고 점수는 독립 집계한다.
- DAVE·음성 UDP·재연결·승인 음원 재생·YouTube 링크/목록 관리의 증거. 직접 오디오는 지원 제외 상태를 확인한다.
- API 접근·입력 검증·셸 실행 금지·로그 필터링의 보안 결과표.

## LXC 검증

- `DiscordBotLXC`: 테스트 guild에서 전 T/P 사례와 슬래시·버튼·확인 권한을 실행한다. 전체 자연어 요청의 후보·문맥·계획을 평가하는 runner도 이 서버에서 실행한다.
- `DiscordBotLXC의 중계`: Jev API의 N/API provider_calls 예산 원자성·단계 건너뛰기·재시작 불명·중복 수신을 시험한다. 전송 불명 timeout/크래시 예산은 환불하지 않고 tombstone을 보존한다.
- DiscordBotLXC의 봇·중계: 권한 해제·큐 재정렬·현재곡 변경·기한 초과 경쟁을 실행 중 주입한다.
- 내부 TLS·JEV_API_TOKEN·접근 제한과 안전한 오류, signed URL·토큰 비노출을 확인한다. JEV_HOSTED_API_KEY는 gateway만 접근하고 외부에는 합성/익명 fixture·최소 후보만 전송된다.
- 설치·lint·빌드·시험은 원격에서만 수행하고 결과 원문에서 민감값을 제거한다.

## 통과 기준

- T-01~T-20, N-01~N-36, P-01~P-12, O-01·02·08의 필수 기대 결과가 전건 일치한다. 남은 O 항목은 04~05단계에서 인수한다.
- 비DJ 변경·무확인 위험 삭제·timeout/취소 후 실행·잘못된 대상 수정이 0건이다.
- Jev API에서 최대 3단계 판단/질문·request_provider_calls_total≤3·숨은 호출 0건·조기 종료·장애 중 기본 기능 유지가 충족된다. hosted의 forward_passes/request_forward_passes_total은 null·forward_passes_source=unavailable이며 원격 계산 종료/forward 상한을 검증했다고 기록하지 않는다.
- 승인된 1.0.0 범위는 승인 음원·YouTube 링크/목록 관리다. 직접 YouTube 오디오는 범위 제외/비활성이며 승인 음원 인수를 직접 YouTube 재생 PASS로 표시하지 않는다.

## 중단·후속 처리

- Jev API에 안전·권한·예산 오류가 있으면 해당 결과를 FAIL로 기록하고 출시를 차단한다. mock PASS로 대체하지 않고 후보를 수정한다.
- 소스 정책·권리·기술 검증 실패는 완전한 1.0.0 차단으로 유지한다.
- 후보 변경 후 영향 회귀를 다시 수행하고 독립 한국어 평가로 진행한다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
