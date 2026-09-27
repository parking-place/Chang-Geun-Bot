"""Three-stage TLS/provenance/replay probe on DiscordBotLXC; no Discord/DB mutations."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path

from changgeun.config import BotConfig
from changgeun.nlp.client import GatewayClient


async def run(path: Path) -> None:
    config = BotConfig.read(path)
    if config.inference is None:
        raise SystemExit("explicit inference binding required")
    client = GatewayClient(config.inference)
    await client.ready()
    request_id, expires = str(uuid.uuid4()), time.time() + 12
    timings = []
    for stage in (1, 2, 3):
        payload = {
            "schema_version": "1.2",
            "provider": client.provider,
            "profile_id": client.profile_id,
            "config_hash": client.config_hash,
            "request_id": request_id,
            "stage_index": stage,
            "task": ("classify_intent", "select_action", "resolve_context")[stage - 1],
            "request_expires_at": expires,
            "remaining_timeout_ms": 4000,
            "context_snapshot_id": "synthetic-transport-snapshot-v1",
            "candidate_set_id": "transport-" + str(stage),
            "utterance": "음악을 재생해줘",
            "context": {},
            "prompt_version": "transport-probe-v1",
            "candidates": [
                {"id": "play", "description": "음악 재생 요청"},
                {"id": "clarify", "description": "불명확하거나 해당 없음"},
            ],
        }
        start = time.monotonic()
        selected = await client.choose(payload, min(4, expires - time.time()))
        assert selected.calls == stage
        timings.append(round((time.monotonic() - start) * 1000))
    # GatewayClient rejects fabricated provenance. Replay has no new paid dispatch.
    replay = await client.choose(payload, 2)
    assert replay == selected
    print(
        json.dumps(
            {
                "status": "PASS",
                "scope": "synthetic TLS transport; not Korean quality",
                "provider": client.provider,
                "profile_id": client.profile_id,
                "config_hash": client.config_hash,
                "stages": 3,
                "provider_calls_total": 3,
                "forward_passes_total": None,
                "forward_passes_source": "unavailable",
                "cached_replay": "PASS",
                "stage_elapsed_ms": timings,
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    try:
        asyncio.run(run(parser.parse_args().config))
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
