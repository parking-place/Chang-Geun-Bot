"""Validated startup configuration; no secret or provider auto-selection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from changgeun.discord_adapter.prefix import PREFIX, PrefixConfig
from changgeun.domain.models import Policy


@dataclass(frozen=True)
class BotConfig:
    database_path: Path
    policy: Policy
    audio_root: Path
    audio_mapping: dict[str, str]
    inference: dict[str, Any] | None = None
    youtube_key_file: Path | None = None
    prefix: PrefixConfig = field(default_factory=PrefixConfig)
    youtube_audio_enabled: bool = False
    youtube_js_runtime: Path = Path("/usr/bin/node")
    natural_parser_version: str = "v1"
    parser_llm_fallback: str = "disabled"
    parser_trace_path: Path | None = None

    @classmethod
    def read(cls, path: Path) -> BotConfig:
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict) or "<REPLACE_" in json.dumps(raw):
            raise ValueError("invalid/unresolved bot configuration")
        ids = {
            key: frozenset(str(v) for v in raw[section][key])
            for section, key in (
                ("app", "guild_allowlist"),
                ("permissions", "dj_role_ids"),
                ("commands", "allowed_text_channel_ids"),
                ("voice", "allowed_channel_ids"),
            )
        }
        if any(not values or any(not v.isdecimal() for v in values) for values in ids.values()):
            raise ValueError("explicit guild/role/channel IDs required")
        database = Path(raw["storage"]["database_path"])
        if not database.is_absolute():
            raise ValueError("absolute database path required")
        permissions = raw["permissions"]
        prefix_raw = raw["commands"].get("prefix", {})
        if not isinstance(prefix_raw, dict) or set(prefix_raw) - {
            "enabled",
            "value",
            "allowed_text_channel_ids",
        }:
            raise ValueError("invalid prefix configuration")
        enabled = prefix_raw.get("enabled", False)
        channels = prefix_raw.get("allowed_text_channel_ids", [])
        if type(enabled) is not bool or prefix_raw.get("value", PREFIX) != PREFIX:
            raise ValueError("invalid prefix configuration")
        if not isinstance(channels, list) or any(
            type(v) not in {str, int} or not str(v).isdecimal() for v in channels
        ):
            raise ValueError("invalid prefix channels")
        prefix = PrefixConfig(enabled, frozenset(str(v) for v in channels))
        if len(channels) != len(prefix.channel_ids) or len(channels) > 20:
            raise ValueError("duplicate/too many prefix channels")
        policy = Policy(
            ids["guild_allowlist"],
            ids["dj_role_ids"],
            ids["allowed_text_channel_ids"],
            ids["allowed_channel_ids"],
            admin_dj_override=permissions.get("admin_dj_override", False),
            same_voice_required=permissions.get(
                "require_same_voice_channel_for_playback_control", True
            ),
            allow_remote_voice_control=permissions.get("allow_remote_voice_control", False),
        )
        media = raw.get("media", {})
        youtube_audio = media.get("youtube_audio_enabled", False)
        if type(youtube_audio) is not bool:
            raise ValueError("youtube_audio_enabled must be boolean")
        inference = raw.get("active_inference")
        if inference is not None and (
            not isinstance(inference, dict) or inference.get("provider") != "jev-api"
        ):
            raise ValueError("active inference must use Jev API")
        parser_version = raw["commands"].get("natural_parser_version", "v1")
        llm_fallback = raw["commands"].get("parser_llm_fallback", "disabled")
        if parser_version not in {"v1", "v2"} or llm_fallback not in {
            "disabled", "gpt-5-nano"
        } or (parser_version == "v2" and inference is None):
            raise ValueError("invalid natural parser configuration")
        if parser_version == "v1" and llm_fallback != "disabled":
            raise ValueError("LLM fallback requires parser v2")
        trace_raw = raw["commands"].get("parser_trace_path")
        trace_path = Path(trace_raw) if isinstance(trace_raw, str) and trace_raw else None
        if (parser_version == "v2" and (trace_path is None or not trace_path.is_absolute())):
            raise ValueError("parser v2 requires an absolute trace path")
        if parser_version == "v1" and trace_path is not None:
            raise ValueError("parser trace path requires parser v2")
        return cls(
            database,
            policy,
            Path(media.get("approved_audio_root", "/var/lib/changgeun/audio")),
            media.get("approved_audio_mapping", {}),
            inference,
            Path(media["youtube_api_key_file"]) if media.get("youtube_api_key_file") else None,
            prefix,
            youtube_audio,
            Path(media.get("youtube_js_runtime", "/usr/bin/node")),
            parser_version,
            llm_fallback,
            trace_path,
        )
