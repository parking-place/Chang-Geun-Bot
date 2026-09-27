"""LXC-only first PCM probe; never persist media or expose signed URLs."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from changgeun.domain.models import DomainError
from changgeun.providers.youtube_audio import MediaResolver


async def run(identifier: str, node: Path) -> None:
    started = time.monotonic()
    resolver = MediaResolver(Path("/nonexistent"), {}, True, node)
    try:
        source = await resolver.prepare("youtube", identifier)
        frame = await asyncio.to_thread(source.read)
        await resolver.close()
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "first_pcm_bytes": len(frame),
                    "preparation_seconds": round(time.monotonic() - started, 3),
                    "scope": "actual extraction and PCM only; no Discord listening",
                }
            )
        )
    except DomainError as exc:
        print(
            json.dumps(
                {
                    "result": "FAIL",
                    "code": exc.code,
                    "preparation_seconds": round(time.monotonic() - started, 3),
                }
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--node", type=Path, default=Path("/usr/bin/node"))
    args = parser.parse_args()
    asyncio.run(run(args.video_id, args.node))
