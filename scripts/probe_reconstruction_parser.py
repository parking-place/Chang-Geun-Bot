#!/usr/bin/env python3
"""Exercise three fixed, read-only v2 interpretations on a disposable LXC DB.

This makes real Jev calls but never starts Discord or invokes a command handler.
Run only as the development bot account on DiscordBotLXC after checking budget.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path

from changgeun.config import BotConfig
from changgeun.discord_adapter.client import ChangGeunClient
from changgeun.domain.models import Actor
from changgeun.parser.gateway import ParserSession
from changgeun.parser.jev import JevInterpreter
from changgeun.parser.normalizer import InputNormalizer
from changgeun.parser.orchestrator import ParserOrchestrator
from changgeun.parser.validation import DraftValidator

CASES = (
    ("저장된 재생목록을 보여줘", "C01"),
    ("지금 대기열에 뭐가 있어?", "C16"),
    ("사용법을 알려줘", "C38"),
)


async def probe(config: BotConfig, database: Path) -> dict[str, object]:
    client = ChangGeunClient(replace(
        config, database_path=database, natural_parser_version="v1",
        parser_trace_path=None,
    ))
    try:
        if client.gateway is None:
            raise RuntimeError("gateway unavailable")
        await client.gateway.parser_ready("disabled")
        before = await client.gateway.usage()
        if before["limit"] - before["reserved_calls"] < len(CASES) * 3:
            raise RuntimeError("insufficient Jev test budget")
        actor = Actor(next(iter(config.policy.guild_ids)), "synthetic-parser-probe",
                      frozenset(), next(iter(config.policy.text_channel_ids)))
        scope_hash = hashlib.sha256(
            f"{actor.guild_id}:{actor.text_channel_id}:{actor.user_id}".encode()
        ).hexdigest()
        results: list[dict[str, object]] = []
        for text, expected in CASES:
            root_id = "synthetic-" + uuid.uuid4().hex
            view = InputNormalizer().normalize(text, request_id=root_id)
            session = ParserSession(client.gateway, request_id=root_id,
                                    scope_hash=scope_hash, original_text=text)
            interpreter = JevInterpreter(client.command_service, session, client.db,
                                         config.policy)
            orchestrator = ParserOrchestrator(
                interpreter, session, client.command_service, client.db, config.policy,
                llm_enabled=False,
            )
            outcome = await orchestrator.parse(
                view, actor, root_id=root_id, scope_hash=scope_hash,
                expires_at=session.root["expires_at"],
            )
            command = outcome.draft.command_id if outcome.draft else None
            validated = False
            if outcome.status == "parsed" and outcome.draft is not None:
                validator = DraftValidator(client.command_service, client.db,
                                           config.policy, orchestrator.snapshots)
                validator.validate(outcome.draft, view, actor, root_id=root_id,
                                   pass_id="initial", scope_hash=scope_hash,
                                   watch_allowed=True)
                validated = True
            results.append({"expected": expected, "status": outcome.status,
                            "command": command, "code": outcome.code,
                            "validated": validated})
        after = await client.gateway.usage()
        return {"cases": results, "jev_reserved_before": before["reserved_calls"],
                "jev_reserved_after": after["reserved_calls"],
                "jev_limit": after["limit"], "discord_execution": False,
                "pass": all(row["status"] == "parsed" and
                            row["command"] == row["expected"] and row["validated"]
                            for row in results)}
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = BotConfig.read(args.config)
    if config.natural_parser_version != "v2" or config.parser_llm_fallback != "disabled":
        parser.error("active parser v2 with LLM disabled required")
    with tempfile.TemporaryDirectory(prefix="parser-v2-probe-") as temporary:
        database = Path(temporary) / "bot.db"
        with (sqlite3.connect(config.database_path) as source,
              sqlite3.connect(database) as target):
            source.backup(target)
        result = asyncio.run(probe(config, database))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
