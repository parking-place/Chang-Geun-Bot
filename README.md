# 창근이 / Chang-Geun-Bot

한국어 자연어 요청으로 창팝 곡·플레이리스트를 관리하고 Discord 음성채널에서 재생하는 봇을 개발합니다.

저장소: [parking-place/Chang-Geun-Bot](https://github.com/parking-place/Chang-Geun-Bot)

**개발 구현과 지정 LXC 시험을 진행 중입니다.** 테스트 서버의 구조화 명령, 승인 시험음 재생, Jev API 추론 어댑터와 고정 후보 배포을 구현했습니다. 전체 버전 인수·한국어 품질·장시간 시험·정식 운영 출시는 아직 완료하지 않았습니다.

2026-09-27 사용자 지시로 **Jev API 전용**으로 개발합니다. 2026-09-28 OpenJevLXC 사용을 종료하고 DiscordBotLXC에서 봇과 별도 계정의 API 중계를 실행합니다. [제공자 결정](docs/decisions/0005-jev-api-only.md)과 [현재 배치](docs/decisions/0008-single-lxc-jev-api.md)를 따릅니다.

사용자 승인에 따른 1.0.0 범위는 **승인 음원 재생과 YouTube 링크·목록 관리**입니다. 이 제한은 1.0.0 기준선에 적용됩니다. [범위 결정](docs/decisions/0003-approved-audio-release-scope.md)을 따릅니다.

2026-09-28 후속 계획을 추가했습니다. [1.0.1](Plans/0.DevPhase/1.0.1/README.md)은 승인 음원 매핑 없는 YouTube 영상 재생, [1.0.2](Plans/0.DevPhase/1.0.2/README.md)는 지정 채널의 `!!창근아` 한국어 문장 명령이 목표입니다. 두 버전은 개발 후보를 구현하고 지정 LXC에서 검증 중입니다. 지정 영상 URL·공식 검색 선택과 두 채널의 접두어 입력을 연결했습니다. YouTube 주소의 `https://`는 생략할 수 있습니다. [실행 증거와 남은 인수](evidence/public/youtube-prefix-20260928.md)를 따릅니다.

2026-09-28 [1.0.3 주시 채널 관리](Plans/0.DevPhase/1.0.3/README.md)를 구현했습니다. 서버 관리자가 `/주시 추가·제거·목록·켜기·끄기·점검`으로 `!!창근아` 반응 채널을 관리합니다. 설정은 DB에 저장되며 관리 명령은 Jev를 호출하지 않습니다. 개발 봇에 적용했으며 사용자가 목록·점검·끄기·켜기와 접두어 반응을 정상으로 확인했습니다. [자동 회귀와 남은 전체 인수](evidence/public/watch-channels-20260928.md)를 구분합니다.

## 먼저 읽을 문서

- [개발 명세 1.3](Plans/CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md)
- [0.0.0 → 1.0.3 버전별 계획](Plans/0.DevPhase/README.md)
- [현재 진행 현황](Plans/0.DevPhase/STATUS.md)
- [Jev API 전용 계약](Plans/0.DevPhase/INFERENCE_PROFILES.md)
- [개발·검증 환경](Plans/0.DevPhase/ENVIRONMENT.md)
- [저장소 구조](docs/REPOSITORY_STRUCTURE.md)

## 디렉터리 구성

```text
.
├── Plans/          # 원본 명세, 14개 버전·70단계 계획, 시험/출시 기준
├── bot/            # Discord·도메인·SQLite·재생 패키지
├── inference/      # 공통 게이트웨이·제공자 어댑터 패키지
├── shared/         # 공통 API 1.2 요청·응답 JSON Schema
├── tests/          # 단위·통합·안전·한국어 평가와 합성 fixture 위치
├── deploy/         # 비밀 없는 설정·프로필·환경·systemd 템플릿
├── scripts/        # 저장소 점검·LXC 동기화·프로필 선택과 probe
├── docs/           # 개발/운영 안내와 설계 결정
├── evidence/       # 실제 검증 결과; 검토한 공개 요약만 Git에 포함
└── .github/        # 저장소 점검 workflow와 이슈/PR 양식
```

개인 서버·GitHub 입력·API 키는 `.private/`에 보관하며 Git 추적에서 제외합니다. 환경 파일, DB·원장, 모델, 로그와 백업도 제외합니다. 설정 예시에는 실제 주소·Discord ID·키를 넣지 않습니다.

## Jev API 전용 실행

| 프로필 | 판단 경로 | 준비 상태 |
| --- | --- | --- |
| `jev-api` | DiscordBotLXC의 별도 계정 중계 → 호스팅 Jev API | [현재 개발 프로필](deploy/profiles/eval-jev-api-single-lxc-v1.yaml), 실제 TLS 3단계·캐시 검증; 최종 품질 인수 전 |
| `mock` | 고정 fixture, 자동 계약시험 전용 | [설정 템플릿](deploy/profiles/mock.yaml), 계약/안전 회귀 시험; 실제 제공자 품질 증거와 구분 |

[검증한 실행 절차](docs/REMOTE_DEVELOPMENT.md)에 따라 `scripts/test_profile.py`에서 프로필을 선택합니다. 자동 재시도·다른 제공자 fallback은 허용하지 않습니다.

```bash
python3 scripts/test_profile.py --ssh-config .private/lxc-ssh.conf --profile jev-api --suite status
```

현재 `activate`는 준비된 중계를 유지하고 봇 후보만 전환합니다. 기존 DB·고정 중계 원장/예산과 요청 tombstone을 보존하며 `transport`는 명시적으로 실제 판단 최대 3회를 사용합니다. `contract`는 LXC 단위/mock 시험이며 모델 품질을 판정하지 않습니다.

## 저장소 점검과 개발

```bash
python3 scripts/check_repository.py
```

위 명령은 Git 공개 후보·ignore 규칙·문서 링크·TOML/JSON·비밀값 패턴을 읽어 검사합니다. 제품 코드를 import하거나 패키지/모델을 설치하고 실행하지 않습니다. GitHub Actions도 이 저장소 검사만 수행합니다. 통과는 제품 시험 PASS가 아닙니다.

현재 제품 설치·lint·타입 검사·빌드·단위/mock·통합·API·음성 시험은 DiscordBotLXC에서 수행합니다. OpenJevLXC에는 새 작업을 수행하지 않습니다. 실제 실행 절차는 [개발 안내](CONTRIBUTING.md)와 [원격 개발 runbook](docs/REMOTE_DEVELOPMENT.md)을 따릅니다. 고정 개발 wheel과 의존성 제약은 LXC 후보별로 기록합니다. 정식 출시용 잠금·manifest·최종 인수는 별도로 완료해야 합니다.

GitHub 업로드 범위와 검증 절차는 [Git 안내](docs/GIT_SETUP.md)를 참고하세요. 라이선스는 아직 미지정입니다.
