"""Authenticated encrypted off-node development backups; root-only prepared LXC tool."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile
from pathlib import Path

KEYDIR = Path("/var/lib/changgeun-dev/secrets/backup-recovery")
MAX_BYTES = 128 * 1024 * 1024


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("keygen", "encrypt", "decrypt"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0 or not Path(__file__).resolve().is_relative_to(Path("/opt/changgeun-dev")):
        parser.error("root deployment account on a prepared LXC required")
    os.umask(0o077)
    key, certificate = KEYDIR / "recovery.key", KEYDIR / "recipient.crt"
    if args.operation == "keygen":
        if KEYDIR.exists():
            parser.error("recovery keys are retained; never overwrite")
        KEYDIR.mkdir(mode=0o700)
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:3072",
                "-nodes",
                "-keyout",
                str(key),
                "-out",
                str(certificate),
                "-days",
                "365",
                "-subj",
                "/CN=changgeun-dev-backup-recovery",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        key.chmod(0o600)
        certificate.chmod(0o600)
        print(json.dumps({"key_ready": True, "private_key_owner": "root", "algorithm": "RSA3072"}))
        return
    if args.source is None or args.destination is None or args.destination.exists():
        parser.error("explicit source and new destination required")
    source, destination = args.source, args.destination
    if source.is_symlink():
        parser.error("symlink sources are rejected")
    if args.operation == "encrypt":
        manifest = json.loads((source / "manifest.json").read_text())
        expected = {"manifest.json", *manifest["files"]}
        if expected not in (
            {"manifest.json", "bot.db"},
            {"manifest.json", "ledger.db", "tombstones.db"},
        ):
            parser.error("only completed database snapshots can be encrypted")
        if sum((source / name).stat().st_size for name in expected) > MAX_BYTES:
            parser.error("development snapshot exceeds encryption size limit")
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as archive:
            for name in sorted(expected):
                path = source / name
                if not path.is_file() or path.is_symlink():
                    parser.error("invalid snapshot member")
                archive.add(path, arcname=name, recursive=False)
        result = subprocess.run(
            [
                "openssl",
                "cms",
                "-encrypt",
                "-aes-256-gcm",
                "-binary",
                "-outform",
                "DER",
                "-recip",
                str(certificate),
            ],
            input=data.getvalue(),
            check=True,
            capture_output=True,
        )
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with destination.open("xb") as stream:
            stream.write(result.stdout)
        destination.chmod(0o600)
        print(
            json.dumps(
                {
                    "encrypted": True,
                    "cipher": "AES256-GCM",
                    "authenticated": True,
                    "sha256": hashlib.sha256(result.stdout).hexdigest(),
                    "bytes": len(result.stdout),
                }
            )
        )
    else:
        if not source.is_file() or source.stat().st_size > MAX_BYTES:
            parser.error("invalid encrypted backup size")
        result = subprocess.run(
            [
                "openssl",
                "cms",
                "-decrypt",
                "-binary",
                "-inform",
                "DER",
                "-recip",
                str(certificate),
                "-inkey",
                str(key),
            ],
            input=source.read_bytes(),
            capture_output=True,
        )
        if result.returncode:
            parser.error("authenticated decryption failed; no restore directory created")
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:gz") as archive:
            members = archive.getmembers()
            if (
                {member.name for member in members}
                not in (
                    {"manifest.json", "bot.db"},
                    {"manifest.json", "ledger.db", "tombstones.db"},
                )
                or len(members) not in {2, 3}
                or any(not member.isfile() for member in members)
                or sum(member.size for member in members) > MAX_BYTES
            ):
                parser.error("invalid decrypted snapshot members")
            destination.mkdir(parents=True, mode=0o700)
            for member in members:
                with (destination / member.name).open("xb") as stream:
                    stream.write(archive.extractfile(member).read())
                (destination / member.name).chmod(0o600)
        print(
            json.dumps(
                {
                    "decrypted": True,
                    "authentication_verified": True,
                    "isolated_snapshot": True,
                    "files": len(members),
                }
            )
        )


if __name__ == "__main__":
    main()
