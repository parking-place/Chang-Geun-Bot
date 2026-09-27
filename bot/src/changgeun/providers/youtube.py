"""Official public YouTube metadata API. No cookies, media extraction, or remote edits."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx

from changgeun.domain.models import DomainError
from changgeun.providers.media import Metadata


def playlist_id(url: str) -> str:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise DomainError("invalid_youtube_playlist") from None
    if (
        parts.scheme != "https"
        or parts.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com"}
        or parts.username
        or parts.password
        or port
        or parts.path not in {"/playlist", "/watch"}
    ):
        raise DomainError("invalid_youtube_playlist")
    values = parse_qs(parts.query).get("list", [])
    if len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]{10,100}", values[0]):
        raise DomainError("invalid_youtube_playlist")
    return values[0]


def duration_seconds(value: object) -> int | None:
    if not isinstance(value, str) or len(value) > 100:
        return None
    match = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match or not any(match.groups()):
        return None
    days, hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


@dataclass(frozen=True)
class PlaylistSnapshot:
    items: list[Metadata]
    complete: bool
    unavailable_count: int
    reason: str | None


class YouTubeData:
    def __init__(self, key: str, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if not key.strip():
            raise DomainError("youtube_key_missing")
        self.key, self.transport = key.strip(), transport

    async def _get(self, resource: str, parameters: dict[str, str | int]) -> dict[str, Any]:
        if resource not in {"search", "videos", "playlistItems"}:
            raise DomainError("invalid_youtube_resource")
        fields = {
            "search": "items(id/videoId)",
            "videos": (
                "items(id,snippet(title,channelTitle),contentDetails(duration),"
                "status(privacyStatus))"
            ),
            "playlistItems": "items(snippet(resourceId/videoId)),nextPageToken",
        }
        parameters = {**parameters, "fields": fields[resource], "prettyPrint": "false"}
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=4, trust_env=False, follow_redirects=False
            ) as client:
                async with client.stream(
                    "GET",
                    "https://www.googleapis.com/youtube/v3/" + resource,
                    params={**parameters, "key": self.key},
                ) as response:
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 262144:
                            raise DomainError("youtube_response_too_large")
                    if response.status_code != 200:
                        raise DomainError(
                            "youtube_quota_or_access"
                            if response.status_code in {403, 429}
                            else "youtube_metadata_failed"
                        )
                    payload = json.loads(data)
                    if (
                        not isinstance(payload, dict)
                        or not isinstance(payload.get("items"), list)
                        or not all(isinstance(item, dict) for item in payload["items"])
                    ):
                        raise DomainError("youtube_invalid_response")
                    return payload
        except (httpx.HTTPError, ValueError):
            # Exception URLs can contain the API key: never expose them to UI/logs.
            raise DomainError("youtube_metadata_failed") from None

    async def videos(self, identifiers: list[str]) -> dict[str, Metadata]:
        if not 1 <= len(identifiers) <= 50 or any(
            not re.fullmatch(r"[A-Za-z0-9_-]{11}", value) for value in identifiers
        ):
            raise DomainError("invalid_youtube_video_ids")
        result = await self._get(
            "videos", {"part": "snippet,contentDetails,status", "id": ",".join(identifiers)}
        )
        wanted = set(identifiers)
        videos: dict[str, Metadata] = {}
        for item in result["items"]:
            identifier = item.get("id")
            if not isinstance(identifier, str) or identifier not in wanted or identifier in videos:
                raise DomainError("youtube_invalid_response")
            status = item.get("status", {})
            if not isinstance(status, dict):
                raise DomainError("youtube_invalid_response")
            if status.get("privacyStatus") == "private":
                continue
            snippet = item.get("snippet", {})
            if not isinstance(snippet, dict) or not isinstance(
                item.get("contentDetails", {}), dict
            ):
                raise DomainError("youtube_invalid_response")
            title, author = snippet.get("title"), snippet.get("channelTitle")
            if not isinstance(title, str) or not title or not isinstance(author, str):
                raise DomainError("youtube_invalid_response")
            videos[identifier] = Metadata(
                identifier,
                title[:500],
                author[:200],
                duration_seconds(item.get("contentDetails", {}).get("duration", "")),
            )
        return videos

    async def search(self, query: str, count: int = 5) -> list[Metadata]:
        if not query.strip() or len(query) > 200 or type(count) is not int or not 1 <= count <= 10:
            raise DomainError("invalid_youtube_search")
        result = await self._get(
            "search", {"part": "snippet", "type": "video", "q": query, "maxResults": count}
        )
        if any(not isinstance(item.get("id"), dict) for item in result["items"]):
            raise DomainError("youtube_invalid_response")
        identifiers = [item["id"].get("videoId") for item in result["items"]]
        if any(not isinstance(identifier, str) for identifier in identifiers):
            raise DomainError("youtube_invalid_response")
        if not identifiers:
            return []
        metadata = await self.videos(identifiers)
        return [metadata[identifier] for identifier in identifiers if identifier in metadata]

    async def playlist(self, url: str, limit: int = 500) -> PlaylistSnapshot:
        identifier = playlist_id(url)
        if type(limit) is not int or not 1 <= limit <= 500:
            raise DomainError("invalid_import_limit")
        items: list[Metadata] = []
        unavailable, processed = 0, 0
        page_token = ""
        seen_tokens: set[str] = set()
        try:
            async with asyncio.timeout(30):
                while True:
                    parameters: dict[str, str | int] = {
                        "part": "snippet",
                        "playlistId": identifier,
                        "maxResults": min(50, limit - processed),
                    }
                    if page_token:
                        parameters["pageToken"] = page_token
                    page = await self._get("playlistItems", parameters)
                    references = []
                    for item in page["items"]:
                        snippet = item.get("snippet", {})
                        if not isinstance(snippet, dict) or not isinstance(
                            snippet.get("resourceId", {}), dict
                        ):
                            raise DomainError("youtube_invalid_response")
                        references.append(snippet.get("resourceId", {}).get("videoId"))
                    if len(references) > min(50, limit - processed):
                        raise DomainError("youtube_invalid_response")
                    valid = [
                        value
                        for value in references
                        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", value)
                    ]
                    # Keep playlist order and duplicates; unavailable items are explicitly counted.
                    metadata = await self.videos(list(dict.fromkeys(valid))) if valid else {}
                    for reference in references:
                        if isinstance(reference, str) and reference in metadata:
                            items.append(metadata[reference])
                        else:
                            unavailable += 1
                    processed += len(references)
                    page_token = page.get("nextPageToken", "")
                    if not page_token:
                        return PlaylistSnapshot(items, True, unavailable, None)
                    if (
                        not isinstance(page_token, str)
                        or page_token in seen_tokens
                        or not references
                    ):
                        raise DomainError("youtube_pagination_invalid")
                    seen_tokens.add(page_token)
                    if processed >= limit:
                        return PlaylistSnapshot(items, False, unavailable, "item_limit")
        except (DomainError, TimeoutError) as exc:
            if not processed:
                raise DomainError(
                    exc.code if isinstance(exc, DomainError) else "youtube_import_timeout"
                ) from None
            return PlaylistSnapshot(
                items,
                False,
                unavailable,
                exc.code if isinstance(exc, DomainError) else "youtube_import_timeout",
            )
