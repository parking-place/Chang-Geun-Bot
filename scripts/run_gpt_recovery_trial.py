#!/usr/bin/env python3
"""Temporarily stop the test bot, test GPT recovery, and restore disabled mode.

This local script only orchestrates SSH and transfers the user-provided key via
stdin. Every product operation runs on DiscordBotLXC. A failed restoration
leaves the bot stopped rather than starting it against the wrong LLM profile.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

from test_profile import ssh

SOURCE = "/opt/changgeun-dev/source"
CONFIG = "/opt/changgeun-dev/runs/recon120p12j-20260928/jev-api/bot-config.yaml"
OUTPUT_DIR = "/opt/changgeun-dev/runs/recon120p12j-20260928/jev-api"
KEY_FILE = "/var/lib/changgeun-jev-api/secrets/openai-validation.env"
SWITCH = SOURCE + "/scripts/switch_single_lxc_llm_validation.py"
PROFILE_CODE = (
    "import importlib.util; from pathlib import Path; "
    "p=Path('/opt/changgeun-dev/source/scripts/switch_single_lxc_llm_validation.py'); "
    "s=importlib.util.spec_from_file_location('gpt_switch',p); "
    "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
    "print(m.request('/health')['parser_llm_profile'])"
)
REMOVE_KEY_CODE = (
    "from pathlib import Path; "
    "p=Path('/var/lib/changgeun-jev-api/secrets/openai-validation.env'); "
    "assert not p.is_symlink(); p.unlink(missing_ok=True)"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-config", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--only", nargs="+", required=True)
    parser.add_argument("--force-full-parse", action="store_true")
    args = parser.parse_args()
    if (not args.ssh_config.is_file() or args.ssh_config.stat().st_mode & 0o077
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", args.trial_id)
            or not 1 <= len(args.only) <= 3
            or any(not re.fullmatch(r"C(?:0[1-9]|[1-4][0-9])", item)
                   for item in args.only)):
        parser.error("restricted SSH and one to three safe cases/trial ID required")

    def remote(command: list[str], *, capture: bool = False) -> bytes:
        return ssh(args.ssh_config, "DiscordBotLXC", command, capture=capture)

    def profile() -> str:
        return remote(["python3", "-c", PROFILE_CODE], capture=True).decode().strip()

    remote(["systemctl", "is-active", "--quiet", "changgeun-dev-bot.service"])
    if profile() != "disabled":
        parser.error("active gateway must start in disabled profile")
    remote(["test", "!", "-e", KEY_FILE])
    subprocess.run([
        sys.executable, str(Path(__file__).with_name("provision_gpt_validation_key.py")),
        "--ssh-config", str(args.ssh_config), "--source", str(args.source),
        "--host", "DiscordBotLXC",
    ], check=True)
    bot_stopped = False
    try:
        remote(["systemctl", "stop", "changgeun-dev-bot.service"])
        bot_stopped = True
        remote(["python3", SWITCH, "--enable", "--trial-id", args.trial_id])
        remote([
            "runuser", "-u", "changgeun-dev", "--", "env",
            "PYTHONPATH=" + SOURCE + "/bot/src:" + SOURCE + "/inference/src",
            "/opt/changgeun-dev/venv/bin/python",
            SOURCE + "/scripts/probe_reconstruction_gpt_recovery.py",
            "--config", CONFIG,
            "--dataset", SOURCE + "/tests/nlp_eval/development_v2_command_selection.json",
            "--output", OUTPUT_DIR + "/gpt-recovery-" + args.trial_id + ".json",
            "--only", *args.only,
        ] + (["--force-full-parse"] if args.force_full_parse else []))
    finally:
        current = profile()
        if current == "gpt-5-nano":
            remote(["python3", SWITCH, "--restore", "--trial-id", args.trial_id])
            current = profile()
        if current != "disabled":
            raise RuntimeError("gateway profile not restored; bot remains stopped")
        remote(["python3", "-c", REMOVE_KEY_CODE])
        if bot_stopped:
            remote(["systemctl", "start", "changgeun-dev-bot.service"])
            time.sleep(2)
            remote(["systemctl", "is-active", "--quiet", "changgeun-dev-bot.service"])
        print("GPT trial ended; gateway disabled, key removed, test bot active")


if __name__ == "__main__":
    main()
