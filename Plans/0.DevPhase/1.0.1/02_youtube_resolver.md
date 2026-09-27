# 1.0.1 Phase 2 — 비동기 YouTube resolver

- 상태: **IN_PROGRESS — 개발 후보·부분 LXC 검증; 전체 인수 전**
- 선행: [Phase 1](01_source_contract_and_feasibility.md)의 어댑터·전송·오류 계약.
- 구현 위치: `bot/src/changgeun/providers/media.py`의 공통 경계와 신규 YouTube 오디오 어댑터, `bot/src/changgeun/config.py`, candidate 의존성 준비 코드. 실제 파일명은 구현 시 확정한다.

## 작업

- 동기 로컬 Path resolver를 공통 비동기 인터페이스로 감싼다. 승인 음원 어댑터와 YouTube 어댑터의 can-play/resolve/cancel/cleanup을 분리하고 SQL transaction·Discord event loop에서 외부 해석을 기다리지 않는다.
- 입력을 HTTPS YouTube 허용 호스트와 검증한 video ID로 정규화한다. 중복 `v`, 자격정보/포트, 임의 URL·로컬 파일·사설 IP·다른 프로토콜을 거절한다. canonical watch URL을 생성해 단일 영상 모드로 전달하며 사용자 원문을 CLI 옵션으로 전달하지 않는다.
- yt-dlp를 채택하면 shell 없는 인자 배열/고정 라이브러리 옵션, 무시된 사용자 설정·플러그인, 다운로드/로그/재시도 제한을 사용한다. JS/EJS 의존성도 빌드 단계에서 고정하고 실행 중 다운로드·자동 업데이트하지 않는다.
- redirect·DNS·manifest 내 segment/key URI·최종 CDN까지 검증된 HTTPS/공인 목적지만 허용한다. extractor와 FFmpeg 자체 통신에도 같은 egress 제한이 적용되어야 한다. 도메인 문자열 검사나 최초 URL 검사만으로 완료하지 않는다. CDN 허용 목록은 실제 probe 근거로 버전 관리한다.
- FFmpeg에는 사용자 URL·헤더·옵션을 직접 전달하지 않는다. 미디어 프록시/pipe 또는 동등한 네트워크 제한 경계를 선택해 내부 주소 접근과 서명 URL의 프로세스 목록·stderr 노출을 차단한다. 재생에 필요한 데이터는 버퍼로 처리하며 영상 파일을 영구 저장하지 않는다.
- 현재 항목 준비 접수부터 대기·재시도 포함 총25초와 누적 resolve15초/누적 startup10초를 적용하고 각 작업은 남은 기한으로 절삭한다. semaphore는 동시1/대기4이며 retry가 시계를 초기화하지 않는다. 하위 프로세스 그룹을 관리하고 취소 시 종료→회수→버퍼 폐기한다. 대기 중 cancel도 즉시 제거한다.

## 산출물

엄격한 source/config 계약·고정 의존성 manifest·URL/egress validator·분류된 오류·취소 가능한 resolver·fixture 회귀. 기존 설정은 기능 off로 읽히고 미준비 기능 on은 분명한 시작 오류여야 한다. 새 설정은 구현 전 deploy 템플릿에 동작하는 값처럼 추가하지 않는다.

## LXC 시험과 통과

| 시험 | 필수 결과 |
| --- | --- |
| Y-04 | watch/shorts/embed/짧은 링크의 같은 ID 정규화, 잘못된 형식 거절, list 부착 URL의 단일 영상 처리 |
| Y-05 | redirect·DNS 변경·사설/loopback/metadata 주소·manifest segment·file/concat 프로토콜의 실제 연결 차단 |
| Y-06 | 동시1·대기4·25초 총기한/15초 해석/10초 시작 한도, event loop 응답 유지, 초과/취소 뒤 worker와 FD 회수 |
| Y-07 | 서명 URL/헤더·외부 키·원문이 DB/백업/로그/argv/오류 응답에 없음, URL 만료·cleanup 검증 |
| Y-08 | 새 후보 무쿠키·무자동업데이트·고정 의존성으로 재현, 승인 음원 기존 resolver 회귀 PASS |

mock HTTP/프로세스 시험과 실제 CDN 전송 증거를 구분한다. 네트워크 경계가 fixture에서만 확인됐다면 실재생 안전 인수는 미완료다. 다음: [Phase 3](03_commands_queue_and_playback.md).

## 2026-09-28 개발 기록

[고정 후보와 부분 실행 증거](../../../evidence/public/youtube-prefix-20260928.md)를 따른다. 단위/mock·실제 API·첫 PCM·Discord 사용자 청취를 구분하며 아래 필수 인수 조건은 유지한다. 부분 성공만으로 이 단계나 전체 버전을 VERIFIED/DONE으로 표시하지 않는다.
