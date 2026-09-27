"""Metadata references and approved audio are independent, explicit sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

from changgeun.domain.models import DomainError


def youtube_id(url: str) -> str:
    if re.match(r"(?i)^(?:(?:www\.|m\.)?youtube\.com|youtu\.be)/", url):
        url = "https://" + url
    try:
        parts = urlsplit(url)
        invalid = parts.scheme != "https" or parts.username or parts.password or parts.port
    except ValueError:
        raise DomainError("invalid_youtube_url") from None
    if invalid:
        raise DomainError("invalid_youtube_url")
    if parts.hostname == "youtu.be":
        identifier = parts.path.strip("/")
    elif parts.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parts.path == "/watch":
            identifiers = parse_qs(parts.query).get("v", [])
            if len(identifiers) != 1:
                raise DomainError("invalid_youtube_url")
            identifier = identifiers[0]
        elif parts.path.startswith(("/shorts/", "/embed/")):
            identifier = parts.path.split("/")[-1]
        else:
            raise DomainError("invalid_youtube_url")
    else:
        raise DomainError("invalid_youtube_url")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", identifier):
        raise DomainError("invalid_youtube_url")
    return identifier


@dataclass(frozen=True)
class Metadata:
    external_id: str
    title: str
    source_author: str
    duration_seconds: int | None = None


class YouTubeMetadata:
    async def fetch(self, url: str) -> Metadata:
        identifier = youtube_id(url)
        async with httpx.AsyncClient(timeout=4, follow_redirects=False, trust_env=False) as client:
            result = await client.get(
                "https://www.youtube.com/oembed",
                params={"url": "https://www.youtube.com/watch?v=" + identifier, "format": "json"},
            )
            result.raise_for_status()
            if len(result.content) > 65536:
                raise DomainError("metadata_too_large")
            raw = result.json()
        return Metadata(identifier, str(raw["title"])[:500], str(raw["author_name"])[:200])


class ApprovedAudioResolver:
    def __init__(self, root: Path, mapping: dict[str, str]) -> None:
        self.root, self.mapping = root.resolve(), mapping

    def resolve(self, source_type: str, external_id: str) -> Path:
        if source_type != "approved_audio" or external_id not in self.mapping:
            raise DomainError("audio_source_not_approved")
        original = self.root / self.mapping[external_id]
        path = original.resolve()
        if original.is_symlink() or not path.is_relative_to(self.root) or not path.is_file():
            raise DomainError("invalid_audio_mapping")
        return path

    def validate(self, source_type: str, external_id: str) -> None:
        self.resolve(source_type, external_id)
