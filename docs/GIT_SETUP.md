# Git 업로드 준비

저장소 대상은 `.private/GitHub-info`에 제공된 [parking-place/Chang-Geun-Bot](https://github.com/parking-place/Chang-Geun-Bot)입니다. 로컬 기본 브랜치는 `main`, 원격 이름은 `origin`을 사용합니다. 2026-09-28 사용자가 1.0.3 구현과 GitHub 업로드를 요청했습니다. 초기 원격은 공개 빈 저장소로 확인했으며 이 작업에서 검증한 공개 소스를 최초 main 커밋으로 올립니다. 정식 VERSION/릴리스 태그는 포함하지 않습니다.

## 업로드 전에

```bash
python3 scripts/check_repository.py
git status --short --untracked-files=all
git check-ignore -v .private/GitHub-info .private/Jev-API-key .private/ServerInfo
git add --dry-run .
```

저장소 검사는 공개 후보의 문서·TOML/JSON·ignore·비밀값 패턴만 점검합니다. 마지막 명령은 추가할 파일 목록만 보여주고 stage하지 않습니다. `.private`, 실제 `.env`, DB/원장·모델·로그·백업이 후보에 없어야 합니다. `.gitignore`는 이미 추적한 파일의 과거 기록을 지우지 않으므로 강제 추가를 사용하지 않습니다.

## 첫 커밋/업로드 시 사용할 절차

이번 업로드와 후속 업로드에서 다음 절차를 사용합니다. 실제 업로드 SHA와 CI 결과는 Git 이력 및 해당 GitHub 실행에서 확인합니다.

1. `git remote -v`와 Git 작성자 설정을 확인합니다. 실제 이름/이메일은 사용자 본인의 값을 사용합니다.
2. `git ls-remote --heads origin`으로 원격에 기존 브랜치/커밋이 있는지 확인합니다. 원격이 비어 있지 않으면 기존 이력과 통합할 경로를 먼저 정합니다.
3. 파일 목록을 확인한 뒤 `git add .`, `git diff --cached --stat`, `git diff --cached --check`, `python3 scripts/check_repository.py`로 stage된 내용을 점검합니다.
4. 확인한 내용을 첫 커밋으로 기록하고 기존 이력과 맞는 방식으로 `git push -u origin main`을 수행합니다. 강제 push로 원격 이력을 덮어쓰지 않습니다.

GitHub 로그인/인증은 환경의 credential manager 또는 사용자 인증을 사용합니다. 토큰을 remote URL이나 문서에 포함하지 않습니다. 저장소 공개/비공개 설정은 변경하지 않으며 라이선스는 아직 미지정입니다. `.private`·실제 키/설정·DB/원장·백업과 LXC runtime은 업로드하지 않습니다.
