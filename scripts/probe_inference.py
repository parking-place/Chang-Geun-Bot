"""Single bounded provider probe through the durable service; run on OpenJevLXC."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path

from changgeun_inference.config import read_profile
from changgeun_inference.contracts import Candidate, DecisionRequest
from changgeun_inference.ledger import Ledger
from changgeun_inference.providers import HostedProvider
from changgeun_inference.service import DecisionService, ServiceError


async def run(args: argparse.Namespace) -> None:
    config, config_hash = read_profile(args.profile)
    key = args.key_env.read_text().split("=", 1)[1].strip()
    hosted = config["hosted"]
    provider = HostedProvider(hosted["endpoint"], hosted["model"], key)
    service = DecisionService(
        provider,
        Ledger(args.ledger),
        provider_name=config["provider"],
        profile_id=config["profile_id"],
        config_hash=config_hash,
        run_id=args.run_id,
        max_run_calls=20,
    )
    request = DecisionRequest(
        schema_version="1.2",
        provider=config["provider"],
        profile_id=config["profile_id"],
        config_hash=config_hash,
        request_id=str(uuid.uuid4()),
        stage_index=1,
        task="classify_intent",
        request_expires_at=time.time() + 12,
        remaining_timeout_ms=4000,
        context_snapshot_id="synthetic-baseline",
        candidate_set_id="intent-probe-v1",
        utterance="음악을 재생해줘",
        context={},
        prompt_version="probe-v1",
        candidates=[
            Candidate(id="play", description="음악 재생을 요청한다"),
            Candidate(id="clarify", description="명령이 아니거나 불명확하다"),
        ],
    )
    started = time.perf_counter()
    try:
        result = await service.decide(request)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                    "result": result,
                },
                ensure_ascii=False,
            )
        )
    except ServiceError as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": exc.code,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000),
                }
            )
        )
        await service.drain()
        raise SystemExit(1) from None
    await service.drain()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--key-env", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
