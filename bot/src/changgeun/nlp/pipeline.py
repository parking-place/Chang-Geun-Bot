"""Closed candidates, immutable request budgets and conditional context resolution."""

from __future__ import annotations

import asyncio
import json
import math
import re
import time
import unicodedata
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import Any, Protocol

from changgeun.application.watch import policy_for_request
from changgeun.domain.models import (
    Action,
    ActionPlan,
    Actor,
    DomainError,
    InferenceTrace,
    Policy,
    authorize,
    normalized_name,
)
from changgeun.observability import Metrics
from changgeun.providers.media import youtube_id
from changgeun.storage.database import Database

INTENTS = {
    "play_request": "등록곡 또는 저장 목록을 틀거나 재생하기; 목록 보기/조회와 다름",
    "playback_control": "일시정지, 계속, 넘기기, 정지, 음량, 반복 제어",
    "queue_edit": "현재 재생 대기열 항목 추가, 제거, 이동, 비우기; 저장 목록에 넣기는 해당 없음",
    "playlist_edit": (
        "저장 목록 편집: 이름만 정한 빈 목록 만들기/생성, "
        "현재곡을 특정 저장 목록에 넣기, 제거/이동/삭제"
    ),
    "playlist_generate": (
        "등록 카탈로그에서 태그/제작자/길이/개수 조건으로 곡을 선곡하여 목록 구성; "
        "빈 목록 생성은 제외"
    ),
    "info_query": "목록, 현재곡, 대기열, 등록된 곡 정보 조회",
    "voice_control": "허용 음성채널 입장, 이동, 퇴장",
    "song_proposal": "일반 멤버의 곡 제안",
    "non_command": "감상, 설명, 질문 등 동작을 요청하지 않음",
    "clarify": "모호하거나 지원하지 않는 요청; 사용자에게 다시 질문",
}


@dataclass(frozen=True)
class Choice:
    id: str
    description: str


@dataclass(frozen=True)
class Selection:
    selected_id: str
    probabilities: dict[str, float]
    calls: int


class DecisionPort(Protocol):
    provider: str
    profile_id: str
    config_hash: str

    async def choose(self, payload: dict[str, Any], timeout: float) -> Selection: ...


@dataclass(frozen=True)
class Reference:
    playlist_id: str
    name: str
    expires_at: float


class ContextCache:
    def __init__(self, *, clock: Any = time.monotonic) -> None:
        self.clock = clock
        self.values: dict[tuple[str, str, str], list[Reference]] = {}

    def remember(self, actor: Actor, playlist_id: str, name: str) -> None:
        key = (actor.guild_id, actor.text_channel_id, actor.user_id)
        previous = self.values.get(key, [])
        self.values[key] = (
            [Reference(playlist_id, name, self.clock() + 120)]
            + [r for r in previous if r.playlist_id != playlist_id and r.expires_at > self.clock()]
        )[:2]

    def get(self, actor: Actor) -> list[Reference]:
        key = (actor.guild_id, actor.text_channel_id, actor.user_id)
        return [r for r in self.values.get(key, []) if r.expires_at > self.clock()]


NUMBERS = {
    "첫": 1,
    "한": 1,
    "하나": 1,
    "두": 2,
    "둘": 2,
    "세": 3,
    "셋": 3,
    "네": 4,
    "넷": 4,
    "다섯": 5,
    "여섯": 6,
    "일곱": 7,
    "여덟": 8,
    "아홉": 9,
    "열": 10,
    "스무": 20,
    "스물": 20,
    "서른": 30,
    "백": 100,
}


def korean_number(text: str) -> int | None:
    value = text.strip()
    return int(value) if value.isdecimal() and len(value) <= 3 else NUMBERS.get(value)


def anonymized(text: str) -> str:
    text = re.sub(r"<[@#][!&]?\d+>", "[참조]", text)
    text = re.sub(r"\b\d{17,20}\b", "[식별자]", text)
    text = re.sub(r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}", "[비밀값]", text)
    return text


@dataclass(frozen=True)
class CandidatePlan:
    choice: Choice
    plan: ActionPlan | None = None
    unresolved_action: Action | None = None


class Pipeline:
    def __init__(
        self,
        db: Database,
        policy: Policy,
        port: DecisionPort,
        *,
        confidence: float,
        margin: float,
        prompt_version: str,
        context: ContextCache | None = None,
    ) -> None:
        if port.provider not in {"jev-api", "mock"}:
            raise ValueError("invalid explicit provider")
        if not 0.5 <= confidence <= 1 or not 0 <= margin < 1:
            raise ValueError("invalid development thresholds")
        self.db, self.policy, self.port = db, policy, port
        self.binding = (port.provider, port.profile_id, port.config_hash)
        self.confidence, self.margin, self.prompt_version = confidence, margin, prompt_version
        self.context = context or ContextCache()
        self.cooldowns: dict[tuple[str, str, str], float] = {}
        self.metrics = Metrics()

    def _snapshot(self, guild: str) -> dict[str, Any]:
        observed_at = time.monotonic()
        conn = self.db.connect()
        try:
            conn.execute("BEGIN")
            return {
                "session": dict(
                    conn.execute("SELECT * FROM sessions WHERE guild_id=?", (guild,)).fetchone()
                ),
                "playlists": [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM playlists "
                        "WHERE guild_id=? AND deleted_at IS NULL ORDER BY normalized_name",
                        (guild,),
                    )
                ],
                "playlist_entries": [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM playlist_entries "
                        "WHERE guild_id=? ORDER BY playlist_id,position",
                        (guild,),
                    )
                ],
                "queue": [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM queue_entries WHERE guild_id=? ORDER BY position", (guild,)
                    )
                ],
                "tracks": [
                    dict(r) for r in conn.execute("SELECT * FROM tracks WHERE guild_id=?", (guild,))
                ],
            }
        finally:
            conn.close()
            self.metrics.duration("snapshot", time.monotonic() - observed_at)

    def _session_marker(self, guild: str) -> tuple[int, int]:
        """Read only the state that can invalidate an in-flight decision."""
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT version,generation FROM sessions WHERE guild_id=?", (guild,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise DomainError("guild_not_allowed")
        return int(row[0]), int(row[1])

    def _plan(
        self,
        actor: Actor,
        request: str,
        snapshot: dict[str, Any],
        action: Action,
        arguments: dict[str, Any],
    ) -> ActionPlan:
        versions = {}
        if "playlist_id" in arguments:
            rows = [p for p in snapshot["playlists"] if p["id"] == arguments["playlist_id"]]
            if not rows:
                raise DomainError("playlist_not_found")
            versions[arguments["playlist_id"]] = rows[0]["version"]
        if action.value.startswith(("queue.", "playback.", "voice.")) or action in {
            Action.PLAYLIST_PLAY,
            Action.TRACK_PLAY,
        }:
            versions["queue"] = snapshot["session"]["version"]
        return ActionPlan(
            request,
            actor.guild_id,
            actor.user_id,
            action,
            arguments,
            versions,
            "natural_language",
            snapshot["session"]["generation"],
        )

    def _candidates(
        self, text: str, actor: Actor, request: str, snapshot: dict[str, Any]
    ) -> tuple[str, list[CandidatePlan]]:
        normalized = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
        plans: list[tuple[str, Action, dict[str, Any]]] = []
        group = "clarify"
        lines = [line for line in text.splitlines() if line.strip()]
        if (
            sum(
                bool(re.search(r"틀어|재생|멈|정지|빼|지워|비우|추가|넣어|나가", line))
                for line in lines
            )
            > 1
        ):
            return group, []
        # Never let a classifier select one half of a compound mutation.
        if re.search(
            r"그리고|(?:비우|지우|삭제하|제거하|추가하|넣|생성하|만들|재생하|틀|"
            r"멈추|정지하|넘기|퇴장하|입장하)(?:고|한\s*뒤|한\s*후).*"
            r"(?:재생|틀어|정지|멈|퇴장|나가|입장|들어|삭제|제거|지워|빼|비우|"
            r"넣|추가|넘겨|다음\s*곡|생성|만들)",
            normalized,
        ):
            return group, []
        if re.search(r"(?:명령(?:어)?|방법|뜻|사용법).*(?:무엇|뭐|설명|알려|어떻게)", normalized):
            return group, []
        safe_move = bool(re.search(r"(?:지우|삭제하|빼|제거하)지\s*말고.*(?:뒤|끝)", normalized))
        safe_add = bool(
            re.search(r"틀지\s*말고", normalized)
            and re.search(r"현재곡|지금\s*곡", normalized)
            and re.search(r"추가|넣어", normalized)
        )
        # Negations are never removed/truncated before interpretation.
        if not (safe_move or safe_add) and re.search(
            r"하지\s*마|하지말|하지\s*말|지\s*말|안\s*(?:틀|지워|빼)|않", normalized
        ):
            if ("목록" in normalized or "대기열" in normalized) and "보" in normalized:
                action = Action.QUEUE_SHOW if "대기열" in normalized else Action.PLAYLIST_LIST
                return "info_query", [
                    CandidatePlan(
                        Choice("c1", "변경 없이 정보만 조회"),
                        self._plan(actor, request, snapshot, action, {}),
                    )
                ]
            return group, []
        if "대기열" in normalized:
            number_match = re.search(
                r"(\d{1,3}|첫|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*"
                r"(?:번째|번\s*째|번)",
                normalized,
            )
            number = korean_number(number_match[1]) if number_match else None
            if re.search(r"비우|모두.*(?:빼|지워)", normalized):
                group = "queue_edit"
                plans.append(("대기 중인 항목만 비우기; 현재곡 유지", Action.QUEUE_CLEAR, {}))
            elif number is not None and 1 <= number <= len(snapshot["queue"]):
                entry = snapshot["queue"][number - 1]
                group = "queue_edit"
                if not safe_move and re.search(r"빼|제거|지워|삭제", normalized):
                    plans.append(
                        (
                            f"대기열의 선택 항목 {number} 제거",
                            Action.QUEUE_REMOVE,
                            {"entry_id": entry["id"]},
                        )
                    )
                elif re.search(r"뒤|끝|이동", normalized):
                    plans.append(
                        (
                            f"대기열의 선택 항목 {number} 맨 뒤로 이동",
                            Action.QUEUE_MOVE,
                            {"entry_id": entry["id"], "position": len(snapshot["queue"]) - 1},
                        )
                    )
            elif re.search(r"보|알려|확인", normalized):
                group = "info_query"
                plans.append(("대기열 정보 조회", Action.QUEUE_SHOW, {}))
        controls = [
            (r"일시\s*정지|잠깐.*멈", Action.PLAYBACK_PAUSE, "현재 위치에서 일시정지"),
            (r"계속|재개", Action.PLAYBACK_RESUME, "일시정지 재개"),
            (r"넘겨|넘기|다음\s*곡", Action.PLAYBACK_SKIP, "현재곡 건너뛰기"),
            (r"정지|멈춰", Action.PLAYBACK_STOP, "현재 항목을 앞에 보존하고 정지"),
        ]
        if not plans and "대기열" not in normalized:
            for pattern, action, description in controls:
                if re.search(pattern, normalized):
                    group = "playback_control"
                    if (
                        action == Action.PLAYBACK_RESUME
                        and snapshot["session"]["desired_state"] == "idle"
                    ):
                        action = Action.PLAYBACK_START
                    plans.append((description, action, {}))
                    break
            volume = re.search(r"(?:볼륨|음량)\s*(\d{1,3})", normalized)
            if volume and 0 <= int(volume[1]) <= 100:
                group = "playback_control"
                plans = [("음량 설정", Action.PLAYBACK_VOLUME, {"percent": int(volume[1])})]
        if not plans and re.search(r"나가|퇴장", normalized):
            group = "voice_control"
            plans.append(("현재곡 보존 후 퇴장", Action.VOICE_LEAVE, {}))
        if not plans and re.search(r"입장|들어와|와\s*줘", normalized) and actor.voice_channel_id:
            group = "voice_control"
            action = (
                Action.VOICE_MOVE
                if actor.bot_voice_channel_id
                and actor.bot_voice_channel_id != actor.voice_channel_id
                else Action.VOICE_JOIN
            )
            plans.append(
                ("요청자가 있는 허용 채널로 연결", action, {"channel_id": actor.voice_channel_id})
            )
        if not plans and "목록" in normalized and re.search(r"보여|보기|알려", normalized):
            group = "info_query"
            plans.append(("저장된 목록 조회", Action.PLAYLIST_LIST, {}))
        if not plans and re.search(
            r"(?:지금|현재).*?(?:무슨\s*곡|곡.*(?:알려|보여|뭐))", normalized
        ):
            group = "info_query"
            plans.append(("현재곡과 대기열 조회", Action.QUEUE_SHOW, {}))
        quoted = re.search(r'["“‘\']([^"”’\']{1,100})["”’\']\s*(?:목록|플레이리스트)', text)
        urls = re.findall(
            r"(?<![\w@./:-])(?:https?://[^\s<>]+|"
            r"(?:(?:www\.|m\.)?youtube\.com|youtu\.be)/[^\s<>]+)",
            text,
            flags=re.IGNORECASE,
        )
        if not plans and urls and re.search(r"틀어|재생", normalized):
            target_channel = actor.bot_voice_channel_id or actor.voice_channel_id
            if len(urls) != 1 or not target_channel:
                return "clarify", []
            try:
                identifier = youtube_id(urls[0])
            except DomainError:
                return "clarify", []
            group = "play_request"
            plans.append(
                (
                    "지정한 YouTube 영상 오디오 재생",
                    Action.TRACK_PLAY,
                    {"track_id": "youtube:" + identifier, "channel_id": target_channel},
                )
            )
        if not plans and quoted and re.search(r"만들|생성", normalized):
            group = "playlist_edit"
            plans.append(
                ("지정한 이름으로 빈 목록 생성", Action.PLAYLIST_CREATE, {"name": quoted[1]})
            )
        matched = [p for p in snapshot["playlists"] if normalized_name(p["name"]) in normalized]
        matched.sort(key=lambda p: (-len(normalized_name(p["name"])), p["normalized_name"]))
        if len(matched) > 10 and re.search(r"틀어|재생|추가|넣어", normalized):
            # Truncation could silently discard the intended target.
            return "clarify", []
        if not plans and matched and re.search(r"틀어|재생", normalized):
            group = "play_request"
            target_channel = actor.bot_voice_channel_id or actor.voice_channel_id
            if target_channel:
                for playlist in matched[:10]:
                    tracks = [
                        e["track_id"]
                        for e in snapshot["playlist_entries"]
                        if e["playlist_id"] == playlist["id"]
                    ]
                    plans.append(
                        (
                            "등록된 " + playlist["name"] + " 목록 재생",
                            Action.PLAYLIST_PLAY,
                            {
                                "playlist_id": playlist["id"],
                                "channel_id": target_channel,
                                "track_ids": tracks,
                            },
                        )
                    )
        if (
            not plans
            and snapshot["session"]["current_track_id"]
            and re.search(r"현재곡|지금\s*곡", normalized)
        ):
            if re.search(r"추가|넣어", normalized):
                group = "playlist_edit"
                for playlist in matched[:10]:
                    plans.append(
                        (
                            "현재곡을 " + playlist["name"] + " 저장 목록에 추가",
                            Action.PLAYLIST_ADD,
                            {
                                "playlist_id": playlist["id"],
                                "track_ids": [snapshot["session"]["current_track_id"]],
                            },
                        )
                    )
                if (
                    not plans
                    and re.search(r"아까|앞에서|그\s*목록", normalized)
                    and self.context.get(actor)
                ):
                    return group, [
                        CandidatePlan(
                            Choice("c1", "현재곡을 최근 참조한 저장 목록에 추가"),
                            unresolved_action=Action.PLAYLIST_ADD,
                        )
                    ]
        if not plans and re.search(r"틀어|재생", normalized):
            target_channel = actor.bot_voice_channel_id or actor.voice_channel_id
            if target_channel:
                track_matches: list[tuple[int, dict[str, Any]]] = []
                for track in snapshot["tracks"]:
                    names = [track["title"]] + json.loads(track["annotations_json"]).get(
                        "aliases", []
                    )
                    matching = [
                        len(normalized_name(name))
                        for name in names
                        if isinstance(name, str)
                        and 1 <= len(name) <= 100
                        and normalized_name(name) in normalized
                    ]
                    if matching:
                        track_matches.append((max(matching), track))
                if len(track_matches) > 10:
                    return "clarify", []
                for _, track in sorted(
                    track_matches, key=lambda item: (-item[0], item[1]["title"], item[1]["id"])
                ):
                    group = "play_request"
                    plans.append(
                        (
                            "등록 곡 " + track["title"] + " 재생",
                            Action.TRACK_PLAY,
                            {"track_id": track["id"], "channel_id": target_channel},
                        )
                    )
        candidates = [
            CandidatePlan(
                Choice("c" + str(i + 1), description),
                self._plan(actor, request, snapshot, action, arguments),
            )
            for i, (description, action, arguments) in enumerate(plans[:10])
        ]
        return group, candidates

    async def interpret(
        self,
        text: str,
        actor: Actor,
        *,
        started_at: float | None = None,
        refresh_actor: Callable[[], Awaitable[Actor]] | None = None,
        request_id: str | None = None,
    ) -> ActionPlan | None:
        observed_at = time.monotonic()
        try:
            result = await self._interpret_impl(
                text,
                actor,
                started_at=started_at,
                refresh_actor=refresh_actor,
                request_id=request_id,
            )
        except asyncio.CancelledError:
            self.metrics.outcome("cancelled")
            raise
        except DomainError:
            self.metrics.outcome("rejected")
            raise
        except Exception:
            self.metrics.outcome("failed")
            raise
        else:
            self.metrics.outcome("selected" if result else "clarified")
            return result
        finally:
            self.metrics.duration("request", time.monotonic() - observed_at)

    async def _interpret_impl(
        self,
        text: str,
        actor: Actor,
        *,
        started_at: float | None = None,
        refresh_actor: Callable[[], Awaitable[Actor]] | None = None,
        request_id: str | None = None,
    ) -> ActionPlan | None:
        request_id = request_id or str(uuid.uuid4())
        proven_request = request_id

        def request_policy() -> Policy:
            conn = self.db.connect()
            try:
                return policy_for_request(conn, self.policy, actor, proven_request)
            finally:
                conn.close()

        started_at = started_at if started_at is not None else time.monotonic()
        if not text.strip() or len(text) > 500:
            raise DomainError("input_too_large")
        key = (actor.guild_id, actor.text_channel_id, actor.user_id)
        now = time.monotonic()
        if self.cooldowns.get(key, 0) > now:
            raise DomainError("user_cooldown")
        self.cooldowns[key] = now + 2
        authorize(
            ActionPlan("preflight", actor.guild_id, actor.user_id, Action.PLAYLIST_LIST),
            actor,
            request_policy(),
        )
        request_id, snapshot_id = request_id or str(uuid.uuid4()), str(uuid.uuid4())
        snapshot = self._snapshot(actor.guild_id)
        group, candidates = self._candidates(text, actor, request_id, snapshot)
        if group == "clarify" or not candidates:
            return None
        # Deny only when every feasible interpretation has the same permission
        # requirement. Mixed read/write candidates still need model selection.
        actions = {
            c.plan.action if c.plan is not None else c.unresolved_action for c in candidates
        }
        if len(actions) == 1:
            first_plan = candidates[0].plan
            if first_plan is not None:
                authorize(first_plan, actor, request_policy())
        expires = time.time() + max(0, 12 - (time.monotonic() - started_at))

        def complete(plan: ActionPlan, stage: int) -> ActionPlan:
            trace = InferenceTrace(
                *self.binding,
                stages=stage,
                questions=stage,
                provider_calls=stage,
                forward_passes=None,
                forward_passes_source="unavailable",
            )
            return replace(plan, expires_at=expires, inference=trace)

        async def choose(stage: int, choices: list[Choice], context: dict[str, str]) -> str:
            nonlocal actor
            if stage > 1 and refresh_actor:
                actor = await refresh_actor()
                permission_action = (
                    candidates[0].plan.action
                    if candidates[0].plan
                    else candidates[0].unresolved_action
                )
                if permission_action:
                    authorize(
                        self._plan(actor, request_id, snapshot, permission_action, {}),
                        actor,
                        request_policy(),
                    )
            request_policy()  # Each dispatch rechecks the durable source/generation.
            if (self.port.provider, self.port.profile_id, self.port.config_hash) != self.binding:
                raise DomainError("inference_profile_mismatch")
            if self._session_marker(actor.guild_id) != (
                snapshot["session"]["version"],
                snapshot["session"]["generation"],
            ):
                raise DomainError("execution_generation_conflict")
            remaining = 12 - (time.monotonic() - started_at)
            if remaining <= 0 or stage == 3 and remaining < 1:
                raise DomainError("inference_deadline")
            opaque = choices + [Choice("clarify", "불명확하거나 지원하지 않는 요청")]
            payload = {
                "schema_version": "1.2",
                "provider": self.binding[0],
                "profile_id": self.binding[1],
                "config_hash": self.binding[2],
                "request_id": request_id,
                "stage_index": stage,
                "task": ("classify_intent", "select_action", "resolve_context")[stage - 1],
                "request_expires_at": expires,
                "remaining_timeout_ms": min(4000, int(remaining * 1000)),
                "context_snapshot_id": snapshot_id,
                "candidate_set_id": snapshot_id + "-" + str(stage),
                "utterance": anonymized(text),
                "context": context,
                "candidates": [
                    {"id": c.id, "description": anonymized(c.description)[:200]} for c in opaque
                ],
                "prompt_version": self.prompt_version,
            }
            decision_started = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    self.port.choose(payload, min(4, remaining)), min(4, remaining)
                )
            finally:
                self.metrics.duration("decision", time.monotonic() - decision_started)
            request_policy()  # Each dispatch rechecks the durable source/generation.
            if (self.port.provider, self.port.profile_id, self.port.config_hash) != self.binding:
                raise DomainError("inference_profile_mismatch")
            ids = {c.id for c in opaque}
            if (
                result.selected_id not in ids
                or set(result.probabilities) != ids
                or result.calls != stage
            ):
                raise DomainError("invalid_inference_response")
            if any(not math.isfinite(v) or not 0 <= v <= 1 for v in result.probabilities.values()):
                raise DomainError("invalid_inference_response")
            if not math.isclose(sum(result.probabilities.values()), 1, abs_tol=0.02):
                raise DomainError("invalid_inference_response")
            ranked = sorted(result.probabilities.values(), reverse=True)
            score = result.probabilities[result.selected_id]
            if (
                result.selected_id == "clarify"
                or score < self.confidence
                or score - ranked[1] < self.margin
            ):
                return "clarify"
            return result.selected_id

        initial_context = {}
        if len(candidates) == 1 and candidates[0].plan is not None:
            # A server-validated action description is data, not model authority.
            initial_context["feasible_action"] = anonymized(candidates[0].choice.description)[:200]
        references = self.context.get(actor)
        if references and re.search(r"아까|앞에서|그\s*목록", text):
            initial_context["recent_playlist"] = anonymized(references[0].name)
        first = await choose(
            1,
            [Choice(group, INTENTS[group]), Choice("non_command", INTENTS["non_command"])],
            initial_context,
        )
        if first in {"clarify", "non_command"} or first != group:
            return None
        if len(candidates) == 1 and candidates[0].plan is not None:
            authorize(candidates[0].plan, actor, request_policy())
            return complete(candidates[0].plan, 1)
        # Permission denial ends the request before any second question.
        permission_action = (
            candidates[0].plan.action if candidates[0].plan else candidates[0].unresolved_action
        )
        if permission_action is None:
            return None
        authorize(
            self._plan(actor, request_id, snapshot, permission_action, {}),
            actor,
            request_policy(),
        )
        second = await choose(2, [c.choice for c in candidates], {})
        if second == "clarify":
            return None
        selected = next(c for c in candidates if c.choice.id == second)
        if selected.plan is not None:
            return complete(selected.plan, 2)
        references = self.context.get(actor)
        if selected.unresolved_action != Action.PLAYLIST_ADD or not references:
            return None
        context_plans: list[CandidatePlan] = []
        for reference in references:
            matches = [p for p in snapshot["playlists"] if p["id"] == reference.playlist_id]
            if matches:
                context_plans.append(
                    CandidatePlan(
                        Choice(
                            "r" + str(len(context_plans) + 1),
                            "선행 발화에서 참조한 " + reference.name + " 목록에 현재곡만 추가",
                        ),
                        self._plan(
                            actor,
                            request_id,
                            snapshot,
                            selected.unresolved_action,
                            {
                                "playlist_id": reference.playlist_id,
                                "track_ids": [snapshot["session"]["current_track_id"]],
                            },
                        ),
                    )
                )
        if not context_plans:
            return None
        third = await choose(
            3,
            [c.choice for c in context_plans],
            {"recent_playlist": anonymized(references[0].name)},
        )
        if third == "clarify":
            return None
        final = next(c.plan for c in context_plans if c.choice.id == third)
        if final is not None and final.action != selected.unresolved_action:
            raise DomainError("inference_action_conflict")
        return complete(final, 3) if final is not None else None
