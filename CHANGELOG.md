# 변경 기록

## Unreleased

- 1.0.3 `/주시`6명령·관리자 전용 확인·서버별 DB 설정/최초 이관·prefix 출처/세대·선별 취소·승인 만료 큐·채널 진단 구현. 봇328/gateway41 LXC 자동 회귀 통과. [후보/실제 인수 범위](evidence/public/watch-channels-20260928.md).

- 1.0.3 주시 채널 관리5단계 계획·W-01~20과 출시 기준 추가. 개발 봇 적용 후 사용자가 목록·점검·끄기·켜기/접두어 동작 정상 확인. 전체 W 인수는 진행 중.
- OpenJevLXC 사용을 종료하고 별도 계정/loopback TLS의 Jev API 중계를 DiscordBotLXC에 적용. 기존 서버 데이터·예산은 보존하며 새로운 고정 실행 epoch를 사용. [배치 결정](docs/decisions/0008-single-lxc-jev-api.md).

- 1.0.1 YouTube 영상 재생·1.0.2 지정 채널 `!!창근아` 한국어 명령의 10단계 계획과 후속 시험/출시 기준 추가. 개발 후보·부분 LXC 검증 진행 중.

- 공개 YouTube 단일곡/검색 선택·PCM worker, 접두어 두 채널·영속 중복/취소 원장 구현. 정지 상태의 지정곡 우선 시작과 정지 후 동일곡 재요청을 수정. YouTube URL의 https:// 생략 입력과 영상ID 대소문자 보존을 지원. [검증 범위](evidence/public/youtube-prefix-20260928.md).

- 개발 명세1.3·전 버전 계획·코드/설정을 사용자 지시에 따라 Jev API 전용으로 개정. 기존 로컬 모델 시험 기록은 보존.
- bot/inference/shared/tests/deploy/scripts 초기 디렉터리와 Python 패키지 메타데이터 추가.
- Git 제외 규칙, 편집/줄바꿈 설정, 공개 README·개발/원격 실행 안내 추가.
- 비밀 없는 Jev API·격리 mock 프로필·환경·systemd 템플릿, 저장소 파일 검사와 GitHub 양식 추가.

제품 구현과 부분 LXC 시험은 진행 중이며 정식 릴리스 이력은 아직 없습니다. 실제 제품 버전은 해당 게이트를 통과한 뒤 별도로 기록합니다.
