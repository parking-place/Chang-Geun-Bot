#!/usr/bin/env python3
"""Switch one immutable same-LXC gateway wheel without changing its run state.

Run as root on DiscordBotLXC after the candidate has been built and tested.
The old unit is kept for an automatic rollback if readiness fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import re
import shlex
import sqlite3
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path

UNIT = Path("/etc/systemd/system/changgeun-jev-api.service")
SERVICE = "changgeun-jev-api.service"
BASE = Path("/opt/changgeun-dev/candidates")
RUN = Path("/var/lib/changgeun-jev-api/runs/single-lxc-20260928")
TOKEN = Path("/var/lib/changgeun-jev-api/secrets/internal-token")
CERT = Path("/var/lib/changgeun-jev-api/secrets/server.crt")


def call(*args: str) -> None:
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def budget() -> int:
    db = sqlite3.connect((RUN / "ledger.db").as_uri() + "?mode=ro", uri=True)
    try:
        row = db.execute(
            "SELECT calls FROM run_budget WHERE run_id=?", ("single-lxc-20260928",)
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        db.close()


def health() -> dict[str, object]:
    context = ssl.create_default_context(cafile=str(CERT))
    request = urllib.request.Request(
        "https://127.0.0.1:8443/health",
        headers={"Authorization": "Bearer " + TOKEN.read_text().strip()},
    )
    with urllib.request.urlopen(request, context=context, timeout=2) as response:
        if response.status != 200 or int(response.headers.get("content-length", "0")) > 65536:
            raise RuntimeError("gateway health response rejected")
        return json.loads(response.read(65537))


def wait_health(expected: dict[str, object]) -> None:
    for _ in range(30):
        try:
            call("systemctl", "is-active", "--quiet", SERVICE)
            observed = health()
            if all(observed.get(key) == value for key, value in expected.items()):
                return
        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError):
            pass
        time.sleep(0.5)
    raise RuntimeError("gateway readiness/binding failed")


def write_unit(data: str) -> None:
    temporary = UNIT.with_name(UNIT.name + ".patch-tmp")
    temporary.write_text(data)
    temporary.chmod(0o600)
    os.replace(temporary, UNIT)
    call("systemctl", "daemon-reload")
    call("systemctl", "restart", SERVICE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate")
    parser.add_argument("--parser-v2-disabled", action="store_true",
                        help="expose v2 with LLM disabled for isolated Jev evaluation")
    args = parser.parse_args()
    if os.geteuid() != 0 or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", args.candidate):
        parser.error("root and a safe candidate ID required")
    os.umask(0o077)
    candidate = BASE / args.candidate
    manifest = json.loads((candidate / "candidate.json").read_text())
    if manifest["component"] != "gateway" or hashlib.sha256(
        (candidate / "wheels" / manifest["wheel"]).read_bytes()
    ).hexdigest() != manifest["wheel_sha256"]:
        parser.error("gateway artifact mismatch")
    interpreter = candidate / "jev-api/bin/python"
    if not interpreter.is_file():
        parser.error("installed gateway interpreter missing")
    gateway = pwd.getpwnam("changgeun-gateway")
    # The public wheel is root-owned and readable; credentials stay in STATE.
    for item in [candidate, *candidate.rglob("*")]:
        if item.is_symlink():
            continue
        os.chown(item, 0, 0)
        item.chmod(item.stat().st_mode | 0o444 | (0o111 if item.is_dir() else 0))
    call("runuser", "-u", gateway.pw_name, "--", "test", "-x", str(interpreter))
    previous = UNIT.read_text()
    lines = previous.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.startswith("ExecStart=")]
    if len(matches) != 1:
        parser.error("unexpected gateway unit")
    index = matches[0]
    argv = shlex.split(lines[index][len("ExecStart=") :])
    if (
        not argv[0].startswith(str(BASE) + "/")
        or argv[1:3] != ["-m", "changgeun_inference.server"]
        or argv[argv.index("--run-id") + 1] != "single-lxc-20260928"
        or argv[argv.index("--profile") + 1] != str(RUN / "profile.json")
        or argv[argv.index("--ledger") + 1] != str(RUN / "ledger.db")
        or argv[argv.index("--host") + 1] != "127.0.0.1"
        or argv[argv.index("--token-file") + 1] != str(TOKEN)
    ):
        parser.error("existing gateway run binding differs")
    binding = json.loads(
        Path("/var/lib/changgeun-dev/secrets/single-lxc-binding.json").read_text()
    )
    expected = {
        "ready": True,
        "provider": "jev-api",
        "profile_id": binding["profile_id"],
        "config_hash": binding["config_hash"],
    }
    if not all(health().get(key) == value for key, value in expected.items()):
        parser.error("existing gateway is not ready with expected binding")
    if args.parser_v2_disabled:
        if "--tombstones" not in argv:
            parser.error("v2 candidate needs old durable tombstones")
        current_v2 = "--parser-v2" in argv or "--llm-fallback" in argv
        if current_v2 and not (
            argv.count("--parser-v2") == 1 and argv.count("--llm-fallback") == 1
            and argv[argv.index("--llm-fallback") + 1] == "disabled"
        ):
            parser.error("existing v2 profile must be disabled")
    before = budget()
    backup = UNIT.with_name(UNIT.name + ".before-" + args.candidate)
    if backup.exists():
        parser.error("backup already exists; refusing ambiguous rollback")
    backup.write_text(previous)
    backup.chmod(0o600)
    argv[0] = str(interpreter)
    after_expected = dict(expected)
    if args.parser_v2_disabled and not current_v2:
        argv.extend(["--parser-v2", "--llm-fallback", "disabled"])
    if args.parser_v2_disabled:
        after_expected.update(parser_v2_ready=True, parser_llm_profile="disabled")
    lines[index] = "ExecStart=" + shlex.join(argv) + "\n"
    try:
        write_unit("".join(lines))
        wait_health(after_expected)
        after = budget()
        if after < before:
            raise RuntimeError("ledger budget decreased")
    except Exception:
        write_unit(previous)
        wait_health(expected)
        raise
    print(
        json.dumps(
            {
                "candidate": args.candidate,
                "ready": True,
                "budget_before": before,
                "budget_after": after,
                "run_id": "single-lxc-20260928",
                "parser_v2_disabled": args.parser_v2_disabled,
                "rollback_unit": str(backup),
            }
        )
    )


if __name__ == "__main__":
    main()
