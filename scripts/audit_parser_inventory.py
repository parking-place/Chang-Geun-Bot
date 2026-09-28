#!/usr/bin/env python3
"""Emit the live slash-derived parser inventory from a disposable LXC client.

Run on DiscordBotLXC only. This reads no service config, credential, or user DB.
The output is command metadata, not proof that natural-language execution works.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from changgeun.config import BotConfig
from changgeun.discord_adapter.client import ChangGeunClient
from changgeun.domain.models import Policy


def safe_default(value: Any) -> Any:
    if value is None or type(value) in {str, int, bool, float}:
        return value
    return {"unserializable_type": type(value).__name__}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="parser-inventory-") as directory:
        root = Path(directory)
        policy = Policy(frozenset({"synthetic"}), frozenset({"dj"}),
                        frozenset(), frozenset())
        client = ChangGeunClient(BotConfig(root / "db.sqlite", policy,
                                          root / "audio", {}))
        commands = []
        for identifier, spec in sorted(client.command_service.specs.items()):
            commands.append({
                "id": identifier, "slash_name": spec.name,
                "permission": spec.permission, "risk": spec.risk,
                "private": spec.private,
                "arguments": [{
                    "name": argument.name, "kind": argument.kind,
                    "required": argument.required,
                    "default": safe_default(argument.default),
                    "source": argument.source, "collection": argument.collection,
                    "depends_on": argument.depends_on,
                    "minimum": argument.minimum, "maximum": argument.maximum,
                    "max_length": argument.max_length,
                    "choices": list(argument.choices),
                } for argument in spec.arguments],
            })
        if len(commands) != 47 or {entry["id"] for entry in commands} != {
            f"C{index:02}" for index in range(1, 48)
        }:
            raise SystemExit("public command inventory changed")
        print(json.dumps({"schema_version": "parser-inventory-v1",
                          "command_count": len(commands),
                          "argument_count": sum(len(entry["arguments"]) for entry in commands),
                          "commands": commands}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
