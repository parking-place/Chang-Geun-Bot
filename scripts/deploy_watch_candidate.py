#!/usr/bin/env python3
"""Switch only the development bot; retain the active gateway ledger and old DB pair.

Workstation execution uses stdlib SSH orchestration only. Product work is on LXC.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from test_profile import ssh


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-config", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.ssh_config.is_file() or args.ssh_config.stat().st_mode & 0o077:
        parser.error("restricted SSH configuration required")
    if any(
        not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", v)
        for v in (args.candidate, args.run_id)
    ):
        parser.error("safe new candidate/run identifiers required")
    code = (
        "import json,shlex; from pathlib import Path; "
        "unit=Path('/etc/systemd/system/changgeun-dev-bot.service').read_text(); "
        "argv=shlex.split(next(l[10:] for l in unit.splitlines() if l.startswith('ExecStart='))); "
        "path=argv[argv.index('--config')+1]; c=json.loads(Path(path).read_text()); "
        "print(json.dumps({'binding':c['active_inference'],"
        "'static_text_channels':c['commands']['allowed_text_channel_ids']}))"
    )
    active = json.loads(
        ssh(args.ssh_config, "DiscordBotLXC", ["python3", "-c", code], capture=True)
    )
    if active["binding"]["provider"] != "jev-api":
        parser.error("Jev API must already be active")
    # Current deployments use the isolated gateway account on the same LXC.
    gateway_binding = json.loads(
        ssh(
            args.ssh_config,
            "DiscordBotLXC",
            ["cat", "/var/lib/changgeun-dev/secrets/single-lxc-binding.json"],
            capture=True,
        )
    )
    active["binding"] = gateway_binding
    # A fresh bot run copies the stopped prior DB; gateway is never switched or reset.
    plan = {
        **active,
        "profile": "jev-api",
        "config_id": "eval-jev-api-single-lxc-v1",
        "candidate": args.candidate,
        "run_id": args.run_id,
        "prefix_channels": True,
        "youtube_audio": True,
    }
    controller = "/opt/changgeun-dev/source/scripts/profile_control.py"
    payload = json.dumps(plan).encode()
    ssh(args.ssh_config, "DiscordBotLXC", ["python3", controller, "prepare", "bot"], payload)
    # Probe gateway TLS/binding from the bot before interrupting the running bot.
    ssh(args.ssh_config, "DiscordBotLXC", ["python3", controller, "ready", "bot"], payload)
    try:
        ssh(args.ssh_config, "DiscordBotLXC", ["python3", controller, "stop", "bot"], payload)
        ssh(args.ssh_config, "DiscordBotLXC", ["python3", controller, "ready", "bot"], payload)
        ssh(args.ssh_config, "DiscordBotLXC", ["python3", controller, "install", "bot"], payload)
    except BaseException:
        ssh(args.ssh_config, "DiscordBotLXC", ["python3", controller, "rollback", "bot"], payload)
        raise
    print(
        json.dumps(
            {
                "result": "ACTIVE",
                "candidate": args.candidate,
                "run_id": args.run_id,
                "gateway": "unchanged; ledger/budget retained",
                "formal_release": False,
            }
        )
    )


if __name__ == "__main__":
    main()
