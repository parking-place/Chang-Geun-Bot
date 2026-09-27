# Jev API 전용 전환·개발 검증

기록: 2026-09-28 Asia/Seoul. 사용자 “안되겠다 그냥 Jev API Only로 하자”에 따라 [결정0005](../../docs/decisions/0005-jev-api-only.md)·[명세1.3](../../Plans/CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md)·11버전/55단계·시험/출시 기준을 개정했다. **제품1.0.0 전체 인수·정식 출시 완료 기록이 아니다.**

## 전용 실행 경계

- 실제 제공자는 jev-api 하나, mock은 지정 LXC의 명시 계약시험 전용이다. 설정 loader·봇 config/client/InferenceTrace·NLP·요청/응답 schema·gateway 서비스·controller에서 local 제공자를 거절한다.
- 로컬 모델 어댑터·준비/비교 스크립트·공개 local 프로필을 실행 소스에서 제외했다. 이전 소스는 비공개 보관하며 LXC 모델/캐시/가상환경·원장·복원 데이터를 삭제하지 않았다. 새candidate는 해당 환경을 공유하지 않는다.
- gateway candidate의 torch/transformers/OpenJev 부재·isolated venv·pip check·wheel/source hash를 검사했다. 외부키는 gateway만 읽고 내부 TLS/Bearer·origin 제한을 유지한다.
- 승인 음원·YouTube 링크/목록 범위, 실제 DJ/채널 권한·확인·원장·최대3단계/3 dispatch·전체12초/단계4초·fallback/retry0은 유지했다. hosted 내부forward와 미공개revision은 null/unavailable이다.

## 고정 후보

| 후보 | source manifest SHA256 | 봇 wheel SHA256 | gateway wheel SHA256 |
| --- | --- | --- | --- |
| dev20260928a | d1b61e0aa7f3751a632f2983f75707ac09e70549876fbb506433d4a4bc6e27b5 | 4922f68e8750a46152bc53ddf03d0b5424dd70c9cb3225ddaf2875d9d9050df6 | 1d555bb62461d258bd0cd63ec3ffaa5cb0b52736521dec8466f0d1a69c0de80b |
| dev20260928b | 7e59a44943d31dbbbe9c853693e6c19fd62c3c7460bf6cfa9486e31d2bd1a891 | 6b65d5db45c40a50325efeb530e27fa85bdad549d93a0e84825da4415f7ba637 | 749b2865677e33d8ae0f33bb543458ac1b646fabe687ec100910c9ca6a038865 |
| dev20260928c | 1bcfc5f4d3001e89a047c658a12423c870f747e3812a5cfff6af22e3b9800f79 | 9ed081c76f7697e2d3091930fb4640b57aa78ec44216810f382e3d060611a3e8 | bfcef92db7b42fadb55ae94cecd10ff4ee4514cf40608503d1e0291a5aec1021 |
| dev20260928d | ad5500597e9a41ae15bde190fead1291e4951376be1a60aba2278333dd2e44b4 | dabd11c0f18b4003f2a5b4fbfa5c07dd4de5617478ba997c9384ed8d7fabb837 | b8a1005f56d582741ebf4505a16d04a4f9846b441ff5ffa5d4f62ffda06830bc |

각 후보는 지정 LXC에서 비root로 build/install·pip check를 통과했다. build 실패/미검증 산출물을 정식 release로 취급하지 않는다. 소스 동기화만으로 활성 fixed wheel을 바꾸지 않는다.

## 원격 회귀·실제 전송

전용 초기변경에서 봇187·gateway41개가 통과했다. 추가 domain/backup 경계 회귀에서 처음1개가 이전 오류 문자열을 기대해 실패했으며 unsupported binding을 정확히 검사하도록 수정했다. 뒤의 봇190·gateway41개가 통과했다. 복합문/설명 질문 차단과 후보축소 변경 후 **봇197·gateway41 PASS**; 이후 검증된 action 설명을 제공하는 수정의 봇198 PASS, 최신 bot mypy26·gateway mypy7개 source PASS, ruff PASS다. Discord 라이브러리의 비차단 DeprecationWarning1개는 남아 있다. mock/계약 통과를 실제 모델 품질 인수로 합산하지 않는다.

candidate a를 기존 development-v2-20260927/jev-api에 활성화해 DB·원장·config hash `1f607a67ff8bd08eb1778e45d86d5ee4a0d5c8d5efe0210df8f3d5e17c26dde4`와 예산을 유지했다. TLS ready는 판단0회, 실제3단계 전송은 신규3dispatch·지연297/258/272ms·재전송cached PASS였다. 기존 smoke 원장의 예약은9→12/20으로 증가했으며 초기화하지 않았다. 이 값은 합성 transport 실측이며 전체 NL p95가 아니다.

현재 후보 d/v5에서도 TLS ready 판단0회·합성3단계 신규3dispatch·캐시재사용 PASS를 확인했다. 단계 지연은386/275/253ms였고 내부forward는 null/unavailable이다. 개발평가29dispatch 뒤 transport3회로 v5 원장은32/3000이다. 이전 v2/v3/v4 평가 원장 예약31/31/29와 smoke12/20을 그대로 유지했고 모든 원장 quick_check=ok였다. 양쪽 활성 서비스는 active·NRestarts=0이다. 명세의 요청/응답 JSON 예시4개를 후보d의 실제 Pydantic 계약으로 LXC에서 검증했다. 마지막 저장소 검사에서 공개202파일·문서링크785개·JSON예시10개 및 ignore/자격정보 패턴 검사를 통과했다. 이 파일 검사는 제품 인수 증거가 아니다.

## 실제 한국어 개발 평가

`korean-eval`을 구현해 실제 eval 목적/config hash·남은예산≥문장수×3을 사전 확인한다. 37문장 최대111dispatch를 계획하고 isolated DB/합성actor로 ActionPlan만 채점한다. **실제 Discord 변경·오디오 재생은 실행하지 않는다.** 결과는 새로운 제한 파일에 저장하며 같은 report를 덮어쓰지 않는다.

| 후보 / prompt | run | 전체 | 명확한 요청 | 위험 계획 | 판정 |
| --- | --- | --- | --- | --- | --- |
| a / v2 | evaluation-v2-20260928 | 34/37 | 22/25 | 0 | 개발목표95% 미달; 실제31dispatch |
| b / v3 | evaluation-v3-20260928 | 34/37 | 23/25 | 1 | FAIL; 복합 요청의 한 부분을 계획해 a/v2로 복귀 |
| c / v4 | evaluation-v4-20260928 | 35/37 | 23/25 | 0 | 안전회귀 수정 확인; 개발목표95% 미달 |
| d / v5 | evaluation-v5-20260928 | 37/37 | 25/25 | 0 | 한정 개발 세트 PASS; 독립held-out 인수 아님 |

v3에서는 “대기열을 비우고 다음 곡으로 넘겨줘”를 queue.clear만 계획했다. 실행은 하지 않았고 보고/원장을 보존했다. threshold0.80·margin0.10을 유지하면서 복합 요청/사용법 질문을 추론 전에 거절하고, 가능한 의도+non_command+clarify로 첫 후보를 좁힌 v4를 별도 후보 c에서 검증해 위험 계획0을 확인했다. 남은 두 거절은 정보조회/등록목록재생의 낮은점수였다. 실제 DB에서 검증한 단일 action 설명을 최소context 데이터로 제공하는 v5를 후보d에서 별도검증해37/37·명확25/25·위험계획0을 확인했다. config hash는 `6e163bf85e60d2adde628bc8f5e9f342466e1385ec5597c70cb18ff7d7feadab`이며 이 후보가 현재 테스트 서비스에 활성화되어 있다. 기존run/config/예산은 변경하지 않았다.

## 보존한 이전 실제 시험

사용자 제공 YouTube 목록31개는 공식API에서 완전조회·길이/순서확인·확인import/export/reimport를 별도DB에서 통과했다. 사용자도 승인시험음 청취와 재생/일시정지/계속/정지의 정상 응답을 확인했다. 이 결과는 이전후보의 해당 범위 증거이며 전체역할/버튼/새후보인수를 대신하지 않는다.

이전 Jev API 봇/원장 및 과거local snapshot의 격리복원과 CMS AES256-GCM 암호화 사본의 노드간 checksum을 확인했다. bot offnode 사본을 복호화/격리복원했고 변조암호문은 output경로 없이 거절했다. 복구 private key는 봇root·별도비공개escrow, gateway에는 public certificate만 있다. 원본DB를 gateway로 전송하지 않았다. 주기복사/보존·RPO/RTO·candidate/lock manifest 전체 인수는 남아 있다.

## 남은 인수

지원 P0/P1 기능·실제 DJ/non-DJ/버튼/채널·최소봇권한, 독립held-out≥200·명확한 요청≥95%, 단계별≥100요청, 실제음성혼합≥8시간, 주기백업/보존/복원·장애/rollback·잠금/운영manifest·배포후 인수가 남아 있다. local 품질/CPU/양쪽 제공자 시험은 사용자 결정으로 현재 게이트에서 제외했다. Git commit/push·제품VERSION·출시태그는 만들지 않았다.
