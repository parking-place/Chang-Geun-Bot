"""Isolated pinned extractor -> HTTPS -> FFmpeg stdin -> PCM stdout.

No cookies, configuration, plugins, cache, URL argv, media file or signed URL output.
The parent controls the process group and preparation deadline. Errors are codes only.
"""

from __future__ import annotations

import json
import os
import re
import resource
import socket
import ssl
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from changgeun.domain.models import DomainError
from changgeun.providers.network_guard import PinnedDNS, check_url


class Quiet:
    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


def extract(identifier: str, node: str) -> dict[str, Any]:
    import yt_dlp  # type: ignore[import-untyped]
    import yt_dlp.networking._urllib as networking  # type: ignore[import-untyped]

    original_redirect = networking.RedirectHandler.redirect_request

    def redirect(self: Any, req: Any, fp: Any, code: Any, msg: Any, headers: Any, url: str) -> Any:
        check_url(url)
        return original_redirect(self, req, fp, code, msg, headers, url)

    networking.RedirectHandler.redirect_request = redirect

    class Guarded(yt_dlp.YoutubeDL):  # type: ignore[misc]
        def urlopen(self, request: Any) -> Any:
            check_url(request if isinstance(request, str) else request.url)
            return super().urlopen(request)

    options = {
        "quiet": True,
        "no_warnings": True,
        "logger": Quiet(),
        "cachedir": False,
        "proxy": "",
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 4,
        "extractor_retries": 0,
        "retries": 0,
        "fragment_retries": 0,
        "format": "bestaudio[protocol=https]/best[protocol=https]",
        "js_runtimes": {"node": {"path": node}},
        "remote_components": set(),
        "plugin_dirs": [],
        "usenetrc": False,
        "geo_bypass": False,
    }
    with Guarded(options) as downloader:
        downloader._request_director.handlers = {
            key: value
            for key, value in downloader._request_director.handlers.items()
            if key == "Urllib"
        }
        result = downloader.extract_info(
            "https://www.youtube.com/watch?v=" + identifier, download=False
        )
    if not isinstance(result, dict) or result.get("id") != identifier:
        raise DomainError("youtube_unavailable")
    duration = result.get("duration")
    if (
        result.get("live_status") not in {None, "not_live", "was_live"}
        or result.get("is_live")
        or result.get("has_drm")
        or result.get("age_limit", 0) >= 18
        or result.get("availability") not in {None, "public", "unlisted"}
        or not isinstance(duration, (int, float))
        or isinstance(duration, bool)
        or not 0 < duration <= 1800
        or result.get("protocol") != "https"
    ):
        raise DomainError("youtube_unsupported")
    check_url(result.get("url", ""), media=True)
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        raise DomainError("media_redirect_denied")


def main() -> None:
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    socket.getaddrinfo = PinnedDNS().resolve  # type: ignore[assignment]
    header_sent = False
    ready_sent = False
    try:
        raw = json.loads(sys.stdin.buffer.read(1024))
        identifier, node = raw["id"], raw["node"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", identifier):
            raise DomainError("invalid_youtube_video_ids")
        node_path = Path(node)
        if (
            not node_path.is_absolute()
            or node_path.is_symlink()
            or not (
                node_path == Path("/usr/bin/node")
                or node_path.is_relative_to("/opt/changgeun-dev/runtimes")
            )
        ):
            raise DomainError("media_runtime_missing")
        info = extract(identifier, node)
        # Only bounded, nonsecret metadata leaves the extractor process.
        sys.stdout.buffer.write(json.dumps({"duration": info["duration"]}).encode() + b"\n")
        sys.stdout.buffer.flush()
        header_sent = True
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
        request = urllib.request.Request(info["url"], headers={"User-Agent": "Mozilla/5.0"})
        try:
            response = opener.open(request, timeout=5)
        except urllib.error.HTTPError:
            raise DomainError("youtube_stream_unavailable") from None
        with response:
            if response.status != 200:
                raise DomainError("youtube_stream_unavailable")
            process = subprocess.Popen(
                [
                    "/usr/bin/ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "quiet",
                    "-protocol_whitelist",
                    "pipe",
                    "-i",
                    "pipe:0",
                    "-vn",
                    "-f",
                    "s16le",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "pipe:1",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            assert process.stdin is not None and process.stdout is not None
            errors: list[bool] = []

            def feed() -> None:
                try:
                    # Streaming, bounded bytes; never persist media.
                    received = 0
                    while chunk := response.read(16384):
                        received += len(chunk)
                        if received > 256 * 1024 * 1024:
                            raise DomainError("media_byte_limit")
                        assert process.stdin is not None
                        process.stdin.write(chunk)
                except Exception:
                    errors.append(True)
                finally:
                    assert process.stdin is not None
                    process.stdin.close()

            thread = threading.Thread(target=feed, daemon=True)
            thread.start()
            first = bytearray()
            while len(first) < 3840:
                chunk = process.stdout.read(3840 - len(first))
                if not chunk:
                    break
                first.extend(chunk)
            if len(first) != 3840:
                raise DomainError("youtube_first_pcm_failed")
            sys.stdout.buffer.write(b'{"ready":true}\n')
            sys.stdout.buffer.write(first)
            sys.stdout.buffer.flush()
            ready_sent = True
            while frame := process.stdout.read(3840):
                sys.stdout.buffer.write(frame)
                sys.stdout.buffer.flush()
            thread.join(timeout=2)
            if thread.is_alive() or process.wait(timeout=2) != 0 or errors:
                raise DomainError("youtube_stream_failed")
    except DomainError as exc:
        if not header_sent and exc.code in {"youtube_unavailable", "youtube_unsupported"}:
            # A fixed code is safe to return; upstream text or media URLs are not.
            sys.stdout.buffer.write(json.dumps({"error": exc.code}).encode() + b"\n")
            sys.stdout.buffer.flush()
        elif header_sent and not ready_sent:
            code = (
                exc.code
                if exc.code in {"youtube_stream_unavailable", "youtube_first_pcm_failed"}
                else "youtube_prepare_failed"
            )
            sys.stdout.buffer.write(json.dumps({"error": code}).encode() + b"\n")
            sys.stdout.buffer.flush()
        os._exit(2)
    except Exception:
        # Never emit exceptions containing signed media URLs or upstream bodies.
        if header_sent and not ready_sent:
            sys.stdout.buffer.write(b'{"error":"youtube_prepare_failed"}\n')
            sys.stdout.buffer.flush()
        os._exit(2)


if __name__ == "__main__":
    main()
