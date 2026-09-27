"""Root-only Jev API gateway installation on DiscordBotLXC; secret input via stdin.

Creates a separate Unix service account and loopback TLS endpoint. Existing remote
run data is retained; a new immutable profile epoch rejects old request payloads.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import secrets
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path("/opt/changgeun-dev")
STATE = Path("/var/lib/changgeun-jev-api")
SERVICE = "changgeun-jev-api.service"


def run(argv: list[str]) -> bytes:
    result = subprocess.run(argv, capture_output=True)
    if result.returncode:
        raise SystemExit("gateway preparation failed: " + argv[0])
    return result.stdout


def write(path: Path, data: bytes, uid: int, gid: int, *, immutable: bool = True) -> None:
    if path.exists():
        if immutable and path.read_bytes() != data:
            raise SystemExit("immutable gateway input differs")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    path.chmod(0o600)
    os.chown(path, uid, gid)


def main() -> None:
    if os.geteuid() != 0 or not BASE.is_dir():
        raise SystemExit("prepared DiscordBotLXC deployment account required")
    os.umask(0o077)
    payload = json.load(sys.stdin)
    candidate = payload["candidate"]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", candidate):
        raise SystemExit("invalid candidate")
    try:
        account = pwd.getpwnam("changgeun-gateway")
    except KeyError:
        run(
            [
                "useradd",
                "--system",
                "--home-dir",
                str(STATE),
                "--shell",
                "/usr/sbin/nologin",
                "changgeun-gateway",
            ]
        )
        account = pwd.getpwnam("changgeun-gateway")
    bot = pwd.getpwnam("changgeun-dev")
    runtime = BASE / "candidates" / candidate
    manifest = json.loads((runtime / "candidate.json").read_text())
    if (
        manifest["component"] != "gateway"
        or hashlib.sha256((runtime / "wheels" / manifest["wheel"]).read_bytes()).hexdigest()
        != manifest["wheel_sha256"]
    ):
        raise SystemExit("candidate artifact mismatch")
    # Only this public code runtime changes ownership; old candidate directories stay intact.
    BASE.chmod(BASE.stat().st_mode | 0o001)
    (BASE / "candidates").chmod(0o711)
    # Public runtime is shared read-only, root-owned; credentials stay under STATE/0700.
    for item in [runtime, *runtime.rglob("*")]:
        if item.is_symlink():
            continue
        os.chown(item, 0, 0)
        item.chmod(item.stat().st_mode | 0o444 | (0o111 if item.is_dir() else 0))
    for directory in (
        STATE,
        STATE / "secrets",
        STATE / "runs",
        STATE / "runs" / "single-lxc-20260928",
    ):
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)
        os.chown(directory, account.pw_uid, account.pw_gid)
    secret_dir = STATE / "secrets"
    environment = payload["hosted_env"]
    if (
        not environment.startswith("JEV_HOSTED_API_KEY=")
        or len(environment.strip().splitlines()) != 1
    ):
        raise SystemExit("single hosted credential required")
    write(secret_dir / "hosted.env", environment.encode(), 0, 0)
    token = secret_dir / "internal-token"
    if not token.exists():
        write(token, secrets.token_urlsafe(48).encode(), account.pw_uid, account.pw_gid)
    cert, key = secret_dir / "server.crt", secret_dir / "server.key"
    if not cert.exists():
        run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:3072",
                "-sha256",
                "-nodes",
                "-days",
                "30",
                "-subj",
                "/CN=changgeun-jev-api-local",
                "-addext",
                "subjectAltName=DNS:localhost,IP:127.0.0.1",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            ]
        )
        for item in (cert, key):
            item.chmod(0o600)
            os.chown(item, account.pw_uid, account.pw_gid)
    profile = {
        "profile_id": "eval-jev-api-single-lxc-v1",
        "provider": "jev-api",
        "api_schema_version": "1.2",
        "automatic_provider_retries": 0,
        "automatic_fallback": False,
        "max_provider_calls_per_request": 3,
        "hosted": {
            "endpoint": "https://api.typesafe.ai/v1/systemone",
            "model": "jev-1.13.0",
            "api_key_env": "JEV_HOSTED_API_KEY",
            "max_calls_per_run": 3000,
            "run_purpose": "development-evaluation",
        },
        "decision": {
            "prompt_version": "korean-candidates-dev-v5",
            "confidence_threshold": 0.8,
            "margin_threshold": 0.1,
        },
    }
    run_dir = STATE / "runs" / "single-lxc-20260928"
    profile_path = run_dir / "profile.json"
    write(
        profile_path, json.dumps(profile, sort_keys=True).encode(), account.pw_uid, account.pw_gid
    )
    historical = Path("/var/lib/changgeun-dev/gateway-history-20260928/tombstones.db")
    registry = STATE / "request-tombstones.db"
    if not registry.exists() and historical.is_file():
        shutil.copyfile(historical, registry)
        registry.chmod(0o600)
        os.chown(registry, account.pw_uid, account.pw_gid)
    interpreter = runtime / "jev-api/bin/python"
    metadata = json.loads(
        run(
            [
                "runuser",
                "-u",
                "changgeun-gateway",
                "--",
                str(interpreter),
                "-c",
                "import json,sys; from pathlib import Path; "
                "from changgeun_inference.config import read_profile; "
                "c,h=read_profile(Path(sys.argv[1])); print(json.dumps({'provider':c['provider'],"
                "'profile_id':c['profile_id'],'config_hash':h,'decision':c['decision']}))",
                str(profile_path),
            ]
        )
    )
    bot_secret = Path("/var/lib/changgeun-dev/secrets")
    write(bot_secret / "single-lxc-ca.crt", cert.read_bytes(), bot.pw_uid, bot.pw_gid)
    write(bot_secret / "single-lxc-internal-token", token.read_bytes(), bot.pw_uid, bot.pw_gid)
    binding = {
        **metadata,
        "base_url": "https://127.0.0.1:8443",
        "ca_file": str(bot_secret / "single-lxc-ca.crt"),
        "token_file": str(bot_secret / "single-lxc-internal-token"),
    }
    write(
        bot_secret / "single-lxc-binding.json",
        json.dumps(binding, sort_keys=True).encode(),
        bot.pw_uid,
        bot.pw_gid,
    )
    write(
        bot_secret / "single-lxc-gateway-runtime.json",
        json.dumps(
            {
                "python": str(interpreter),
                "profile": str(profile_path),
                "ledger": str(run_dir / "ledger.db"),
                "run_id": "single-lxc-20260928",
            }
        ).encode(),
        bot.pw_uid,
        bot.pw_gid,
    )
    argv = [
        str(interpreter),
        "-m",
        "changgeun_inference.server",
        "--profile",
        str(profile_path),
        "--ledger",
        str(run_dir / "ledger.db"),
        "--run-id",
        "single-lxc-20260928",
        "--tombstones",
        str(registry),
        "--token-file",
        str(token),
        "--host",
        "127.0.0.1",
        "--port",
        "8443",
        "--tls-cert",
        str(cert),
        "--tls-key",
        str(key),
    ]
    unit = (
        f"[Unit]\nDescription=ChangGeun Jev API gateway (loopback)\nAfter=network-online.target\n"
        f"[Service]\nType=simple\nUser=changgeun-gateway\nGroup=changgeun-gateway\n"
        f"EnvironmentFile={secret_dir}/hosted.env\nWorkingDirectory={run_dir}\n"
        f"ExecStart={shlex.join(argv)}\nRestart=on-failure\nRestartSec=5\nKillSignal=SIGINT\n"
        f"TimeoutStopSec=30\nUMask=0077\nNoNewPrivileges=true\nPrivateTmp=true\n"
        f"ProtectSystem=strict\nProtectHome=true\nReadWritePaths={STATE}\nMemoryMax=384M\n"
        f"[Install]\nWantedBy=multi-user.target\n"
    )
    write(Path("/etc/systemd/system") / SERVICE, unit.encode(), 0, 0)
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "start", SERVICE])
    run(["systemctl", "is-active", "--quiet", SERVICE])
    # A separate account/path prevents the Discord process reading hosted.env or the gateway key.
    denial = subprocess.run(
        ["runuser", "-u", "changgeun-dev", "--", "test", "-r", str(secret_dir / "hosted.env")],
        capture_output=True,
    )
    assert denial.returncode != 0
    print(
        json.dumps(
            {
                "gateway": "active",
                "provider": "jev-api",
                "profile_id": metadata["profile_id"],
                "config_hash": metadata["config_hash"],
                "hosted_key_bot_readable": False,
                "listen": "loopback TLS only",
                "memory_limit": "384M",
                "candidate": candidate,
            }
        )
    )


if __name__ == "__main__":
    main()
