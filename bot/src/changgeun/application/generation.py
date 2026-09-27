"""Deterministic catalog rules. Never infer or fetch additional songs."""

from __future__ import annotations

import json
import random
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any

from changgeun.domain.models import DomainError, digest, normalized_name


@dataclass(frozen=True)
class Rules:
    include_tags: tuple[str, ...] = ()
    exclude_tags: tuple[str, ...] = ()
    creator: str | None = None
    count: int = 20
    max_seconds: int | None = None
    recent_days: int = 7
    seed: int = 0

    def validate(self) -> None:
        if type(self.count) is not int or not 1 <= self.count <= 100:
            raise DomainError("invalid_generation_rules")
        if type(self.recent_days) is not int or not 0 <= self.recent_days <= 365:
            raise DomainError("invalid_generation_rules")
        if type(self.seed) is not int or not -(2**63) <= self.seed < 2**63:
            raise DomainError("invalid_generation_rules")
        if self.max_seconds is not None and (
            type(self.max_seconds) is not int or not 1 <= self.max_seconds <= 86400
        ):
            raise DomainError("invalid_generation_rules")
        if self.creator is not None:
            if not isinstance(self.creator, str):
                raise DomainError("invalid_generation_rules")
            normalized_name(self.creator)
        for values in (self.include_tags, self.exclude_tags):
            if not isinstance(values, tuple) or len(values) > 20:
                raise DomainError("invalid_generation_rules")
            for value in values:
                if not isinstance(value, str):
                    raise DomainError("invalid_generation_rules")
                normalized_name(value)

    def serialize(self) -> dict[str, Any]:
        result = asdict(self)
        result["include_tags"], result["exclude_tags"] = (
            list(self.include_tags),
            list(self.exclude_tags),
        )
        return result

    @classmethod
    def read(cls, raw: dict[str, Any]) -> Rules:
        if not isinstance(raw, dict) or set(raw) != set(cls().serialize()):
            raise DomainError("invalid_generation_rules")
        values = dict(raw)
        for key in ("include_tags", "exclude_tags"):
            if not isinstance(values[key], list):
                raise DomainError("invalid_generation_rules")
            values[key] = tuple(values[key])
        rules = cls(**values)
        rules.validate()
        return rules


@dataclass(frozen=True)
class Generated:
    track_ids: list[str]
    snapshot_hash: str
    requested_count: int
    known_seconds: int
    unknown_durations: int


def select(conn: sqlite3.Connection, guild: str, rules: Rules, reference_time: float) -> Generated:
    rules.validate()
    tracks = [
        dict(row)
        for row in conn.execute("SELECT * FROM tracks WHERE guild_id=? ORDER BY id", (guild,))
    ]
    history = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM playback_history WHERE guild_id=? ORDER BY played_at,entry_id", (guild,)
        )
    ]
    snapshot = digest({"tracks": tracks, "history": history})
    recent = {
        row["track_id"]
        for row in history
        if rules.recent_days and row["played_at"] >= reference_time - rules.recent_days * 86400
    }
    include, exclude = (
        {normalized_name(value) for value in tags}
        for tags in (rules.include_tags, rules.exclude_tags)
    )
    eligible: list[tuple[str, str, int | None]] = []
    for track in tracks:
        if track["id"] in recent:
            continue
        annotations = json.loads(track["annotations_json"])
        tags = {normalized_name(tag) for tag in annotations.get("tags", [])}
        if not include <= tags or exclude & tags:
            continue
        if rules.creator is not None and normalized_name(
            annotations.get("creator", "미표기")
        ) != normalized_name(rules.creator):
            continue
        metadata = json.loads(track["metadata_json"])
        seconds = metadata.get("duration_seconds")
        if type(seconds) is not int or seconds < 0:
            seconds = None
        if rules.max_seconds is not None and seconds is None:
            continue
        eligible.append((track["id"], track["external_id"], seconds))
    random.Random(rules.seed).shuffle(eligible)
    seen: set[str] = set()
    selected: list[str] = []
    total = unknown = 0
    for identifier, external_id, seconds in eligible:
        if external_id in seen:
            continue
        if rules.max_seconds is not None and total + (seconds or 0) > rules.max_seconds:
            continue
        seen.add(external_id)
        selected.append(identifier)
        total += seconds or 0
        unknown += int(seconds is None)
        if len(selected) == rules.count:
            break
    return Generated(selected, snapshot, rules.count, total, unknown)
