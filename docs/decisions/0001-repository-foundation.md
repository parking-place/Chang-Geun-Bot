# 0001 — 저장소 초기 구조와 실행 경계

- 날짜: 2026-09-27
- 상태: 채택 — 저장소 구조 결정
- 기준: [명세 §18](../../Plans/CHANGGEUN_DEVELOPMENT_SPEC_v1.2.md#s18), [환경 계약](../../Plans/0.DevPhase/ENVIRONMENT.md)

## 선택

기존 Plans 경로를 유지하고 bot/inference 독립 Python 패키지, shared/tests/deploy/scripts/docs/evidence 영역을 추가합니다. 제품 버전 대신 초기 패키지 메타데이터 `0.0.0.dev0`만 사용합니다. 실제 실행 모듈·lock·제품 VERSION은 검증 전 생성하지 않습니다.

`.private`·실제 환경/데이터·모델·로그·백업을 ignore하고, 설정/프로필/systemd는 비밀 없는 placeholder 템플릿으로 작성합니다. GitHub Actions에서는 표준 라이브러리 기반 저장소 파일 검사만 실행합니다. 제품 실행은 지정 LXC로 제한합니다.

## 검증 범위

이번 작업은 디렉터리·메타데이터·ignore·문서/템플릿 준비입니다. 제품 모듈 설치/import/lint/build/시험·LXC 접속·Jev 호출·배포 증거는 없으므로 0.0.0 단계 DONE/PASS를 선언하지 않습니다. 저장소 점검 결과는 제품 기능 검증과 구분합니다.

메타데이터 구성은 [Python 패키징 공식 가이드](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)를 참고했다. 저장소 workflow는 [actions/checkout 공식 저장소](https://github.com/actions/checkout)의 v7 태그를 확인해 commit `3d3c42e5aac5ba805825da76410c181273ba90b1`로 고정하고 인증정보 보존을 끈다. 이 workflow를 원격에서 실행한 결과는 아직 없다.
