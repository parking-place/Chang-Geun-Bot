"""Restricted development-service controller. Executed ONLY on the designated LXC."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

BASE = Path("/opt/changgeun-dev")
SECRETS = Path("/var/lib/changgeun-dev/secrets")


def run(command: list[str], *, capture: bool = False, data: bytes | None = None) -> bytes:
    completed = subprocess.run(
        command,
        input=data,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return completed.stdout if capture else b""


def private_write(path: Path, content: str, *, root_owner: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".new")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(content)
    account = pwd.getpwnam("changgeun-dev")
    os.chown(temporary, 0 if root_owner else account.pw_uid, 0 if root_owner else account.pw_gid)
    temporary.chmod(0o600)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "stop", "install", "ready", "rollback"))
    parser.add_argument("component", choices=("gateway", "bot"))
    args = parser.parse_args()
    if os.geteuid() != 0 or not BASE.is_dir() or not SECRETS.is_dir():
        parser.error("controller requires the prepared development LXC")
    os.umask(0o077)
    plan = json.load(sys.stdin)
    profile, candidate, run_id = (plan[key] for key in ("profile", "candidate", "run_id"))
    if profile != "jev-api" or any(
        not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", value)
        for value in (candidate, run_id)
    ):
        parser.error("invalid explicit profile/candidate/run")
    config_id = plan.get("config_id", "jev-api")
    if config_id not in {
        "jev-api",
        "eval-jev-api",
        "eval-jev-api-v3",
        "eval-jev-api-v4",
        "eval-jev-api-v5",
        "eval-jev-api-single-lxc-v1",
    }:
        parser.error("unregistered Jev API configuration")
    service = "changgeun-dev-" + args.component + ".service"
    unit = Path("/etc/systemd/system") / service
    transaction = SECRETS / ("switch-" + args.component + ".json")
    runtime = BASE / "candidates" / candidate
    run_dir = BASE / "runs" / run_id / profile
    prepared = run_dir / (args.component + "-prepared.json")
    config_path = run_dir / (args.component + "-config.yaml")
    interpreter = runtime / ("bot" if args.component == "bot" else profile) / "bin/python"
    if args.operation == "prepare":
        if not interpreter.is_file():
            parser.error("candidate wheel runtime is missing")
        manifest_path = runtime / "candidate.json"
        if not manifest_path.is_file():
            parser.error("candidate preparation did not complete")
        manifest = json.loads(manifest_path.read_text())
        if manifest["candidate"] != candidate or manifest["component"] != args.component:
            parser.error("candidate manifest mismatch")
        if (
            hashlib.sha256((runtime / "wheels" / manifest["wheel"]).read_bytes()).hexdigest()
            != manifest["wheel_sha256"]
        ):
            parser.error("candidate artifact checksum mismatch")
        run_dir.mkdir(parents=True, exist_ok=True)
        account = pwd.getpwnam("changgeun-dev")
        for directory in (run_dir.parent, run_dir):
            os.chown(directory, account.pw_uid, account.pw_gid)
            directory.chmod(0o700)
        private_write(
            transaction,
            json.dumps(
                {
                    "unit": unit.read_text() if unit.exists() else None,
                    "was_active": subprocess.run(
                        ["systemctl", "is-active", "--quiet", service]
                    ).returncode
                    == 0,
                }
            ),
        )
        if args.component == "gateway":
            profile_file = SECRETS / (config_id + ".yaml")
            # Product validation runs under the selected, nonroot LXC interpreter.
            source = (
                "import json,sys; from pathlib import Path; "
                "from changgeun_inference.config import read_profile; "
                "c,h=read_profile(Path(sys.argv[1])); "
                "print(json.dumps({'provider':c['provider'],'profile_id':c['profile_id'],"
                "'config_hash':h,'decision':c['decision']}))"
            )
            metadata = json.loads(
                run(
                    [
                        "runuser",
                        "-u",
                        "changgeun-dev",
                        "--",
                        str(interpreter),
                        "-c",
                        source,
                        str(profile_file),
                    ],
                    capture=True,
                )
            )
            if metadata["provider"] != profile:
                parser.error("profile file does not match explicit selection")
            if (
                config_path.exists()
                and hashlib.sha256(config_path.read_bytes()).digest()
                != hashlib.sha256(profile_file.read_bytes()).digest()
            ):
                parser.error("existing run profile is immutable; choose a reviewed new run")
            private_write(config_path, profile_file.read_text())
            private_write(prepared, json.dumps(metadata))
            command = [
                str(interpreter),
                "-m",
                "changgeun_inference.server",
                "--profile",
                str(config_path),
                "--ledger",
                str(run_dir / "ledger.db"),
                "--run-id",
                run_id,
                "--tombstones",
                "/var/lib/changgeun-dev/request-tombstones.db",
                "--token-file",
                str(SECRETS / "internal-token"),
                "--host",
                "0.0.0.0",
                "--port",
                "8443",
                "--tls-cert",
                str(SECRETS / "tls/server.crt"),
                "--tls-key",
                str(SECRETS / "tls/server.key"),
            ]
            environment = "EnvironmentFile=" + str(SECRETS / "hosted.env") + "\n"
            dependencies = (
                "Requires=changgeun-dev-firewall.service\nAfter=changgeun-dev-firewall.service\n"
            )
            memory = "1G"
        else:
            # Endpoint/CA/IDs stay in restricted files; never print or shell-source them.
            config = json.loads((SECRETS / "bot-jev-api-config.yaml").read_text())
            if plan.get("youtube_audio", False):
                if not manifest.get("youtube_audio_dependencies", False):
                    parser.error("candidate media dependencies are missing")
                for name in ("node", "ffmpeg"):
                    binary = (
                        Path(manifest.get("node_path", "/usr/bin/node"))
                        if name == "node"
                        else Path("/usr/bin/ffmpeg")
                    )
                    if (
                        hashlib.sha256(binary.read_bytes()).hexdigest()
                        != (manifest[name + "_sha256"])
                    ):
                        parser.error("candidate media runtime changed")
                config["media"]["youtube_audio_enabled"] = True
                config["media"]["youtube_js_runtime"] = manifest.get("node_path", "/usr/bin/node")
            if "static_text_channels" in plan:
                static_channels = plan["static_text_channels"]
                if (
                    not isinstance(static_channels, list)
                    or not static_channels
                    or any(
                        not isinstance(value, str) or not value.isdecimal()
                        for value in static_channels
                    )
                ):
                    parser.error("invalid existing static text policy")
                config["commands"]["allowed_text_channel_ids"] = static_channels
            if plan.get("prefix_channels", False):
                channels = json.loads((SECRETS / "prefix-channels.json").read_text())
                if (
                    not isinstance(channels, list)
                    or not channels
                    or any(
                        not isinstance(channel, str) or not channel.isdecimal()
                        for channel in channels
                    )
                ):
                    parser.error("invalid restricted prefix channel selection")
                config["commands"]["prefix"] = {
                    "enabled": True,
                    "value": "!!창근아",
                    "allowed_text_channel_ids": channels,
                }
            command = [
                str(interpreter),
                "-m",
                "changgeun",
                "--config",
                str(config_path),
                "--token-env",
                str(SECRETS / "bot.env"),
            ]
            config["storage"]["database_path"] = str(run_dir / "bot.db")
            binding = plan["binding"]
            if binding["provider"] != profile:
                parser.error("gateway selection mismatch")
            config["active_inference"].update(binding)
            if config_path.exists() and json.loads(config_path.read_text()) != config:
                parser.error("existing bot run configuration is immutable; select a new run")
            private_write(config_path, json.dumps(config))
            environment, dependencies, memory = "", "", "900M"
        escaped = [value.replace("%", "%%").replace('"', '\\"') for value in command]
        execution = " ".join('"' + value + '"' for value in escaped)
        content = (
            "[Unit]\nDescription=ChangGeun isolated development "
            + args.component
            + "\n"
            + dependencies
            + "[Service]\nType=simple\nUser=changgeun-dev\nGroup=changgeun-dev\n"
            + environment
            + "WorkingDirectory="
            + str(run_dir)
            + "\nExecStart="
            + execution
            + "\n"
            "Restart=on-failure\nRestartSec=5\nKillSignal=SIGINT\nTimeoutStopSec=40\n"
            "UMask=0077\nNoNewPrivileges=true\nPrivateTmp=true\nProtectSystem=strict\nProtectHome=true\n"
            "ReadWritePaths=/opt/changgeun-dev/runs /var/lib/changgeun-dev\nMemoryMax="
            + memory
            + "\nTasksMax=128\n"
        )
        private_write(run_dir / (args.component + ".service"), content)
        print(args.component + " prepared; existing run state preserved", flush=True)
    elif args.operation == "stop":
        run(["systemctl", "stop", service])
        if subprocess.run(["systemctl", "is-active", "--quiet", service]).returncode == 0:
            raise SystemExit("service did not drain and stop")
        if args.component == "gateway":
            # Preserve ownership of all prior requests, including pre-controller probes.
            registry_path = Path("/var/lib/changgeun-dev/request-tombstones.db")
            with sqlite3.connect(registry_path) as registry:
                registry.execute(
                    "CREATE TABLE IF NOT EXISTS request_owners("
                    "id TEXT PRIMARY KEY,binding TEXT NOT NULL,run_id TEXT NOT NULL)"
                )
                for ledger in (BASE / "runs").rglob("ledger.db"):
                    with sqlite3.connect(f"file:{ledger}?mode=ro", uri=True) as previous:
                        for request_id, binding in previous.execute(
                            "SELECT id,binding FROM requests"
                        ):
                            registry.execute(
                                "INSERT OR IGNORE INTO request_owners VALUES(?,?,?)",
                                (request_id, binding, "historical"),
                            )
            account = pwd.getpwnam("changgeun-dev")
            os.chown(registry_path, account.pw_uid, account.pw_gid)
            registry_path.chmod(0o600)
        print(args.component + " stopped; pending work drained", flush=True)
    elif args.operation == "ready":
        code = (
            "import asyncio,sys; from pathlib import Path; "
            "from changgeun.config import BotConfig; "
            "from changgeun.nlp.client import GatewayClient; "
            "c=BotConfig.read(Path(sys.argv[1])); asyncio.run(GatewayClient(c.inference).ready())"
        )
        for _attempt in range(30):
            checked = subprocess.run(
                [
                    "runuser",
                    "-u",
                    "changgeun-dev",
                    "--",
                    str(interpreter),
                    "-c",
                    code,
                    str(config_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if checked.returncode == 0:
                print(
                    "TLS health and frozen profile binding verified; no model dispatch", flush=True
                )
                break
            time.sleep(1)
        else:
            raise SystemExit("gateway readiness failed")
    elif args.operation == "install":
        if args.component == "bot":
            database = run_dir / "bot.db"
            if not database.exists():
                fixture = BASE / "runs/structured-baseline/bot.db"
                previous = json.loads(transaction.read_text())
                if previous["unit"]:
                    import shlex

                    prior_command = shlex.split(
                        next(
                            line[10:]
                            for line in previous["unit"].splitlines()
                            if line.startswith("ExecStart=")
                        )
                    )
                    prior_config = Path(prior_command[prior_command.index("--config") + 1])
                    fixture = Path(json.loads(prior_config.read_text())["storage"]["database_path"])
                    if not fixture.resolve().is_relative_to(BASE / "runs"):
                        parser.error("previous bot database is outside development runs")
                with (
                    sqlite3.connect(f"file:{fixture}?mode=ro", uri=True) as source,
                    sqlite3.connect(database) as destination,
                ):
                    source.backup(destination)
                account = pwd.getpwnam("changgeun-dev")
                os.chown(database, account.pw_uid, account.pw_gid)
                database.chmod(0o600)
        private_write(unit, (run_dir / (args.component + ".service")).read_text(), root_owner=True)
        run(["systemctl", "daemon-reload"])
        run(["systemctl", "start", service])
        run(["systemctl", "is-active", "--quiet", service])
        print(args.component + " active; isolated run data retained", flush=True)
    else:
        previous = json.loads(transaction.read_text())
        run(["systemctl", "stop", service])
        if previous["unit"] is not None:
            private_write(unit, previous["unit"], root_owner=True)
        elif unit.exists():
            unit.unlink()
        run(["systemctl", "daemon-reload"])
        if previous["was_active"]:
            run(["systemctl", "start", service])
        print(args.component + " restored to previous service; new run data retained", flush=True)


if __name__ == "__main__":
    main()
