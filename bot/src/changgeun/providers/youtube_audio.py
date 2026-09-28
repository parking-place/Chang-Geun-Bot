"""Bounded, cancellable media preparation. Discord consumes PCM, never a URL."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import os
import queue
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import discord

from changgeun.domain.models import DomainError
from changgeun.providers.media import ApprovedAudioResolver


class WorkerAudio(discord.AudioSource):
    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self.frames: queue.Queue[bytes | Exception] = queue.Queue(maxsize=16)
        self.loop = asyncio.get_running_loop()
        self.closed = False
        self.killed = False
        self.task: asyncio.Task[None] | None = None

    def read(self) -> bytes:
        try:
            item = self.frames.get(timeout=10)
        except queue.Empty:
            raise DomainError("youtube_stream_timeout") from None
        if isinstance(item, Exception):
            raise item
        return item

    def cleanup(self) -> None:
        if not self.closed:
            self.closed = True
            if self.loop.is_closed():
                self.kill()
            else:
                self.loop.call_soon_threadsafe(self._cancel)

    def _cancel(self) -> None:
        if self.task:
            self.task.cancel()
        self.kill()

    def kill(self) -> None:
        if self.killed:
            return
        self.killed = True
        if self.process.pid:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    async def reap(self) -> None:
        self.kill()
        async with asyncio.timeout(2):
            if self.process.stdout is not None:
                while await self.process.stdout.read(65536):
                    pass
            await self.process.wait()

    async def aclose(self) -> None:
        self.closed = True
        self._cancel()
        if self.task:
            await asyncio.gather(self.task, return_exceptions=True)
        else:
            await self.reap()

    async def pump(self) -> None:
        assert self.process.stdout is not None
        try:
            while True:
                try:
                    async with asyncio.timeout(10):
                        frame = await self.process.stdout.readexactly(3840)
                except asyncio.IncompleteReadError:
                    # Discord PCM frames are 20 ms; discard the final short frame.
                    break
                while self.frames.full():
                    await asyncio.sleep(0.01)
                self.frames.put_nowait(frame)
            code = await self.process.wait()
            item: bytes | Exception = b"" if code == 0 else DomainError("youtube_stream_failed")
            while self.frames.full():
                await asyncio.sleep(0.01)
            self.frames.put_nowait(item)
        except asyncio.CancelledError:
            raise
        except Exception:
            while self.frames.full():
                await asyncio.sleep(0.01)
            self.frames.put_nowait(DomainError("youtube_stream_failed"))
        finally:
            await self.reap()


class MediaResolver(ApprovedAudioResolver):
    def __init__(
        self,
        root: Path,
        mapping: dict[str, str],
        enabled: bool = False,
        node_path: Path = Path("/usr/bin/node"),
    ) -> None:
        super().__init__(root, mapping)
        self.enabled = enabled
        self.node_path = node_path
        self.preparation = asyncio.Semaphore(1)
        self.pending = 0
        self.sources: set[WorkerAudio] = set()
        self.poisoned = False
        if enabled:
            if importlib.metadata.version("yt-dlp") != "2026.8.19" or (
                importlib.metadata.version("yt-dlp-ejs") != "0.8.0"
            ):
                raise DomainError("media_runtime_missing")
            if (
                not node_path.is_absolute()
                or not node_path.is_file()
                or node_path.is_symlink()
                or (not Path("/usr/bin/ffmpeg").is_file())
            ):
                raise DomainError("media_runtime_missing")
            version = subprocess.check_output([str(node_path), "--version"], text=True, timeout=2)
            if int(version.strip().removeprefix("v").split(".")[0]) < 22:
                raise DomainError("media_runtime_unsupported")

    def validate(self, source_type: str, external_id: str) -> None:
        import re

        if source_type == "youtube" and self.enabled:
            if not re.fullmatch(r"[A-Za-z0-9_-]{11}", external_id):
                raise DomainError("invalid_youtube_video_ids")
            return
        self.resolve(source_type, external_id)

    async def prepare(self, source_type: str, external_id: str) -> discord.AudioSource:
        if self.poisoned:
            raise DomainError("media_cleanup_failed")
        self.validate(source_type, external_id)
        if source_type != "youtube":
            return discord.FFmpegPCMAudio(
                str(self.resolve(source_type, external_id)), options="-vn -loglevel error"
            )
        if self.pending >= 5:
            raise DomainError("media_capacity")
        self.pending += 1
        source: WorkerAudio | None = None
        try:
            async with asyncio.timeout(25):
                async with self.preparation:
                    process = await asyncio.create_subprocess_exec(
                        sys.executable,
                        "-m",
                        "changgeun.providers.youtube_worker",
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        start_new_session=True,
                        limit=65536,
                        env={
                            "PATH": "/usr/bin:/bin",
                            "LANG": "C.UTF-8",
                            "NODE_OPTIONS": "--max-old-space-size=128",
                            "YTDLP_NO_PLUGINS": "1",
                        },
                    )
                    source = WorkerAudio(process)
                    assert process.stdin is not None and process.stdout is not None
                    process.stdin.write(
                        json.dumps({"id": external_id, "node": str(self.node_path)}).encode()
                    )
                    await process.stdin.drain()
                    process.stdin.close()
                    async with asyncio.timeout(15):
                        header = await process.stdout.readline()
                        if len(header) > 1024:
                            raise DomainError("youtube_invalid_response")
                        metadata: dict[str, Any] = json.loads(header)
                        if metadata.get("error") in {"youtube_unavailable", "youtube_unsupported"}:
                            raise DomainError(metadata["error"])
                        if not 0 < metadata["duration"] <= 1800:
                            raise DomainError("youtube_unsupported")
                    async with asyncio.timeout(10):
                        try:
                            first = await process.stdout.readexactly(3840)
                        except asyncio.IncompleteReadError:
                            raise DomainError("youtube_first_pcm_failed") from None
                    source.frames.put_nowait(first)
                    source.task = asyncio.create_task(source.pump())
                    self.sources.add(source)

                    def released(task: asyncio.Task[None], audio: WorkerAudio = source) -> None:
                        self.sources.discard(audio)
                        if not task.cancelled() and task.exception() is not None:
                            self.poisoned = True

                    source.task.add_done_callback(released)
                    return source
        except asyncio.CancelledError:
            if source:
                await source.aclose()
            raise
        except DomainError:
            if source:
                await source.aclose()
            raise
        except TimeoutError:
            if source:
                await source.aclose()
            raise DomainError("youtube_prepare_timeout") from None
        except Exception:
            if source:
                await source.aclose()
            raise DomainError("youtube_prepare_failed") from None
        finally:
            self.pending -= 1

    async def close(self) -> None:
        await asyncio.gather(*(source.aclose() for source in tuple(self.sources)))
