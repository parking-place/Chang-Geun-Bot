#!/usr/bin/env python3
"""Send public source and run tools only on an explicitly named LXC.

This orchestrator does not import, install or execute product code locally.
SSH connection details belong in a private SSH config, never in this file.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shlex
import subprocess
import tarfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-config", type=Path, required=True)
    parser.add_argument("--host", choices=("DiscordBotLXC",), required=True)
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    ssh = ["ssh", "-F", str(args.ssh_config.resolve()), args.host]
    if args.sync:
        files = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
        ).split(b"\0")
        buffer = io.BytesIO()
        manifest: dict[str, str] = {}
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for raw in sorted(set(files)):
                if not raw:
                    continue
                name = raw.decode()
                path = root / name
                if not name.startswith(
                    ("bot/", "inference/", "tests/", "shared/", "scripts/")
                ) and name not in {"pyproject.toml", "AGENTS.md"}:
                    continue
                if path.is_symlink() or not path.is_file() or ".private" in path.parts:
                    raise SystemExit("unsafe source member")
                archive.add(path, arcname=name, recursive=False)
                manifest[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            payload = json.dumps(manifest, sort_keys=True).encode()
            info = tarfile.TarInfo("SOURCE_MANIFEST.json")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        subprocess.run(
            ssh + ["runuser -u changgeun-dev -- tar -xzf - -C /opt/changgeun-dev/source"],
            input=buffer.getvalue(),
            check=True,
        )
        print("Public source synced; manifest_sha256=" + hashlib.sha256(payload).hexdigest())
    if args.command:
        command = args.command[1:] if args.command[0] == "--" else args.command
        remote = "cd /opt/changgeun-dev/source && runuser -u changgeun-dev -- " + shlex.join(
            command
        )
        subprocess.run(ssh + [remote], check=True)


if __name__ == "__main__":
    main()
