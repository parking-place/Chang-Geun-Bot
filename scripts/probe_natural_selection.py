#!/usr/bin/env python3
"""Bounded development-only Jev command selection probe on DiscordBotLXC.

This does not change Discord or database state and is not held-out evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path

from changgeun.config import BotConfig
from changgeun.nlp.client import GatewayClient
from changgeun.nlp.command_registry import CommandSelector

CASES = (
    ("운동용 목록 삭제해줘", "C04", False),
    ("youtube.com/watch?v=GD_rjpO7CIQ 틀어줘", "C23", False),
    ("지금 뭐 틀고 있어?", "C31", False),
    ("주시를 다시 켜줘", "C43", True),
    ("운동용을 없애줘", "C04", False),
)


class AuditPort:
    def __init__(self, gateway: GatewayClient) -> None:
        self.gateway = gateway
        self.provider, self.profile_id, self.config_hash = (
            gateway.provider, gateway.profile_id, gateway.config_hash
        )
        self.results: list[dict[str, object]] = []

    async def choose(self, payload: dict[str, object], timeout: float):
        result = await self.gateway.choose(payload, timeout)
        scores = sorted(result.probabilities.values(), reverse=True)
        self.results.append({
            "stage": payload["stage_index"],
            "selected": result.selected_id,
            "top": round(scores[0], 3),
            "margin": round(scores[0] - scores[1], 3),
        })
        return result


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--case", type=int, choices=range(len(CASES)))
    args = parser.parse_args()
    config = BotConfig.read(args.config)
    if config.inference is None or config.inference["provider"] != "jev-api":
        raise SystemExit("Jev API profile is not active")
    port = GatewayClient(config.inference)
    try:
        cases = CASES if args.case is None else (CASES[args.case],)
        usage = await port.usage()
        maximum = len(cases) * 2
        if usage["limit"] - usage["reserved_calls"] < maximum:
            raise SystemExit("Not enough reserved-call budget for bounded probe")
        decision = config.inference["decision"]
        audited = AuditPort(port)
        selector = CommandSelector(
            audited,
            confidence=decision["confidence_threshold"],
            margin=decision["margin_threshold"],
            prompt_version=(
                "korean-candidates-compact-v1" if args.compact else decision["prompt_version"]
            ),
        )
        await port.ready()

        async def recheck() -> None:
            return None

        results = []
        for text, expected, admin_only in cases:
            start = len(audited.results)
            selected = await selector.select(
                text, str(uuid.uuid4()), started_at=time.monotonic(),
                recheck=recheck, admin_only=admin_only, allow_admin=admin_only,
            )
            results.append({
                "expected": expected,
                "selected": selected.command.identifier if selected else None,
                "calls": selected.trace.provider_calls if selected else None,
                "stages": audited.results[start:],
            })
        after = await port.usage()
        print(json.dumps({
            "scope": "development_only",
            "prompt": "compact" if args.compact else "active",
            "before": usage["reserved_calls"],
            "after": after["reserved_calls"],
            "limit": after["limit"],
            "cases": results,
        }, ensure_ascii=False))
    finally:
        await port.close()


if __name__ == "__main__":
    asyncio.run(main())
