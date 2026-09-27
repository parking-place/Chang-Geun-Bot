# 2026-09-27 실행 기록 — 개발 진행 중

출시 증거가 아닌 초기 실행/개발 기록이다. 최신 후보의 전체 시험·실제 기능 인수는 별도로 추적한다. 비공개 ID·주소·토큰은 포함하지 않는다.

| 실행 | 호스트 | 결과 | 범위/제한 |
| --- | --- | --- | --- |
| SSH·OS·자원/기존 서비스 확인 | 두 LXC | PASS | Debian 13, Python 3.13.5; 기존 서비스 보존 |
| 비root 계정/venv/격리 개발 경로 | 두 LXC | PASS | `/opt/changgeun-dev`와 별도 런타임 경로; 운영 배포 아님 |
| 도메인·SQLite·권한·확인·공통 실행기 첫 시험 | DiscordBotLXC | 56 PASS | 단위/DB 시험; 실제 슬래시 인수 아님 |
| 재생 상태·소스 경계 포함 후속 시험 | DiscordBotLXC | 75 PASS | 최신 전체 후보는 다시 검증 필요 |
| API·원장·중복·3단계·timeout·redirect·인증 | OpenJevLXC | 24 PASS | mock/transport 시험; 실제 모델 품질 아님 |
| Discord 초기 음성 probe | DiscordBotLXC | PASS | discord.py 2.7.1, DAVE protocol 1, 시험음 100 frames, 정상 퇴장; 사람의 청취 확인 없음 |
| hosted 단일 합성 판단 | OpenJevLXC | PASS | 482ms, dispatch 1; 반환 model `jev-1.13.0`; 내부 forward null/unavailable |
| local 단일 합성 판단 | OpenJevLXC | PASS | 929ms, CPU FP32, 실측 forward 1; cold load는 별도이며 출시 지연 아님 |
| Discord 시험 설정 | DiscordBotLXC | 완료 | 지정 테스트 채널 식별; DJ 역할 생성/지정 사용자 부여; ID는 비공개 보관 |
| 봇·DB·재생·해석·핸들러 후속 회귀 | DiscordBotLXC | 100 PASS | 목록 재생의 큐 version·미승인/누락 파일의 변경 전 거절 포함; 실제 사용자 인수 아님 |
| 게이트웨이 후속 안전 회귀 | OpenJevLXC | 26 PASS | 이전 run UID 소유권, 캐시 신규 호출 0, 인증 후 JSON 처리·chunked body 상한 포함 |
| 코드 lint·타입 검사 | 지정 LXC | PASS | ruff, bot 21개/inference 7개 source; 이후 변경은 해당 범위 재검증 |
| 내부 HTTPS 신뢰·인증 | DiscordBotLXC → OpenJevLXC | PASS | 정상 200, 비인증 401, 비신뢰 CA 거절, 정확한 profile/config binding; health 유료 호출 0 |
| hosted → local 명시 전환 | 두 LXC | PASS | 정상 종료/drain, 프로필별 독립 DB·원장, 이전 요청 tombstone 보존; 전체 장애 롤백 인수 전 |
| hosted TLS 합성 3단계 + replay | DiscordBotLXC → OpenJevLXC | PASS | 실제 dispatch 누계 3, cached replay 신규 dispatch 0; 단계 398/252/285ms; 한국어 품질/최종 성능 아님 |
| local TLS 합성 3단계 + replay | DiscordBotLXC → OpenJevLXC | PASS | 실제 forward 누계 3, cached replay 신규 forward 0; 단계 865/817/792ms; 한국어 품질/최종 성능 아님 |
| 실제 Discord 사용자 조작·청취 | 시험 서버 / DiscordBotLXC | PASS — 사용자 확인 | `dev20260927e`, jev-api 활성; `/재생 목록:시험음 목록`·일시정지·계속·정지와 실제 시험음 청취 모두 정상이라고 사용자 확인; 전체 DJ/non-DJ/버튼 조합 인수 아님 |

## 추가 개발 회귀와 공식 YouTube 연결

- 공식 키는 사용자 지정 비공개 파일에서 읽고 제한 파일(0600)로 DiscordBotLXC에 공급했다. 키 값·요청 URL은 로그/증거/Git에 포함하지 않는다.
- 공식 검색 1결과, 제목·채널명·길이 조회와 동일 영상 재조회: PASS. 사용자가 지정한 실제 재생목록에서 31곡 전체 읽기·31곡 길이·미조회 항목 0개를 확인했다. 오디오를 가져오지 않았다.
- 첫 probe는 조회를 마친 뒤 잘못된 속성명으로 출력 단계에서 실패했다. 수정 후 3호출 probe가 통과했으며 첫 실행의 호출도 삭제/환불하지 않는다.
- 최신 봇 회귀: **166 PASS**, source manifest `4854f12e70a841996b18fd30239334535ebd2765c4e3c6344163729a83f6f0af`. 공개 API metadata mock·페이지/할당량/부분 읽기·import/export·DJ 권한 재조회·승인 음원 경계·규칙 생성·동시 편집 방지 undo를 포함한다. 이후 형식/후속 변경은 새 revision으로 추적한다.
- 새 `/유튜브검색`, `/목록 가져오기`, `/목록 만들기`, 제안/표기와 `/되돌리기`는 소스/핸들러 회귀를 통과했으나 이 시점의 고정 live `dev20260927e`에는 아직 적용하지 않았다.
- API 1.2 응답에 task/context_snapshot_id/candidate_set_id를 추가 결합했다. 공개 JSON Schema를 지정 LXC에서 생성했다. 기존 live와 함께 봇·게이트웨이를 교체하기 전까지 신규 클라이언트를 live 응답에 섞지 않는다.
- hosted v1의 합성 한국어 개발 3문장 결과는 **2/3**이다. 문맥의 ‘틀지 말고 목록에 넣기’는 안전하게 거절했지만 기대 action을 해석하지 못했다. held-out 점수나 출시 PASS가 아니다. threshold를 낮추지 않고 prompt v2·문맥 후보 개선을 준비했다. 후속 v2 3문장에서는 hosted 3/3, local 1/3이다. local의 37문장 확대 개발 평가에서는 14/37, 명확한 25문장 중 2/25만 맞췄으며 잘못된 실행 계획은 0개였다. 낮은 품질의 안전 거절을 성공으로 세지 않고 개선한다.

## 고정 모델과 런타임

OpenJev commit `3e97d9cd934a1bb573e4da41200bf4615760d2db`, Qwen/Qwen3-0.6B model revision `c1899de289a04d12100db370d81485cdf75e47ca`. CPU 모델은 별도 `local-venv`에 설치했다. Hosted 전용 venv는 torch/transformers를 요구하지 않는다.

초기 공통 manifest: `3e882631d0a99e5d0a2da3b7735f792cb2ae09a52bbc04c1a3eecbe7e99205b8`. 후속 개발로 바뀌므로 이 hash를 최신 전체 후보 인수로 사용하지 않는다. 실행별 소스 manifest와 원시 출력은 비공개 작업/런타임에 보관한다.

3단계 전송/전환 후보 `dev20260927d`의 source manifest는 `6a41dae166493aef0f87317f0d1891aabdd5c8547dadefe35fa51bb415cd9a1b`다. bot wheel SHA256은 `321f5d477cd9a4a3386c04baddf417380dee6822998ba9a1fa6ed02fc8bad8ec`, gateway wheel은 `130514ee590cd96f7fd13eceba2e97fafa80fb0179182e5826599a1d46ae074d`다. 후속 목록 재생 수정과 100개 회귀의 source manifest는 `fc601a99ef2ca160909e09cda56c4732e1659e6dd1325d9cec7d20f08291736a`이며 이전 wheel의 전체 기능 PASS로 합치지 않는다.

사용자 조작 후보 `dev20260927e`의 source manifest는 `e5a71331e03a0d2e89561b782b4d6278bc7cdf3dd7f5412b0c94c9357095375f`, bot wheel은 `a21df90e246a0e2b9bd1d899531de0dc198c8d8eb170cc1fb7ef9e44d6da4338`, gateway wheel은 `a77dd3f8a2289e1573945df99001b68d24cfe2f761a8a2ae6f5b2b18b8702a30`다. 현재 원격 서비스는 고정 wheel이므로 후속 소스/문서 편집이나 시험 동기화가 이 후보의 실행 코드를 바꾸지 않는다.

## 후보 f · 후속 구현/복원

- 고정 후보 `dev20260927f` source manifest: `bb3c7b2801115472e450d1d5e6c3e6c046754fa6a5f94a56a8e5d638617f0202`. bot wheel `ba7ac301f96812468d79ecc586803e3d377a1f5da7cbd2b40a6c93ccc9ddb89a`, gateway wheel `584235bca44f438f96ab9cd2c13155b5f92fbb14e2b94eecec63736ecfd69b68`.
- run `development-v2-20260927`에서 양방향 명시 전환·TLS binding·3단계/replay를 검증했다. local은 실측 forward3, hosted는 forward null/unavailable다. local 전송과 개발 probe가 같은 슬롯을 함께 사용한 지연은 독립 benchmark로 보고하지 않는다.
- 후속 소스에는 explicit mention 공통 진입점, import 공식 길이 저장, 격리 백업/복원 도구가 추가됐다. f의 고정 wheel에는 이러한 후속 변경이 아직 포함되지 않았다.
- 소스 mock/DB/핸들러 후속 **184 PASS**, gateway/복원 **27 PASS**, 평가 예산 검증 **6 PASS**. 184/27 source manifest `3e9f5b6a016c5c7e27669e1e844d32f4931492d0d7f388e28abda234dca39eeb`; 후속 변경은 별도 재검증한다.
- 실제 공식 조회 snapshot의 격리 import/export/reimport: **31/31 순서·참조 보존, 길이31, 필수 확인 PASS**. 합성 Actor를 사용하며 실제 Discord 변경·오디오 추출는 0이다.
- 두 제공자 각각 봇 DB 및 gateway 원장/공유 tombstone을 Online Backup API로 백업·새 경로 복원했다. checksum/프로필 결합·무결성·확인 무효화·자동 재생 차단·기존 예산 보존을 확인했다. 원본과 활성 service를 덮어쓰지 않았다. 노드 밖 암호화 보관·주기적 보존·전체 복원 시간 드릴은 추가 게이트다.

## 현재 제한과 남은 게이트

- Debian/Python의 실제 환경은 [런타임 결정](../../docs/decisions/0002-lxc-runtime.md)에 기록했다. LXC를 재생성하지 않았다.
- 실제 Discord 슬래시/버튼의 사용자별 권한 조합·3초 접수·충돌/확인은 아직 인수 전이다.
- 사용자가 1.0.0 범위를 승인 음원 재생·YouTube 링크/목록 관리로 확정했다. 직접 YouTube 오디오는 제외/비활성이다. 승인 음원의 최종 인수는 아직 완료 전이다.
- Hosted 계정 가격·정확한 한도·데이터 보존 정책과 model revision 고정은 미확인이다. 초기 run의 유료 호출 상한은 준비/실패를 포함한 20회다.
- 한국어 개발/held-out 평가·각 제공자 1/2/3단계 대량 시험·각 8시간 혼합 부하·보안/복원/롤백·최종 배포를 아직 수행하지 않았다.
- 현재 테스트 봇은 서버에서 Administrator 권한을 가진다. 출시 전 최소 권한으로 재검증해야 한다.
- 제품 VERSION/출시 태그/1.0.0 완료 상태는 만들지 않았다.

[진행 현황](../../Plans/0.DevPhase/STATUS.md)
