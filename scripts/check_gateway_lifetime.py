#!/usr/bin/env python3
"""Read-only same-LXC gateway certificate and key-separation preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import ssl
import subprocess
from datetime import UTC, datetime
from pathlib import Path

STATE = Path("/var/lib/changgeun-jev-api/secrets")
BOT_CA = Path("/var/lib/changgeun-dev/secrets/single-lxc-ca.crt")


def expiry_level(days: float) -> str:
    if days <= 1:
        return "critical"
    if days <= 7:
        return "urgent"
    if days <= 14:
        return "warning"
    return "ok"


def certificate_expiry(cert: Path) -> datetime:
    completed = subprocess.run(
        ["openssl", "x509", "-in", str(cert), "-noout", "-enddate"],
        check=True,
        capture_output=True,
        text=True,
    )
    line = completed.stdout.strip()
    if not line.startswith("notAfter="):
        raise ValueError("certificate expiry unavailable")
    return datetime.strptime(line.removeprefix("notAfter="), "%b %d %H:%M:%S %Y %Z").replace(
        tzinfo=UTC
    )


def denied_to_bot(path: Path) -> bool:
    return subprocess.run(
        ["runuser", "-u", "changgeun-dev", "--", "test", "-r", str(path)],
        capture_output=True,
    ).returncode != 0


def tls_fingerprint(cert: Path) -> str:
    context = ssl.create_default_context(cafile=str(BOT_CA))
    with socket.create_connection(("127.0.0.1", 8443), timeout=2) as connection:
        with context.wrap_socket(connection, server_hostname="localhost") as secured:
            peer = secured.getpeercert(binary_form=True)
    if peer is None:
        raise ValueError("gateway did not present a certificate")
    local = ssl.PEM_cert_to_DER_cert(cert.read_text())
    if peer != local:
        raise ValueError("gateway certificate differs from trusted local file")
    return hashlib.sha256(peer).hexdigest()


def check() -> dict[str, object]:
    cert, key, hosted = (
        STATE / "server.crt",
        STATE / "server.key",
        STATE / "hosted.env",
    )
    for path in (cert, key, hosted, BOT_CA):
        if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
            raise ValueError("gateway credential file is missing or broadly readable")
    if not denied_to_bot(key) or not denied_to_bot(hosted):
        raise ValueError("bot can read gateway-only credentials")
    services = ("changgeun-jev-api.service", "changgeun-dev-bot.service")
    service_state = {
        name: subprocess.run(
            ["systemctl", "is-active", "--quiet", name], capture_output=True
        ).returncode == 0
        for name in services
    }
    if not all(service_state.values()):
        raise ValueError("a required service is inactive")
    boot_state = {
        name: subprocess.run(
            ["systemctl", "is-enabled", name], capture_output=True, text=True
        ).stdout.strip()
        for name in services
    }
    expires = certificate_expiry(cert)
    days = (expires - datetime.now(UTC)).total_seconds() / 86400
    return {
        "status": expiry_level(days),
        "expires_utc": expires.isoformat(),
        "remaining_days": round(days, 2),
        "tls_certificate_sha256": tls_fingerprint(cert),
        "tls_validated": True,
        "key_separation": "PASS",
        "service_active": service_state,
        "service_boot": boot_state,
        "threshold_days": [14, 7, 1],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if os.geteuid() != 0 or not Path(__file__).resolve().is_relative_to(
        Path("/opt/changgeun-dev/source")
    ):
        parser.error("prepared DiscordBotLXC root account required")
    try:
        result = check()
    except (OSError, ValueError, subprocess.CalledProcessError, ssl.SSLError) as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None
    print(json.dumps(result))
    if result["status"] != "ok":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
