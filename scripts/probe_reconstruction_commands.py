#!/usr/bin/env python3
"""Run synthetic stage-1 Jev selection for every executable slash command.

Only the first model call is made. No command handler, Discord connection, or
production DB mutation is possible. Run as changgeun-dev on DiscordBotLXC.
This development set is not the independent 1.2.0 quality gate.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import sqlite3
import tempfile
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from changgeun.config import BotConfig
from changgeun.discord_adapter.client import ChangGeunClient
from changgeun.domain.models import Actor
from changgeun.nlp.command_registry import COMMANDS
from changgeun.parser.contracts import ParserOutcome
from changgeun.parser.gateway import ParserSession
from changgeun.parser.jev import JevInterpreter
from changgeun.parser.normalizer import InputNormalizer


class StageOneOnly(JevInterpreter):
    async def _arguments(self, *args: Any, **kwargs: Any) -> ParserOutcome:
        return ParserOutcome("clarify", code="stage1_only")


class ScoredSession(ParserSession):
    async def call(self, operation: str, state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        result = await super().call(operation, state, **kwargs)
        if operation == "command_select":
            self.scores = {}
            for name, answer in result.get("answers", {}).items():
                probabilities = answer.get("probabilities", {})
                values = sorted((value for value in probabilities.values()
                                 if type(value) in {int, float}), reverse=True)
                self.scores[name] = {
                    "choice": answer.get("choice"),
                    "confidence": answer.get("confidence"),
                    "top_probability": values[0] if values else None,
                    "margin": values[0] - values[1] if len(values) > 1 else None,
                }
        return result


def load_cases(path: Path) -> tuple[list[dict[str, str]], str]:
    data = path.read_bytes()
    parsed = json.loads(data)
    cases = parsed.get("cases")
    expected = {item.identifier for item in COMMANDS if item.identifier != "C39"}
    if (parsed.get("schema_version") != "development-v2-command-selection-v1"
            or not isinstance(cases, list) or len(cases) != len(expected)
            or any(not isinstance(row, dict)
                   or set(row) != {"command", "text"}
                   or not isinstance(row["command"], str)
                   or not isinstance(row["text"], str)
                   or not 1 <= len(row["text"]) <= 500 for row in cases)
            or {row["command"] for row in cases} != expected):
        raise ValueError("exact executable command development inventory required")
    return cases, hashlib.sha256(data).hexdigest()


async def evaluate(config: BotConfig, database: Path,
                   cases: list[dict[str, str]]) -> dict[str, Any]:
    client = ChangGeunClient(replace(
        config, database_path=database, natural_parser_version="v1",
        parser_trace_path=None,
    ))
    try:
        if client.gateway is None:
            raise RuntimeError("gateway unavailable")
        await client.gateway.parser_ready("disabled")
        before = await client.gateway.usage()
        if before["limit"] - before["reserved_calls"] < len(cases) + 20:
            raise RuntimeError("insufficient Jev development budget")
        actor = Actor(next(iter(config.policy.guild_ids)), "synthetic-command-probe",
                      config.policy.dj_role_ids,
                      next(iter(config.policy.text_channel_ids)), manage_guild=True)
        scope_hash = hashlib.sha256(
            f"{actor.guild_id}:{actor.text_channel_id}:{actor.user_id}".encode()
        ).hexdigest()
        rows = []
        for case in cases:
            root_id = "synthetic-" + uuid.uuid4().hex
            text = case["text"]
            view = InputNormalizer().normalize(text, request_id=root_id)
            session = ScoredSession(client.gateway, request_id=root_id,
                                    scope_hash=scope_hash, original_text=text)
            interpreter = StageOneOnly(client.command_service, session, client.db,
                                       config.policy)
            started = time.monotonic()
            outcome = await interpreter.interpret(
                view, actor, root_id=root_id, pass_id="initial", scope_hash=scope_hash,
            )
            elapsed_ms = round((time.monotonic() - started) * 1000)
            selected = outcome.options.get("selected_command")
            rows.append({"expected": case["command"], "selected": selected,
                         "status": outcome.status, "code": outcome.code,
                         "correct": selected == case["command"] and
                         outcome.code == "stage1_only", "elapsed_ms": elapsed_ms,
                         "scores": getattr(session, "scores", None)})
        after = await client.gateway.usage()
        return {"cases": rows, "expected_cases": len(cases),
                "correct_cases": sum(row["correct"] for row in rows),
                "jev_reserved_before": before["reserved_calls"],
                "jev_reserved_after": after["reserved_calls"],
                "jev_limit": after["limit"], "discord_execution": False,
                "scope": "stage1_only_development"}
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", nargs="+")
    args = parser.parse_args()
    config = BotConfig.read(args.config)
    if config.natural_parser_version != "v2" or config.parser_llm_fallback != "disabled":
        parser.error("active parser v2 with LLM disabled required")
    cases, dataset_hash = load_cases(args.dataset)
    if args.only:
        selected = set(args.only)
        if selected - {case["command"] for case in cases} or len(selected) != len(args.only):
            parser.error("--only must contain distinct executable command IDs")
        cases = [case for case in cases if case["command"] in selected]
    if (not args.output.is_absolute() or args.output.is_symlink()
            or not args.output.parent.is_dir()
            or args.output.parent.stat().st_mode & 0o077):
        parser.error("new output in a private run directory required")
    with tempfile.TemporaryDirectory(prefix="command-selection-probe-") as temporary:
        database = Path(temporary) / "bot.db"
        with (sqlite3.connect(config.database_path) as source,
              sqlite3.connect(database) as target):
            source.backup(target)
        result = asyncio.run(evaluate(config, database, cases))
    result["dataset_sha256"] = dataset_hash
    duration = sorted(row["elapsed_ms"] for row in result["cases"])
    result["p50_ms"] = duration[len(duration) // 2]
    result["p95_ms"] = duration[math.ceil(len(duration) * .95) - 1]
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
    errors = [row for row in result["cases"] if not row["correct"]]
    print(json.dumps({key: result[key] for key in (
        "scope", "dataset_sha256", "expected_cases", "correct_cases",
        "jev_reserved_before", "jev_reserved_after", "jev_limit", "p50_ms", "p95_ms",
        "discord_execution",
    )} | {"first_failures": errors[:15]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
