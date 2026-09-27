"""LXC-only bounded real first-PCM evaluation; not Discord/soak acceptance."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time
from pathlib import Path

from changgeun.config import BotConfig
from changgeun.domain.models import DomainError
from changgeun.providers.youtube import YouTubeData
from changgeun.providers.youtube_audio import MediaResolver


async def run(config_path: Path, playlist: str, output: Path) -> None:
    if output.exists():
        raise ValueError("evaluation output already exists")
    config = BotConfig.read(config_path)
    if not config.youtube_audio_enabled or config.youtube_key_file is None:
        raise ValueError("explicit media candidate and key required")
    api = YouTubeData(config.youtube_key_file.read_text().strip())
    snapshot = await api.playlist(playlist)
    videos = [
        m
        for m in snapshot.items
        if m.duration_seconds is not None and 0 < m.duration_seconds <= 1800
    ][:20]
    if len(videos) != 20:
        raise ValueError("20 finite known-length public fixtures required")
    results = []
    resolver = MediaResolver(
        config.audio_root, config.audio_mapping, True, config.youtube_js_runtime
    )
    for iteration in range(5):
        for index, metadata in enumerate(videos):
            started = time.monotonic()
            source = None
            try:
                source = await resolver.prepare("youtube", metadata.external_id)
                frame = await asyncio.to_thread(source.read)
                if len(frame) != 3840:
                    raise DomainError("invalid_pcm_frame")
                result, error = "PASS", None
            except DomainError as exc:
                result, error = "FAIL", exc.code
            finally:
                if source:
                    await resolver.close()
            results.append(
                {
                    "round": iteration + 1,
                    "fixture_index": index,
                    "result": result,
                    "seconds": round(time.monotonic() - started, 3),
                    "error_code": error,
                }
            )
            if len(results) % 10 == 0:
                print(
                    json.dumps(
                        {
                            "completed": len(results),
                            "planned": 100,
                            "passed": sum(r["result"] == "PASS" for r in results),
                        }
                    ),
                    flush=True,
                )
    times = sorted(r["seconds"] for r in results if r["result"] == "PASS")
    report = {
        "scope": "actual first PCM only; not Discord transition/listening/8h soak",
        "fixture_count": len(videos),
        "attempts": len(results),
        "passed": len(times),
        "p95_seconds": times[math.ceil(len(times) * 0.95) - 1] if times else None,
        "results": results,
    }
    with output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    output.chmod(0o600)
    print(json.dumps({k: v for k, v in report.items() if k != "results"}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--playlist", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.config, args.playlist, args.output))
