"""Build/install a fixed development wheel candidate on a prepared LXC only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pwd
import re
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--component", choices=("bot", "gateway"), required=True)
    parser.add_argument("--youtube-audio", action="store_true")
    parser.add_argument("--youtube-runtime", type=Path, default=Path("/usr/bin/node"))
    args = parser.parse_args()
    if os.geteuid() != 0 or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", args.candidate):
        parser.error("run on the prepared LXC as its deployment account")
    os.umask(0o077)
    base = Path("/opt/changgeun-dev")
    destination = base / "candidates" / args.candidate
    if destination.exists():
        parser.error("candidate directory already exists; fixed candidates are not overwritten")
    manifest_bytes = (base / "source/SOURCE_MANIFEST.json").read_bytes()
    public_source = json.loads(manifest_bytes)

    def verify_source() -> None:
        for name, expected in public_source.items():
            source = base / "source" / name
            if (
                source.is_symlink()
                or not source.resolve().is_relative_to(base / "source")
                or hashlib.sha256(source.read_bytes()).hexdigest() != expected
            ):
                raise SystemExit("source manifest drift; sync and use a new candidate")
        if (base / "source/SOURCE_MANIFEST.json").read_bytes() != manifest_bytes:
            raise SystemExit("source manifest changed during preparation")

    verify_source()
    account = pwd.getpwnam("changgeun-dev")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.chown(destination.parent, account.pw_uid, account.pw_gid)
    destination.mkdir(parents=True)
    os.chown(destination, account.pw_uid, account.pw_gid)
    log = destination / "preparation.log"
    with log.open("wb") as stream:

        def execute(command: list[str]) -> None:
            subprocess.run(
                ["runuser", "-u", "changgeun-dev", "--", *command],
                check=True,
                stdout=stream,
                stderr=subprocess.STDOUT,
            )

        package = "bot" if args.component == "bot" else "inference"
        execute(
            [
                str(base / "venv/bin/python"),
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(destination / "wheels"),
                str(base / "source" / package),
            ]
        )
        wheel = next((destination / "wheels").glob("changgeun*.whl"))
        frozen = subprocess.check_output(
            [str(base / "venv/bin/python"), "-m", "pip", "freeze"], text=True
        )
        constraints = destination / "constraints.txt"
        constraints.write_text(
            "\n".join(
                line
                for line in frozen.splitlines()
                if "==" in line and not line.startswith(("changgeun-", "openjev"))
            )
            + "\n"
        )
        os.chown(constraints, account.pw_uid, account.pw_gid)
        names = ["bot"] if args.component == "bot" else ["jev-api"]
        for name in names:
            target = destination / name
            execute(["python3", "-m", "venv", str(target)])
            execute(
                [
                    str(target / "bin/python"),
                    "-m",
                    "pip",
                    "install",
                    "--constraint",
                    str(constraints),
                    str(wheel) + ("[youtube]" if args.youtube_audio and name == "bot" else ""),
                ]
            )
            execute([str(target / "bin/python"), "-m", "pip", "check"])
            execute(
                [
                    str(target / "bin/python"),
                    "-c",
                    "import importlib.util,sys; "
                    + ("import changgeun; " if name == "bot" else "import changgeun_inference; ")
                    + (
                        "assert all(importlib.util.find_spec(m) is None "
                        "for m in ('torch','transformers','openjev')); "
                        if name == "jev-api"
                        else ""
                    )
                    + "assert sys.prefix.startswith('/opt/changgeun-dev/candidates/')",
                ]
            )
        verify_source()
        manifest = {
            "candidate": args.candidate,
            "component": args.component,
            "wheel": wheel.name,
            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "source_manifest_sha256": hashlib.sha256(
                (base / "source/SOURCE_MANIFEST.json").read_bytes()
            ).hexdigest(),
            "runtime_scope": "development; Jev API only, no local model dependencies",
            "youtube_audio_dependencies": args.youtube_audio and args.component == "bot",
        }
        if manifest["youtube_audio_dependencies"]:
            manifest["node_path"] = str(args.youtube_runtime)
            manifest["node_sha256"] = hashlib.sha256(args.youtube_runtime.read_bytes()).hexdigest()
            manifest["ffmpeg_sha256"] = hashlib.sha256(
                Path("/usr/bin/ffmpeg").read_bytes()
            ).hexdigest()
        (destination / "candidate.json").write_text(json.dumps(manifest, sort_keys=True))
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
