# 운영 runbook

지정 LXC에서 개발 봇·게이트웨이 서비스가 실행 중이다. 정식 운영 1.0.0 배포는 전체 인수·잠금 manifest·복원/보안·장시간 시험 후 별도로 확정한다. `deploy/systemd/*.service.example`은 placeholder를 포함한 공개 예시이며 현재 개발 unit을 대신하지 않는다.

현재 [한 LXC 배치](decisions/0008-single-lxc-jev-api.md)에서 봇은 `changgeun-dev`, Jev API 중계는 별도 `changgeun-gateway` 계정으로 실행한다. 중계 unit은 `changgeun-jev-api.service`, 상태/원장은 `/var/lib/changgeun-jev-api`다. 외부 키는 봇 계정에서 읽을 수 없으며 내부 API는 loopback TLS8443만 수신한다. OpenJevLXC에는 새 작업을 수행하지 않는다. 고정 wheel은 `/opt/changgeun-dev/candidates`, run별 DB/원장은 `/opt/changgeun-dev/runs`, 제한 키/CA는 `/var/lib/changgeun-dev/secrets`에 둔다. root가 소유하는 개발 unit은 시스템 경로에 설치하며 서비스 계정에 unit 변경 권한을 주지 않는다. 개발 unit은 자동 부팅 시작으로 활성화하지 않았다.

`ProtectSystem=strict`, `ProtectHome`, `NoNewPrivileges`와 명시 쓰기 경로·메모리 제한을 적용했다. 제공된 privileged LXC는 보존했으며 비root 실행만으로 그 위험을 해소했다고 주장하지 않는다. 내부 HTTPS는 개발 전용 CA를 검증하고 지정 봇에서 gateway 포트에 접근하도록 제한한다. 개발 인증서의 갱신과 운영 PKI는 출시 준비에 포함한다.

[현재 봇 후보 배포 절차](REMOTE_DEVELOPMENT.md)는 사전 TLS readiness 뒤 봇 종료·일관성 DB 복사·고정 후보 시작을 수행하며 중계의 고정 원장/예산을 유지한다. 중계 runtime 변경은 별도 준비/검증으로 수행한다. 전환 실패 시 이전 unit/활성 상태를 복구하도록 구현했다. 전체 장애 주입과 동시 전환 차단 시험은 인수 전이며 동시에 전환하지 않는다. 전환은 현재 음성 재생을 중단한다. 시작 후 자동 음성 입장·재생은 금지한다.

Jev 장애 시 기존 재생·구조화 기능은 게이트웨이에 의존하지 않는다. 자동 재시도나 다른 제공자 fallback을 하지 않는다. timeout/전송 불명/실패 호출을 환불하지 않고 모드별 원장과 공유 요청 소유권을 보존한다. health 확인은 유료 판단을 호출하지 않는다.

SQLite Online Backup API·별도 경로 복원·RSA/CMS AES256-GCM 암호화와 당시 두 노드 사이 암호문 보관을 개발 시험했다. 현재 이전 서버 원본은 보존하고 인증 복원한 역사 백업을 별도 경로에 둔다. 최신 이전 원장 전체 이관은 확인되지 않았으며 과거 두 노드 복사 절차는 현재 인수 증거가 아니다. 변조 암호문 거절도 확인했다. 실제 Jev API 봇/원장 snapshot을 보존하며 운영 보존 주기·주기 복사/실패 통지·전체 RPO/RTO·candidate/lock 연결 인수는 남아 있다. 복원은 원본을 덮어쓰지 않는 지정 LXC의 분리 경로에서 진행해야 한다. 승인 음원 파일/레지스트리와 비밀값은 별도의 제한·암호화 백업 범위이며 공개 소스나 manifest에 넣지 않는다.

실제 Discord 사용자가 시험음 청취와 재생·일시정지·계속·정지를 확인했다. 전체 DJ/non-DJ·버튼·채널 조합, 최소 봇 권한, Jev API 한국어 평가와 8시간 시험은 추가 인수 대상이다.

[0.8.0 운영 계획](../Plans/0.DevPhase/0.8.0/README.md) · [1.0.0 출시 계획](../Plans/0.DevPhase/1.0.0/README.md) · [설정 템플릿](../deploy/README.md) · [증거](../evidence/public/execution-20260927.md)

## 주시 채널 관리

1.0.3의 `/주시 추가·제거·목록·켜기·끄기·점검`은 서버 소유자/서버 관리 권한으로 사용한다. [개발 후보 적용 상태](../evidence/public/watch-channels-20260928.md)를 먼저 확인한다. 추가·제거는 채널 생략 시 현재 채널, 점검은 생략 시 전체 등록 채널이다. 관리 명령은 주시되지 않은 접근 가능한 일반 텍스트 채널에서도 사용할 수 있다. 음악 명령의 일반 허용 채널 정책은 유지한다.

제거/끄기는60초 확인을 요구한다. 현재곡은 계속 재생하며 시작 전 prefix 출처 곡은 승인 만료로 남는다. 새 재생 요청으로 재승인하며 단순 다시 켜기/재등록으로 되살리지 않는다. 마지막 채널 제거는 서버 주시를 끄고, 다시 추가해도 켜기를 별도로 실행해야 한다. 설정과 감사는 재시작 후 유지한다. DB 이관이 실패하면 점검/목록으로 상태를 확인하고 운영자가 제한 초기값/접근을 수정한 뒤 기동 이관을 재시도한다. 관리 명령으로 Portal intent나 권한 overwrite를 바꾸지 않는다.

사용자는 현재 후보에서 목록·점검·끄기 확인 후 접두어 무응답·켜기 후 반응을 정상으로 확인했다. 추가/제거·권한 이벤트·페이지·음성·재시작/복구 전체 인수는 남아 있다.

## 1.1.7 인증서·서비스 수명 사전 점검

DiscordBotLXC root에서 공개 소스를 동기화한 뒤 다음 읽기 전용 점검을 실행한다. 현재 서비스 이름은 `changgeun-jev-api.service`와 `changgeun-dev-bot.service`다.

```bash
python3 /opt/changgeun-dev/source/scripts/check_gateway_lifetime.py
```

종료 코드 0은 현재 인증서가 14일보다 더 남고, loopback TLS의 호스트·CA·실제 인증서가 일치하며, 두 서비스가 실행 중이고, 봇 계정에서 게이트웨이 키·hosted 환경 파일을 읽지 못함을 뜻한다. JSON의 `service_boot`는 자동 부팅 설정을 별도로 보여준다. 종료 코드 2는 남은 기간이 14/7/1일 경계에 들어간 경고/긴급/위험 상태이고, 1은 파일·권한·TLS·서비스 점검 실패다. 종료 0만으로 자동 시작, 인증서 갱신, 알림 전송, 재부팅 복귀 인수를 통과한 것은 아니다.

실제 인증서 교체 전에 새 인증서의 SAN·만료일·CA 체인과 양 계정의 권한을 제한 경로에서 확인한다. 새 CA를 사용하는 경우 봇의 trust 교체와 중계 인증서 교체를 한 전환으로 계획하고, 기존 파일/서비스/원장 사본과 rollback 경로를 먼저 고정한다. 중계 재시작 후 무료 TLS readiness와 위 점검을 다시 실행하고 봇의 기존 연결을 갱신한다. 실패하면 보존한 기존 인증서·CA·unit로 복귀하며 고정 epoch·원장·tombstone·예산은 되감지 않는다. 자동 부팅과 경보 수신 대상은 운영 전환 승인 및 재부팅/복귀 검증 때 설정한다. [1.1.7 실행 기록](../evidence/public/patch-117-development-20260928.md)에 현재 미완료 조건을 기록한다.

사용자 지시에 따라 이번 1.1.7의 서버 외부 암호화 백업·격리 복원 검증은 건너뛰었다. 이를 복구 PASS로 해석하거나 현재 원장을 과거 백업으로 덮어쓰지 않는다.
