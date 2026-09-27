"""Consistent restricted SQLite snapshots and isolated restore drills on prepared LXC."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

BINDING_FIELDS = {"provider", "profile_id", "config_hash"}


def binding(value: dict[str, Any]) -> dict[str, str]:
    if set(value) != BINDING_FIELDS or value["provider"] != "jev-api":
        raise ValueError("invalid backup binding")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value["profile_id"]) or not re.fullmatch(
        r"[a-f0-9]{64}", value["config_hash"]
    ):
        raise ValueError("invalid backup binding")
    return value


def copy_database(source: Path, destination: Path) -> None:
    if not source.is_file() or source.is_symlink() or destination.exists():
        raise ValueError("invalid snapshot paths")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    original = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    target = sqlite3.connect(destination)
    try:
        original.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("snapshot integrity failed")
        if target.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("snapshot foreign keys failed")
    finally:
        original.close()
        target.close()


def snapshot(
    destination: Path, component: str, databases: dict[str, Path], active: dict[str, Any]
) -> dict[str, Any]:
    expected = {"bot.db"} if component == "bot" else {"ledger.db", "tombstones.db"}
    if component not in {"bot", "gateway"} or set(databases) != expected or destination.exists():
        raise ValueError("invalid snapshot scope")
    active = binding(active)
    destination.mkdir(parents=True, mode=0o700)
    checksums = {}
    # Owners are committed before ledger reservations; snapshot ledger before owner registry.
    for name in sorted(databases):
        copy_database(databases[name], destination / name)
        checksums[name] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
    manifest = {
        "format": 1,
        "component": component,
        "api_schema_version": "1.2",
        "binding": active,
        "created_at": time.time(),
        "files": checksums,
    }
    path = destination / "manifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
    path.chmod(0o600)
    return manifest


def restore(source: Path, destination: Path, expected_binding: dict[str, Any]) -> dict[str, Any]:
    if destination.exists() or source.is_symlink():
        raise ValueError("restore requires a new isolated destination")
    manifest = json.loads((source / "manifest.json").read_text())
    if set(manifest) != {
        "format",
        "component",
        "api_schema_version",
        "binding",
        "created_at",
        "files",
    }:
        raise ValueError("invalid snapshot manifest")
    if (
        manifest["format"] != 1
        or manifest["api_schema_version"] != "1.2"
        or binding(manifest["binding"]) != binding(expected_binding)
    ):
        raise ValueError("snapshot binding mismatch")
    expected = {"bot.db"} if manifest["component"] == "bot" else {"ledger.db", "tombstones.db"}
    if manifest["component"] not in {"bot", "gateway"} or set(manifest["files"]) != expected:
        raise ValueError("invalid snapshot files")
    for name, checksum in manifest["files"].items():
        path = source / name
        if (
            path.is_symlink()
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != checksum
        ):
            raise ValueError("snapshot checksum mismatch")
    destination.mkdir(parents=True, mode=0o700)
    for name in sorted(expected):
        copy_database(source / name, destination / name)
    if manifest["component"] == "bot":
        with sqlite3.connect(destination / "bot.db") as conn:
            conn.execute("UPDATE confirmations SET consumed=1")
            # Preserve pending/current data for explicit resume; never autojoin or replay.
            conn.execute(
                "UPDATE sessions SET desired_state='disconnected',generation=generation+1,"
                "version=version+1,voice_channel_id=NULL,start_after_connect=0"
            )
            conn.execute(
                "UPDATE external_effects SET status='failed_or_unknown' WHERE status='claimed'"
            )
    else:
        with sqlite3.connect(destination / "ledger.db") as conn:
            conn.execute("UPDATE stages SET status='failed',response=NULL")
            # All restored requests are terminal, including old completed stages.
            conn.execute("UPDATE requests SET deadline=MIN(deadline,?)", (time.time(),))
            requests = conn.execute("SELECT id,binding FROM requests").fetchall()
        with sqlite3.connect(destination / "tombstones.db") as conn:
            for identifier, request_binding in requests:
                row = conn.execute(
                    "SELECT binding FROM request_owners WHERE id=?", (identifier,)
                ).fetchone()
                if row is None or row[0] != request_binding:
                    raise ValueError("restored request ownership mismatch")
    return {
        "component": manifest["component"],
        "binding": manifest["binding"],
        "integrity": "PASS",
        "isolated": True,
        "automatic_playback": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("snapshot", "restore"))
    parser.add_argument("--component", choices=("bot", "gateway"), required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--tombstones", type=Path)
    args = parser.parse_args()
    base = Path("/opt/changgeun-dev")
    if not Path(__file__).resolve().is_relative_to(base):
        parser.error("execute only on a prepared designated LXC")
    os.umask(0o077)
    config = json.loads(args.config.read_text())
    active = config["active_inference"] if args.component == "bot" else config
    active = {key: active[key] for key in BINDING_FIELDS}
    if args.operation == "snapshot":
        databases = (
            {"bot.db": args.source}
            if args.component == "bot"
            else {"ledger.db": args.source, "tombstones.db": args.tombstones}
        )
        if any(value is None for value in databases.values()):
            parser.error("gateway snapshot requires tombstones")
        result = snapshot(args.destination, args.component, databases, active)
        result = {
            "component": result["component"],
            "binding": result["binding"],
            "snapshot": "PASS",
            "file_count": len(result["files"]),
        }
    else:
        result = restore(args.source, args.destination, active)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
