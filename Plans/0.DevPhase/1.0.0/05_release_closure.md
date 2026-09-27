# 1.0.0 Phase 5 — 최종 증거와 출시 종료

- 버전: `1.0.0`
- 단계: `5 / 5`
- 선행: [Phase 4](04_postdeployment_checks.md) 배포 후 smoke·초기 관찰 통과.
- 검증 호스트: `DiscordBotLXC`의 봇·별도 계정 중계
- 상태: **PLANNED — 필수 인수 전**
- 추론 계약: [프로필 선택·시험 실행](../INFERENCE_PROFILES.md), [개발 명세 v1.3](../../CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md), 내부 API schema `1.2`.

## 목표

- 구현·원격 인수·실제 배포가 모두 완료된 버전만 정식 1.0.0으로 기록한다.
- 이후 운영 점검과 업데이트에서 재사용할 재현·복구 근거를 보존한다.

## 로컬 코드 작업

- Jev API의 최종 manifest·원격 시험·backup/restore 증거와 선택한 운영 프로필의 실제 배포/smoke를 한 인덱스로 연결한다. 지원 검증은 양쪽, 운영 활성은 하나라는 범위를 명시한다.
- 명세 §19 모든 필수 항목과 T/N/P/O/B·버전별/run별 인수표의 실제 상태를 갱신한다. 공통 source/fixture/snapshot/seed/정책 및 run별 모델/프롬프트/임계값·config_hash·run_id를 기록하고 점수를 합산하지 않는다.
- release note에 최종 지원 범위·run별 실측 조건·복구 기준을 반영한다. hosted의 원격 forward/취소 관측 불가·반환 모델/API 버전·측정시각·고정 불가 한계와 외부 전송 정책을 알려진 제한으로 기록한다.
- tag·VERSION 등 출시 메타데이터가 필요하면 후보 내용 영향과 재검증 여부를 기록한다.
- 일상 운영·로그 보존·백업·정기 복원·보안/소스 정책·hosted 한도/가격/보존 정책 재확인 작업을 정리한다. 프로필 변경은 기존 검증 범위 확인과 중지/drain·명시 선택·재시작·smoke·rollback을 거친다.

## 산출물

- 1.0.0 최종 검증 인덱스·배포 완료 기록·release manifest·release note.
- 운영 점검·문제 대응·rollback·복원 문서와 다음 개선 backlog.
- 모든 변경·검증·미지원 상태를 구분한 개발 진행 상태 기록.

## LXC 검증

- DiscordBotLXC의 봇·중계: 실제 운영 SHA·provider/profile_id/config_hash·모델 정보·의존성·스키마·prompt/threshold가 선택 프로필의 최종 manifest와 일치하는지 확인한다.
- `DiscordBotLXC`: 마지막 smoke·서비스 상태·DB·백업·외부 복사본을 확인한다.
- `DiscordBotLXC의 중계`: 공통 gateway readiness·인증·단일 dispatch·영속 원장·provider_calls metrics를 확인한다. hosted는 모델/torch 없이 동작·무료 health·외부 키 제한·호출 한도를 확인한다.
- 변경된 메타데이터가 실행 산출물을 바꾸면 필요한 시험·빌드를 해당 LXC에서 반복한다.
- 공개 기록에 IP·SSH 경로·토큰·개인 원문·서명 URL이 없도록 증거를 정리한다.

## 통과 기준

- Jev API에서 필수 기능·권한·소스·한국어 최소 200문장·provider_calls 예산·경로별 최소 100회 성능·8시간 부하·복원·보안 증거가 충족되고 선택 프로필의 배포 증거가 존재한다.
- 운영에서 같은 불변 후보가 실행되고 실제 배포 후 확인까지 완료된다.
- 승인된 변경 범위의 승인 음원 재생과 YouTube 링크·목록 관리를 모두 인수한다. 직접 오디오 추출·전송을 지원한다고 표시하지 않는다.
- 한 프로필을 지원 범위에서 제외하는 경우를 포함하여 명시적으로 합의한 변경 명세가 있다면 원래 제외 범위·근거·최종 계약을 분명히 기록한다. 운영에서 선택하지 않았다는 이유만으로 필수 인수를 생략하지 않는다.

## 중단·후속 처리

- Jev API에서 미구현·미실행·FAIL이 남으면 해당 게이트를 열어 두고 완료·출시로 표시하지 않는다. mock·dry-run 성공으로 실제 제공자 증거를 대신하지 않는다.
- 출시 뒤 회귀는 검증된 rollback과 새 후보 검증으로 처리하며 증거를 보존한다.
- 계획 작성 단계에서는 태그 발행·공개·서비스 배포를 자동 수행하지 않는다.

## Jev API 전용 인수 범위

2026-09-27 사용자 결정에 따라 실제 제공자는 `jev-api` 하나다. [전용 계약](../INFERENCE_PROFILES.md)을 따른다. 과거 로컬 모델 시험은 보존 기록이며 이 단계의 선행 조건이나 출시 게이트가 아니다. 권한·확인·데이터·최대3단계/3 dispatch·전체12초/단계4초·실패 후 추가 전송0 규칙은 유지한다. hosted 내부 forward와 미공개 model revision은 null/unavailable로 남긴다.
