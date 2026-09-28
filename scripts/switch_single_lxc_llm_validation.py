#!/usr/bin/env python3
"""Temporarily enable GPT-5 nano on the v2 gateway, or restore disabled.

Run as root only on DiscordBotLXC. Existing v1/Jev run and ledger are preserved.
An exact disabled unit is kept for rollback; no key value enters the unit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path

UNIT = Path("/etc/systemd/system/changgeun-jev-api.service")
KEY_FILE = Path("/var/lib/changgeun-jev-api/secrets/openai-validation.env")
TOKEN = Path("/var/lib/changgeun-jev-api/secrets/internal-token")
CERT = Path("/var/lib/changgeun-jev-api/secrets/server.crt")
SERVICE = "changgeun-jev-api.service"


def request(path: str) -> dict[str, object]:
    context = ssl.create_default_context(cafile=str(CERT))
    message = urllib.request.Request(
        "https://127.0.0.1:8443" + path,
        headers={"Authorization": "Bearer " + TOKEN.read_text().strip()},
    )
    with urllib.request.urlopen(message, context=context, timeout=2) as response:
        if response.status != 200:
            raise RuntimeError("gateway not ready")
        body = response.read(65537)
        if len(body) > 65536:
            raise RuntimeError("gateway response too large")
    result = json.loads(body)
    if not isinstance(result, dict):
        raise RuntimeError("invalid gateway response")
    return result


def wait_ready(profile: str, binding: dict[str, object]) -> None:
    for _ in range(30):
        try:
            subprocess.run(["systemctl", "is-active", "--quiet", SERVICE], check=True)
            observed = request("/health")
            if (all(observed.get(key) == value for key, value in binding.items())
                    and observed.get("parser_v2_ready") is True
                    and observed.get("parser_llm_profile") == profile):
                return
        except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError):
            pass
        time.sleep(0.5)
    raise RuntimeError("gateway readiness/profile mismatch")


def install_unit(content: str) -> None:
    temporary = UNIT.with_name(UNIT.name + ".validation-tmp")
    temporary.write_text(content)
    temporary.chmod(0o600)
    os.replace(temporary, UNIT)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "restart", SERVICE], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--enable", action="store_true")
    mode.add_argument("--restore", action="store_true")
    parser.add_argument("--trial-id", required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", args.trial_id):
        parser.error("root and a safe trial ID required on DiscordBotLXC")
    backup = UNIT.with_name(UNIT.name + ".before-gpt-validation-" + args.trial_id)
    os.umask(0o077)
    current = UNIT.read_text()
    observed = request("/health")
    binding = {key: observed[key] for key in
               ("ready", "provider", "profile_id", "config_hash")}
    if binding["ready"] is not True or binding["provider"] != "jev-api":
        parser.error("existing Jev gateway is not ready")
    usage_before = request("/v2/usage")
    reserved = usage_before.get("gpt_reserved_micro_usd")
    limit = usage_before.get("gpt_limit_micro_usd")
    if type(reserved) is not int or limit != 1_000_000 or reserved > limit:
        parser.error("cumulative GPT validation ledger is unavailable")

    if args.enable:
        if backup.exists() or KEY_FILE.is_symlink() or not KEY_FILE.is_file():
            parser.error("validation backup/key state is not fresh")
        if KEY_FILE.stat().st_mode & 0o077:
            parser.error("validation key is not owner-only")
        if observed.get("parser_llm_profile") != "disabled":
            parser.error("gateway is not in disabled profile")
        lines = current.splitlines(keepends=True)
        indexes = [index for index, line in enumerate(lines) if line.startswith("ExecStart=")]
        if len(indexes) != 1 or any(str(KEY_FILE) in line for line in lines):
            parser.error("unexpected gateway unit")
        index = indexes[0]
        argv = shlex.split(lines[index][len("ExecStart="):])
        if ("--parser-v2" not in argv or argv.count("--llm-fallback") != 1
                or argv[argv.index("--llm-fallback") + 1] != "disabled"):
            parser.error("v2 disabled gateway unit required")
        argv[argv.index("--llm-fallback") + 1] = "gpt-5-nano"
        lines[index] = "EnvironmentFile=" + str(KEY_FILE) + "\n" + (
            "ExecStart=" + shlex.join(argv) + "\n")
        backup.write_text(current)
        backup.chmod(0o600)
        try:
            install_unit("".join(lines))
            wait_ready("gpt-5-nano", binding)
        except BaseException:
            install_unit(current)
            wait_ready("disabled", binding)
            raise
        action = "enabled"
    else:
        if not backup.is_file() or str(KEY_FILE) not in current:
            parser.error("no validation unit to restore")
        if observed.get("parser_llm_profile") != "gpt-5-nano":
            parser.error("gateway is not in GPT validation profile")
        disabled = backup.read_text()
        try:
            install_unit(disabled)
            wait_ready("disabled", binding)
        except BaseException:
            install_unit(current)
            wait_ready("gpt-5-nano", binding)
            raise
        KEY_FILE.unlink()
        action = "restored_disabled"
    usage_after = request("/v2/usage")
    if usage_after.get("gpt_reserved_micro_usd", 0) < reserved:
        raise RuntimeError("GPT reservation decreased across service restart")
    print(json.dumps({"action": action, "gateway_ready": True,
                      "gpt_reserved_before": reserved,
                      "gpt_reserved_after": usage_after.get("gpt_reserved_micro_usd"),
                      "gpt_actual_micro_usd": usage_after.get("gpt_actual_micro_usd"),
                      "gpt_limit_micro_usd": limit}))


if __name__ == "__main__":
    main()
