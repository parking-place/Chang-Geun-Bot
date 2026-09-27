"""Bounded official metadata probe on DiscordBotLXC; never fetch audio or print URLs."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from changgeun.domain.models import DomainError
from changgeun.providers.youtube import YouTubeData


async def run(key_path: Path, playlist_file: Path | None, snapshot_file: Path | None) -> None:
    if not key_path.is_absolute() or key_path.is_symlink() or key_path.stat().st_mode & 0o077:
        raise DomainError("youtube_key_permissions")

    class CountedYouTube(YouTubeData):
        calls = 0

        async def _get(self, resource, parameters):
            self.calls += 1
            return await super()._get(resource, parameters)

    api = CountedYouTube(key_path.read_text().strip())
    if playlist_file is not None:
        snapshot = await api.playlist(playlist_file.read_text().strip())
        if snapshot_file is not None:
            data = {
                "schema_version": 1,
                "tracks": [
                    {"source_type": "youtube", "external_id": item.external_id, "title": item.title}
                    for item in snapshot.items
                ],
            }
            snapshot_file.write_text(
                json.dumps(
                    {
                        "export": data,
                        "source_metadata": {
                            item.external_id: {
                                "source_author": item.source_author,
                                "duration_seconds": item.duration_seconds,
                            }
                            for item in snapshot.items
                        },
                        "complete": snapshot.complete,
                        "unavailable_count": snapshot.unavailable_count,
                    },
                    ensure_ascii=False,
                )
            )
            snapshot_file.chmod(0o600)
        print(
            json.dumps(
                {
                    "status": "PASS" if snapshot.complete else "PARTIAL",
                    "official_requests": api.calls,
                    "playlist_items": len(snapshot.items),
                    "complete": snapshot.complete,
                    "unavailable_count": snapshot.unavailable_count,
                    "reason": snapshot.reason,
                    "duration_known": sum(
                        item.duration_seconds is not None for item in snapshot.items
                    ),
                    "unique_videos": len({item.external_id for item in snapshot.items}),
                    "audio_fetched": False,
                }
            )
        )
        return
    results = await api.search("창팝", count=1)
    if not results:
        raise DomainError("youtube_probe_no_results")
    first = results[0]
    refreshed = await api.videos([first.external_id])
    item = refreshed.get(first.external_id)
    if item is None or not item.title or item.duration_seconds is None:
        raise DomainError("youtube_probe_metadata_missing")
    print(
        json.dumps(
            {
                "status": "PASS",
                "official_requests": 3,
                "search_results": len(results),
                "title_present": bool(item.title),
                "author_present": bool(item.source_author),
                "duration_present": True,
                "audio_fetched": False,
                "playlist_import": "NOT_RUN",
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--playlist-file", type=Path)
    parser.add_argument("--snapshot-file", type=Path)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.key_file, args.playlist_file, args.snapshot_file))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                    "code": exc.code if isinstance(exc, DomainError) else "probe_failed",
                }
            )
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
