#!/usr/bin/env python3
"""Exercise bounded Jev/GPT recovery with synthetic text and no Discord execution.

Run as changgeun-dev on DiscordBotLXC while the live bot is stopped and the
gateway is explicitly in its temporary gpt-5-nano validation profile.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from changgeun.config import BotConfig
from changgeun.discord_adapter.client import ChangGeunClient
from changgeun.domain.models import Actor
from changgeun.parser.gateway import ParserSession
from changgeun.parser.jev import JevInterpreter
from changgeun.parser.llm_schema import full_parse_schema, validate_full_output
from changgeun.parser.normalizer import InputNormalizer
from changgeun.parser.orchestrator import ParserOrchestrator


async def gpt_usage(client: ChangGeunClient) -> dict[str, Any]:
    assert client.gateway is not None
    gateway = client.gateway
    http = await gateway._http()
    async with http.stream(
        "GET", gateway.base_url + "/v2/usage",
        headers={"Authorization": "Bearer " + gateway.token}, timeout=2,
    ) as response:
        response.raise_for_status()
        return await gateway._bounded_json(response)


async def evaluate(config: BotConfig, database: Path,
                   cases: list[dict[str, str]], progress: Path,
                   force_full_parse: bool = False) -> dict[str, Any]:
    client = ChangGeunClient(replace(
        config, database_path=database, natural_parser_version="v1",
        parser_trace_path=None,
    ))
    try:
        if client.gateway is None:
            raise RuntimeError("gateway unavailable")
        await client.gateway.parser_ready("gpt-5-nano")
        before_jev = await client.gateway.usage()
        before_gpt = await gpt_usage(client)
        if before_jev["limit"] - before_jev["reserved_calls"] < len(cases) * 6:
            raise RuntimeError("insufficient Jev test budget")
        if (before_gpt.get("gpt_limit_micro_usd") != 1_000_000
                or before_gpt["gpt_limit_micro_usd"]
                - before_gpt["gpt_reserved_micro_usd"] < len(cases) * 20_000):
            raise RuntimeError("insufficient GPT test budget")
        actor = Actor(next(iter(config.policy.guild_ids)), "synthetic-gpt-probe",
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
            session = ParserSession(client.gateway, request_id=root_id,
                                    scope_hash=scope_hash, original_text=text)
            interpreter = JevInterpreter(client.command_service, session, client.db,
                                         config.policy)
            orchestrator = ParserOrchestrator(
                interpreter, session, client.command_service, client.db, config.policy,
                llm_enabled=True,
            )
            started = time.monotonic()
            if force_full_parse:
                await interpreter.interpret(view, actor, root_id=root_id,
                                            pass_id="initial", scope_hash=scope_hash)
                spec = client.command_service.specs[case["command"]]
                selected = {case["command"]: spec}
                schema = full_parse_schema(selected, collections={})
                state = {"original_message": text, "normalized_message": view.normalized_text,
                         "rewritten_message": None, "scope": "reparse",
                         "allowed_commands": {case["command"]: spec.description},
                         "unavailable_commands": {}, "collections": {}}
                try:
                    output = await session.call("full_parse", state, output_schema=schema)
                    decision = validate_full_output(output, commands=selected, collections={})
                    plan = decision["plan"]
                    row = {"expected": case["command"],
                           "command": plan["command"] if isinstance(plan, dict) else None,
                           "status": decision["status"], "code": None,
                           "path": "forced_full_parse_schema"}
                except Exception as exc:
                    row = {"expected": case["command"], "command": None,
                           "status": "failed", "code": getattr(exc, "code", type(exc).__name__),
                           "path": "forced_full_parse_schema"}
            else:
                outcome = await orchestrator.parse(
                    view, actor, root_id=root_id, scope_hash=scope_hash,
                    expires_at=session.root["expires_at"],
                )
                draft = outcome.draft
                row = {"expected": case["command"],
                       "command": draft.command_id if draft else
                       outcome.options.get("selected_command"),
                       "status": outcome.status, "code": outcome.code,
                       "path": draft.parser_source if draft else None}
            row["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            rows.append(row)
            with progress.open("a") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        after_jev = await client.gateway.usage()
        after_gpt = await gpt_usage(client)
        return {"scope": "synthetic_gpt_recovery_development",
                "discord_execution": False, "cases": rows,
                "jev_reserved_before": before_jev["reserved_calls"],
                "jev_reserved_after": after_jev["reserved_calls"],
                "gpt_reserved_before": before_gpt["gpt_reserved_micro_usd"],
                "gpt_reserved_after": after_gpt["gpt_reserved_micro_usd"],
                "gpt_actual_after": after_gpt["gpt_actual_micro_usd"],
                "gpt_limit": after_gpt["gpt_limit_micro_usd"],
                "gpt_unknown_cost_calls": after_gpt["gpt_unknown_cost_calls"]}
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", nargs="+", required=True)
    parser.add_argument("--force-full-parse", action="store_true")
    args = parser.parse_args()
    config = BotConfig.read(args.config)
    if config.natural_parser_version != "v2" or config.parser_llm_fallback != "disabled":
        parser.error("frozen bot v2 disabled configuration required for isolated probe")
    if subprocess.run(["systemctl", "is-active", "--quiet", "changgeun-dev-bot.service"],
                      check=False).returncode == 0:
        parser.error("test bot must be stopped during GPT profile validation")
    data = args.dataset.read_bytes()
    fixture = json.loads(data)
    all_cases = fixture.get("cases")
    if (fixture.get("schema_version") != "development-v2-command-selection-v1"
            or not isinstance(all_cases, list)):
        parser.error("versioned development fixture required")
    identifiers = set(args.only)
    if len(identifiers) != len(args.only) or not 1 <= len(identifiers) <= 3:
        parser.error("one to three distinct case IDs required")
    cases = [row for row in all_cases if row.get("command") in identifiers]
    if len(cases) != len(identifiers):
        parser.error("unknown case ID")
    if args.force_full_parse and (len(cases) != 1 or cases[0]["command"] != "C31"):
        parser.error("forced schema probe is limited to synthetic C31")
    progress = args.output.with_suffix(args.output.suffix + ".partial.jsonl")
    if (not args.output.is_absolute() or args.output.exists() or args.output.is_symlink()
            or progress.exists() or progress.is_symlink()
            or not args.output.parent.is_dir()
            or args.output.parent.stat().st_mode & 0o077):
        parser.error("new output in a private run directory required")
    descriptor = os.open(progress, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    with tempfile.TemporaryDirectory(prefix="gpt-recovery-probe-") as temporary:
        database = Path(temporary) / "bot.db"
        with (sqlite3.connect(config.database_path) as source,
              sqlite3.connect(database) as target):
            source.backup(target)
        result = asyncio.run(evaluate(config, database, cases, progress,
                                      force_full_parse=args.force_full_parse))
    result["dataset_sha256"] = hashlib.sha256(data).hexdigest()
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
