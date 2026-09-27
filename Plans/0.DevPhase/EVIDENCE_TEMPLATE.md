# LXC 검증 증거 양식

이 문서는 양식이다. 빈칸·체크박스·목표 수치를 실제 시험 결과로 취급하지 않는다. 단계마다 아래 항목을 채우고 [STATUS](STATUS.md)에 해당 증거 링크를 연결한다.

## 실행 식별

| 항목 | 기록할 값 |
| --- | --- |
| 버전 / 단계 / run_id | 예: 0.4.0 / 03 / UTC 시각을 포함한 고유 ID |
| 실행 상태 | NOT_RUN / PASS / FAIL / BLOCKED / SKIPPED |
| 시험 목적과 시나리오 | T/N/P/O/E/B ID 및 재현 조건 |
| 시작·종료 시각 | UTC 저장, 필요 시 Asia/Seoul 표시 |
| 실행 서버 | DiscordBotLXC: 봇 / 중계 / 둘 모두 |
| 소스 revision | Git SHA; Git 도입 전 소스 파일 목록·내용 해시 |
| 작업 트리 변경 | 있음/없음, 추가 변경의 diff와 해시 |
| 패키지·런타임 | OS/Python, 각 lock hash, 음성/FFmpeg 버전 |
| 추론 프로필 | provider, profile_id, run_id, 실행 세대, 비밀 제외 config_hash; mock/실제 구분 |
| 공통 추론 구성 | API schema1.2, adapter/lock, prompt/threshold version, 후보/평가 hash |
| 제공자별 구성 | Jev API API/요청·반환 model/측정시각, 미공개 revision=null·source=unavailable |
| 호스팅 범위 | 익명/합성 입력 여부·전송 범위, run 호출 한도/사용량·비용 출처; 미제공 값 unknown |
| 환경 | 제공/실측 자원, 스레드, worker/동시/대기 수, 음성 재생 여부 |
| 데이터·설정 | DB schema, fixture/평가 세트 hash, 비밀 제외 설정 hash |
| 실행 명령 | 해당 LXC에서 실제 사용한 명령과 작업 디렉터리 |
| 결과 파일 | 비밀 제거 로그, 보고서, 비교 결과의 상대 링크 |

## 결과 기록

| 시험 ID | 기대 결과 | 실제 결과 | 판정 | 증거 | 실패/skip 이유 |
| --- | --- | --- | --- | --- | --- |
| <ID> | <변경 대상·권한·호출 수 등> | <관측값> | NOT_RUN | <링크> | <이유> |

재현 가능한 입력·사전 DB/큐 상태·actor 역할·기대 버전·실제 변경 횟수를 기록한다. 자연어는 사용 단계·provider dispatch 누계와 hosted forward 미관측(null/unavailable)·조기 종료 이유·3단계 진입 사유·기한·취소 후 결과 폐기를 포함한다. 후보/설정 변경의 이전/이후 설정 해시·drain·불명 요청 보존·이전 ID 차단·데이터 격리 결과를 B-08/09 증거로 남긴다. API 성공만으로 Discord 동작이나 DB 변경 성공을 판정하지 않는다.

성능 보고에는 표본 수·준비 호출·프롬프트 길이·대기 조건·median/p95/max·timeout/취소/오류율을 남긴다. 정상 성공 지연만 뽑아 보고하지 않는다. 백업/복원에는 생성·전송·무결성·복원 시간과 확인 토큰 무효화·자동 음성 재개 없음의 증거를 남긴다.

## 완료 판정

- [ ] 선택 프로필·API·설정 해시가 봇과 게이트웨이에서 일치하고 개발·mock·최종 결과를 합치지 않았다.
- [ ] Jev API 호출 수를 실측 forward로 기록하지 않았다.
- [ ] 소스와 구성 revision이 해당 후보와 일치한다.
- [ ] 모든 필수 항목이 실행되었고 FAIL/SKIPPED/BLOCKED를 PASS로 합치지 않았다.
- [ ] 실제 실행 서버가 현재 지정 DiscordBotLXC이며 로컬 시험 결과를 사용하지 않았다.
- [ ] 비밀값·접속 정보·개인 원문·서명된 URL을 제거했다.
- [ ] 다른 기능과의 회귀 범위 및 미지원 제한을 기록했다.
- [ ] 단계 통과 여부, 남은 차단 항목, 다음 단계 진입 가능 여부를 기록했다.

개발 중 증거 보관 경로는 `evidence/<version>/<phase>/<profile>/<run_id>/`로 정할 수 있다. 공개 부분 실행 요약은 `evidence/public/`에 있으며 민감 원본은 LXC 제한 경로에 보관한다. 공개 요약에는 비밀 제거 정보만 저장하고 민감 원본은 접근통제된 별도 경로에 보관한다. 운영자·사용자 ID를 불필요하게 공개하지 않는다.

프로필별 준비·실패·미실행·차단을 각각 기록한다. 동일 fixture/seed/snapshot이라도 응답의 완전 일치를 요구하지 않는다. [INFERENCE_PROFILES](INFERENCE_PROFILES.md)의 공통 안전 계약과 Jev API 품질 기준으로 판정한다.

실제 원본 결과는 기본 Git 제외 대상이다. 비밀값을 제거하고 검토한 Markdown 요약만 `evidence/public/`에 작성한다. [보관 안내](../../evidence/README.md)를 따른다.
