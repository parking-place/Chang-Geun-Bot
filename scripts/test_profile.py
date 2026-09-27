#!/usr/bin/env python3
"""Explicit LXC profile selection. No product code runs on this workstation."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import uuid
from pathlib import Path


def ssh(
    config: Path,
    host: str,
    command: list[str],
    payload: bytes | None = None,
    *,
    capture: bool = False,
) -> bytes:
    completed = subprocess.run(
        ["ssh", "-F", str(config.resolve()), host, shlex.join(command)],
        input=payload,
        check=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return completed.stdout if capture else b""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-config", type=Path, required=True)
    parser.add_argument("--profile", choices=("jev-api", "mock"), required=True)
    parser.add_argument(
        "--suite",
        choices=("contract", "activate", "status", "transport", "korean-eval"),
        required=True,
    )
    parser.add_argument(
        "--config-id",
        choices=("eval-jev-api-single-lxc-v1",),
        default="eval-jev-api-single-lxc-v1",
    )
    parser.add_argument("--candidate", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--prefix-channels", action="store_true")
    parser.add_argument("--youtube-audio", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.profile == "mock" and args.suite != "contract":
        parser.error("mock supports isolated contract tests only")
    if args.suite == "activate":
        if any(
            not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", value)
            for value in (args.candidate, args.run_id)
        ):
            parser.error("activate requires safe --candidate and --run-id identifiers")
        if not args.prefix_channels or not args.youtube_audio:
            parser.error("watch activation requires --prefix-channels --youtube-audio")
    plan = {
        "profile": args.profile,
        "suite": args.suite,
        "config_id": args.config_id,
        "candidate": args.candidate or None,
        "run_id": args.run_id or None,
        "hosts": ["DiscordBotLXC"],
        "automatic_fallback": False,
        "automatic_retries": 0,
        "prefix_channels": args.prefix_channels,
        "youtube_audio": args.youtube_audio,
    }
    if args.dry_run:
        print(json.dumps(plan, sort_keys=True))
        return
    config = args.ssh_config
    if not config.is_file() or config.stat().st_mode & 0o077:
        parser.error("SSH configuration must be a restricted private file")
    root = Path(__file__).resolve().parents[1]
    runtime = json.loads(
        ssh(
            config,
            "DiscordBotLXC",
            ["cat", "/var/lib/changgeun-dev/secrets/single-lxc-gateway-runtime.json"],
            capture=True,
        )
    )
    code = (
        "import json,shlex,subprocess; from pathlib import Path; "
        "unit=Path('/etc/systemd/system/changgeun-dev-bot.service').read_text(); "
        "argv=shlex.split(next(l[10:] for l in unit.splitlines() "
        "if l.startswith('ExecStart='))); "
        "path=argv[argv.index('--config')+1]; c=json.loads(Path(path).read_text()); "
        "subprocess.run(['systemctl','is-active','--quiet','changgeun-dev-bot'],check=True); "
        "print(json.dumps({'binding':c['active_inference'],'python':argv[0],'config':path}))"
    )
    active = json.loads(ssh(config, "DiscordBotLXC", ["python3", "-c", code], capture=True))
    if args.suite == "contract":
        # No paid/model dispatches. Selecting a real profile does not relabel mocks.
        for interpreter, tests in (
            (
                active["python"],
                [
                    "tests/unit",
                    "tests/integration",
                    "tests/safety/test_pipeline.py",
                    "tests/safety/test_gateway_client.py",
                ],
            ),
            (
                runtime["python"],
                [
                    "tests/safety/test_gateway.py",
                    "tests/safety/test_gateway_restore.py",
                    "tests/safety/test_profile_budget.py",
                ],
            ),
        ):
            subprocess.run(
                [
                    "python3",
                    str(root / "scripts/remote.py"),
                    "--ssh-config",
                    str(config),
                    "--host",
                    "DiscordBotLXC",
                    "--sync",
                    "--",
                    "env",
                    "PYTHONPATH="
                    + str(Path(interpreter).parent.parent / "lib/python3.13/site-packages"),
                    "/opt/changgeun-dev/venv/bin/python",
                    "-m",
                    "pytest",
                    *tests,
                    "-q",
                ],
                check=True,
            )
        print(
            json.dumps(
                {
                    **plan,
                    "result": "PASS",
                    "evidence_scope": "unit/mock/contract",
                    "real_provider_quality": "NOT_RUN",
                }
            )
        )
        return
    if args.suite in {"status", "transport", "korean-eval"}:
        if active["binding"]["provider"] != args.profile:
            parser.error("selected profile is not active; activate it explicitly first")
        ssh(config, "DiscordBotLXC", ["systemctl", "is-active", "--quiet", "changgeun-jev-api"])
        if args.suite == "korean-eval":
            # Development fixture only; no local product imports or held-out claims.
            dataset = root / "tests/nlp_eval/development.json"
            rows = json.loads(dataset.read_text())["cases"]
            maximum = len(rows) * 3
            if not 1 <= len(rows) <= 200:
                parser.error("invalid development evaluation size")
            preflight = (
                "import json,sqlite3,sys; from pathlib import Path; "
                "from changgeun_inference.config import read_profile; "
                "p=Path(sys.argv[1]).parent; c,h=read_profile(Path(sys.argv[1])); "
                "assert c['provider']=='jev-api' and c['profile_id'].startswith('eval-'); "
                "assert c['hosted']['run_purpose']=='development-evaluation'; "
                "assert h==sys.argv[2]; run='single-lxc-20260928'; "
                "db=sqlite3.connect((p/'ledger.db').resolve().as_uri()+'?mode=ro',uri=True); "
                "row=db.execute('SELECT calls FROM run_budget WHERE run_id=?',(run,)).fetchone(); "
                "used=row[0] if row else 0; limit=c['hosted']['max_calls_per_run']; "
                "assert limit-used>=int(sys.argv[3]); "
                "print(json.dumps({'run_id':run,'reserved_calls':used,'limit':limit,"
                "'planned_maximum':int(sys.argv[3])}))"
            )
            gateway_python = runtime["python"]
            budget = json.loads(
                ssh(
                    config,
                    "DiscordBotLXC",
                    [
                        "runuser",
                        "-u",
                        "changgeun-gateway",
                        "--",
                        gateway_python,
                        "-c",
                        preflight,
                        runtime["profile"],
                        active["binding"]["config_hash"],
                        str(maximum),
                    ],
                    capture=True,
                )
            )
            output = str(
                Path(active["config"]).parent / ("korean-development-" + uuid.uuid4().hex + ".json")
            )
            print(
                json.dumps({"scope": "development only; not held-out acceptance", **budget}),
                flush=True,
            )
            ssh(
                config,
                "DiscordBotLXC",
                [
                    "runuser",
                    "-u",
                    "changgeun-dev",
                    "--",
                    active["python"],
                    "/opt/changgeun-dev/source/scripts/probe_pipeline.py",
                    "--config",
                    active["config"],
                    "--dataset",
                    "/opt/changgeun-dev/source/tests/nlp_eval/development.json",
                    "--output",
                    output,
                ],
            )
            return
        if args.suite == "transport":
            ssh(
                config,
                "DiscordBotLXC",
                [
                    "runuser",
                    "-u",
                    "changgeun-dev",
                    "--",
                    active["python"],
                    "/opt/changgeun-dev/source/scripts/probe_transport.py",
                    "--config",
                    active["config"],
                ],
            )
        else:
            check = (
                "import asyncio,sys; from pathlib import Path; "
                "from changgeun.config import BotConfig; "
                "from changgeun.nlp.client import GatewayClient; "
                "asyncio.run(GatewayClient(BotConfig.read(Path(sys.argv[1])).inference).ready())"
            )
            ssh(
                config,
                "DiscordBotLXC",
                [
                    "runuser",
                    "-u",
                    "changgeun-dev",
                    "--",
                    active["python"],
                    "-c",
                    check,
                    active["config"],
                ],
            )
            print(
                json.dumps(
                    {
                        "result": "READY",
                        "profile": args.profile,
                        "profile_id": active["binding"]["profile_id"],
                        "config_hash": active["binding"]["config_hash"],
                        "provider_calls": 0,
                    }
                )
            )
        return
    # Only the bot switches; the separately prepared same-LXC gateway keeps its state.
    if args.profile != "jev-api":
        parser.error("live activation requires Jev API")
    subprocess.run(
        [
            "python3",
            str(root / "scripts/deploy_watch_candidate.py"),
            "--ssh-config",
            str(config),
            "--candidate",
            args.candidate,
            "--run-id",
            args.run_id,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
