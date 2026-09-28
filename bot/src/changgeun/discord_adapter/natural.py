"""Compile closed natural command IDs into trusted application operations."""

from __future__ import annotations

import json
import random
import re
import time
import unicodedata
from dataclasses import replace
from typing import TYPE_CHECKING, Any

import discord

from changgeun.application import undo
from changgeun.application.generation import Rules, select
from changgeun.application.transfer import parse_export
from changgeun.application.watch import source_row
from changgeun.discord_adapter import watch as watch_commands
from changgeun.discord_adapter.mention import MentionEntry
from changgeun.domain.models import Action, Actor, DomainError, authorize, digest
from changgeun.nlp.command_registry import CommandDecision
from changgeun.nlp.pipeline import korean_number
from changgeun.providers.media import Metadata, youtube_id

if TYPE_CHECKING:
    from changgeun.discord_adapter.client import ChangGeunClient


URL = re.compile(
    r"(?<![\w@./:-])(?:https?://[^\s<>]+|(?:(?:www\.|m\.)?youtube\.com|youtu\.be)/[^\s<>]+)",
    re.IGNORECASE,
)
NUMBER = re.compile(
    r"(\d{1,3}|첫|한|하나|두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)\s*(?:번째|번)"
)
QUOTED = re.compile(r"[\"“‘']([^\"”’']{1,100})[\"”’']")


def _numbers(text: str) -> list[int]:
    result = [korean_number(m[1]) for m in NUMBER.finditer(text)]
    return [n for n in result if n is not None]


def _text_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _name(text: str, *, marker: str = "목록") -> str:
    quoted = QUOTED.search(text)
    if quoted:
        return quoted[1]
    match = re.search(r"([\w가-힣-]{1,100})\s*(?:이라는|라는|란)?\s*(?:빈\s*)?" + marker, text)
    if match:
        value = re.sub(r"(?:이라는|라는|란)$", "", match[1])
        value = value.strip()
        if value and value not in {"재생", "저장", "내", "곡", "빈"}:
            return value
    raise DomainError("natural_missing_argument")


def _playlist(client: ChangGeunClient, actor: Actor, text: str) -> tuple[str, str]:
    # An excluded name is never an execution target, even when it occurs first.
    text = text.rsplit("말고", 1)[-1]
    with client.db.connect() as conn:
        rows = conn.execute(
            "SELECT id,name FROM playlists WHERE guild_id=? AND deleted_at IS NULL",
            (actor.guild_id,),
        ).fetchall()
    found = [
        (len(row["name"]), str(row["id"]), str(row["name"]))
        for row in rows
        if _text_key(row["name"]) in _text_key(text)
    ]
    found.sort(key=lambda item: -item[0])
    if not found or any(
        _text_key(item[2]) not in _text_key(found[0][2]) for item in found[1:]
    ):
        raise DomainError("natural_missing_argument")
    return found[0][1], found[0][2]


def _track(client: ChangGeunClient, actor: Actor, text: str) -> str:
    text = text.rsplit("말고", 1)[-1]
    with client.db.connect() as conn:
        rows = conn.execute(
            "SELECT id,title,annotations_json FROM tracks WHERE guild_id=?", (actor.guild_id,)
        ).fetchall()
    found: list[tuple[int, str, str]] = []
    for row in rows:
        names = [row["title"], *json.loads(row["annotations_json"]).get("aliases", [])]
        matches = [
            len(name)
            for name in names
            if isinstance(name, str) and _text_key(name) in _text_key(text)
        ]
        if matches:
            found.append((max(matches), str(row["id"]), str(row["title"])))
    found.sort(reverse=True)
    if not found or any(
        _text_key(item[2]) not in _text_key(found[0][2]) for item in found[1:]
    ):
        raise DomainError("natural_missing_argument")
    return found[0][1]


def _new_name(text: str, verb: str) -> str:
    quoted = QUOTED.findall(text)
    if len(quoted) >= 2:
        return str(quoted[-1])
    match = re.search(r"이름을\s*([^\s]{1,100}?)(?:으로|로)?\s*(?:바꿔|변경|해)", text)
    if match:
        return str(match[1])
    match = re.search(r"(?:을|를)\s*(.{1,100}?)\s*(?:이라는|라는)?\s*목록으로", text)
    if match:
        return str(match[1]).strip()
    match = re.search(r"([\w가-힣-]{1,100})\s*목록으로\s*(?:" + verb + ")", text)
    if match:
        return match[1].strip()
    raise DomainError("natural_missing_argument")


def _query(text: str, external: bool = False) -> str:
    value = (
        re.sub(r"^.*?(?:유튜브에서|등록된\s*곡에서|카탈로그에서|검색어\s*)", "", text)
        if external or "에서" in text
        else text
    )
    value = re.sub(r"(?:찾아|검색|보여|틀어|재생).*?$", "", value).strip(" ,.?을를")
    if not value or len(value) > 100:
        raise DomainError("natural_missing_argument")
    return value


class AdminOpen(discord.ui.View):
    """Only a fresh component interaction can show private admin content."""

    def __init__(
        self, client: ChangGeunClient, actor: Actor, command: str, channel: str | None, request: str
    ) -> None:
        super().__init__(timeout=60)
        self.client, self.actor, self.command, self.channel, self.request = (
            client,
            actor,
            command,
            channel,
            request,
        )
        self.deadline = time.monotonic() + 60
        self.used = False

    @discord.ui.button(label="관리 결과 보기", style=discord.ButtonStyle.secondary)
    async def open_result(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if (
            self.used
            or time.monotonic() >= self.deadline
            or (str(interaction.user.id), str(interaction.guild_id), str(interaction.channel_id))
            != (self.actor.user_id, self.actor.guild_id, self.actor.text_channel_id)
        ):
            await interaction.response.send_message("요청자만 다시 확인할 수 있어.", ephemeral=True)
            return
        try:
            with self.client.db.connect() as conn:
                source = source_row(conn, self.actor.guild_id, self.request)
            if source and source["origin"] == "prefix":
                self.client.bind_prefix_component(self.actor, self.request, str(interaction.id))
            await watch_commands.admin(self.client, interaction)
        except DomainError:
            await interaction.response.send_message(
                "최신 관리자 권한을 확인할 수 없어.", ephemeral=True
            )
            return
        self.used = True
        if self.command == "usage":
            await watch_commands.show_usage(self.client, interaction)
        else:
            await watch_commands.invoke(
                self.client, interaction, self.command, self.channel, request=self.request
            )
        self.stop()


class PrivateReadOpen(discord.ui.View):
    def __init__(
        self, client: ChangGeunClient, actor: Actor, action: Action,
        request: str, result_hash: str,
    ) -> None:
        super().__init__(timeout=60)
        self.client, self.actor, self.action = client, actor, action
        self.request, self.result_hash = request, result_hash
        self.deadline = time.monotonic() + 60

    @discord.ui.button(label="개인 결과 보기", style=discord.ButtonStyle.secondary)
    async def open_result(
        self, interaction: discord.Interaction, button: discord.ui.Button[Any]
    ) -> None:
        if time.monotonic() >= self.deadline or (
            str(interaction.user.id), str(interaction.guild_id), str(interaction.channel_id)
        ) != (self.actor.user_id, self.actor.guild_id, self.actor.text_channel_id):
            await interaction.response.send_message("요청자만 결과를 열 수 있어.", ephemeral=True)
            return
        try:
            with self.client.db.connect() as conn:
                source = source_row(conn, self.actor.guild_id, self.request)
            prefix = bool(source and source["origin"] == "prefix")
            if prefix:
                self.client.bind_prefix_component(self.actor, self.request, str(interaction.id))
            actor = await self.client.fresh_actor(
                interaction, **({"request_id": str(interaction.id)} if prefix else {})
            )
            plan = self.client.make_plan(
                actor, str(interaction.id) + ".read", self.action, {}, origin="button"
            )
            result = self.client.executor.execute(plan, actor)
            if digest(result) != self.result_hash:
                raise DomainError("version_conflict")
            from changgeun.discord_adapter.client import PageView

            page = PageView(
                self.client, actor, self.action, {}, result,
                source_request=self.request if prefix else None,
            )
            await interaction.response.send_message(page.render(), view=page, ephemeral=True)
        except DomainError:
            await interaction.response.send_message(
                "권한이나 목록이 바뀌었어. 다시 요청해줘.", ephemeral=True
            )


async def dispatch(
    client: ChangGeunClient,
    entry: discord.Interaction | MentionEntry,
    actor: Actor,
    decision: CommandDecision,
    text: str,
) -> None:
    """Use only original input spans and current database/Discord state for slots."""
    identifier = decision.command.identifier
    request = (
        entry.request_id if isinstance(entry, MentionEntry) and entry.request_id else str(entry.id)
    )
    if 40 <= int(identifier[1:]) <= 47:
        if not actor.manage_guild:
            raise DomainError("administrator_required")
        channel_match = re.search(r"<#(\d{17,20})>", text)
        channel = channel_match[1] if channel_match else None
        if channel is None and identifier in {"C40", "C41", "C45"}:
            plain = re.search(r"#([\w가-힣-]{1,100})", text)
            if plain is not None:
                matches = [
                    str(item.id) for item in entry.guild.text_channels
                    if item.name == plain[1]
                ] if entry.guild is not None else []
                if len(matches) != 1:
                    raise DomainError("natural_missing_argument")
                channel = matches[0]
        actions = {
            "C40": "add",
            "C41": "remove",
            "C42": "list",
            "C43": "enable",
            "C44": "disable",
            "C45": "inspect",
            "C46": "history",
            "C47": "usage",
        }
        await entry.followup.send(
            "관리 요청을 확인했어. 요청자만 결과를 열 수 있어.",
            view=AdminOpen(client, actor, actions[identifier], channel, request),
            ephemeral=True,
        )
        return
    if identifier == "C38":
        from changgeun.discord_adapter.client import help_text

        state = client.watch.state(actor.guild_id)
        await entry.followup.send(
            help_text(
                actor,
                client.config.policy,
                youtube_audio=client.config.youtube_audio_enabled,
                prefix_enabled=client.config.prefix.enabled,
                watched_here=bool(
                    state["enabled"]
                    and actor.text_channel_id in client.watch.channels(actor.guild_id)
                ),
            ),
            ephemeral=True,
        )
        return
    if identifier == "C31":
        await client.current_status(entry)
        return
    action: Action | None = None
    if identifier in {"C33", "C36"}:
        action = Action.PROPOSAL_LIST if identifier == "C33" else Action.HISTORY_LIST
        plan = replace(
            client.make_plan(actor, request, action, {}),
            origin="natural_language", inference=decision.trace,
            expires_at=decision.expires_at,
        )
        result = client.executor.execute(plan, actor)
        await entry.followup.send(
            "조회했어. 요청자만 결과를 열 수 있어.",
            view=PrivateReadOpen(client, actor, action, request, digest(result)),
            ephemeral=True,
        )
        return
    args: dict[str, Any] = {}
    playlist: str | None = None
    if identifier in {"C03", "C04", "C05", "C06", "C11", "C12", "C13", "C23", "C32"}:
        if identifier != "C23" or "목록" in text or "플레이리스트" in text:
            try:
                search = text.split("이름", 1)[0] if identifier == "C03" else text
                if identifier == "C05":
                    source = re.search(r"^(.+?)(?:목록)?(?:을|를)\s+.+?목록으로\s*복사", text)
                    if source:
                        search = source[1]
                playlist, _ = _playlist(client, actor, search)
            except DomainError:
                if identifier != "C23":
                    raise
    if identifier == "C01":
        action = Action.PLAYLIST_LIST
    elif identifier == "C02":
        action, args = Action.PLAYLIST_CREATE, {"name": _name(text)}
    elif identifier == "C03":
        action, args = (
            Action.PLAYLIST_RENAME,
            {"playlist_id": playlist, "name": _new_name(text, "바꿔|변경")},
        )
    elif identifier == "C04":
        action, args = Action.PLAYLIST_DELETE, {"playlist_id": playlist}
    elif identifier == "C05":
        action, args = (
            Action.PLAYLIST_COPY,
            {"playlist_id": playlist, "name": _new_name(text, "복사")},
        )
    elif identifier == "C06":
        action, args = Action.PLAYLIST_EXPORT, {"playlist_id": playlist}
    elif identifier == "C07":
        match_name = re.search(r"(?:곡\s*\d+\s*개로|\d+\s*곡으로|로)\s*([\w가-힣-]+)\s*목록", text)
        name = match_name[1] if match_name else _name(text)
        count_match = re.search(r"(?:곡\s*(\d{1,3})\s*개|(\d{1,3})\s*곡)", text)
        tags = re.findall(r"([^\s,]+)\s*태그", text)
        excluded = re.findall(r"제외태그\s*([^\s,]+)", text)
        tags = [tag for tag in tags if tag != "제외"]
        creator = re.search(r"제작자(?:는|가)?\s*([^\s,]+)", text)
        recent = re.search(r"최근(?:제외)?\s*(\d{1,3})\s*일", text)
        maximum = re.search(r"최대\s*(\d{1,5})\s*초", text)
        seed = re.search(r"시드\s*(\d{1,10})", text)
        authorize(
            client.make_plan(actor, request, Action.PLAYLIST_GENERATE, {}),
            actor,
            client.request_policy(actor, request),
        )
        rules = Rules(
            tuple(tags),
            tuple(excluded),
            creator[1] if creator else None,
            int(count_match[1] or count_match[2]) if count_match else 20,
            int(maximum[1]) if maximum else None,
            int(recent[1]) if recent else 7,
            int(seed[1]) if seed else 0,
        )
        reference = time.time()
        with client.db.connect() as conn:
            selected = select(conn, actor.guild_id, rules, reference)
        if not selected.track_ids:
            raise DomainError("generation_no_matches")
        action = Action.PLAYLIST_GENERATE
        args = {
            "name": name,
            "rules": rules.serialize(),
            "track_ids": selected.track_ids,
            "snapshot_hash": selected.snapshot_hash,
            "reference_time": reference,
        }
    elif identifier == "C08":
        name_match = re.search(r"목록을\s*([^\s]+?)(?:으로|로)\s*가져", text)
        name = name_match[1] if name_match else _name(text)
        authorize(
            client.make_plan(actor, request, Action.PLAYLIST_IMPORT, {}),
            actor,
            client.request_policy(actor, request),
        )
        urls = URL.findall(text)
        attachments = entry.message.attachments if isinstance(entry, MentionEntry) else []
        if len(urls) + len(attachments) != 1:
            raise DomainError("natural_missing_argument")
        complete, unavailable, metadata = True, 0, {}
        if attachments:
            if attachments[0].size > 524288:
                raise DomainError("import_file_too_large")
            references = parse_export(await attachments[0].read())
        else:
            snapshot = await client.youtube_api().playlist(urls[0])
            complete, unavailable = snapshot.complete, snapshot.unavailable_count
            metadata = {
                item.external_id: {
                    "source_author": item.source_author,
                    "duration_seconds": item.duration_seconds,
                }
                for item in snapshot.items
            }
            references = [
                {"source_type": "youtube", "external_id": item.external_id, "title": item.title}
                for item in snapshot.items
            ]
        action = Action.PLAYLIST_IMPORT
        args = {
            "name": name,
            "references": references,
            "complete": complete,
            "unavailable_count": unavailable,
            "accept_partial": bool(re.search("부분.*허용", text)),
            "allow_duplicates": bool(re.search("중복.*허용", text)),
            "replace": bool(re.search("교체|덮어", text)),
            "source_metadata": metadata,
        }
        if "기존" in text or args["replace"]:
            existing, _ = _playlist(client, actor, text.split("에 가져", 1)[0])
            args["playlist_id"] = existing
    elif identifier == "C09":
        urls = URL.findall(text)
        if len(urls) != 1:
            raise DomainError("natural_missing_argument")
        authorize(
            client.make_plan(actor, request, Action.CATALOG_REGISTER, {}),
            actor,
            client.request_policy(actor, request),
        )
        metadata_item: Metadata | None
        if client.config.youtube_key_file is None:
            from changgeun.providers.media import YouTubeMetadata

            metadata_item = await YouTubeMetadata().fetch(urls[0])
        else:
            video = youtube_id(urls[0])
            metadata_item = (await client.youtube_api().videos([video])).get(video)
            if metadata_item is None:
                raise DomainError("youtube_metadata_failed")
        action = Action.CATALOG_REGISTER
        args = {
            "source_type": "youtube",
            "external_id": metadata_item.external_id,
            "title": metadata_item.title,
            "metadata": {
                "source_author": metadata_item.source_author,
                "duration_seconds": metadata_item.duration_seconds,
            },
        }
    elif identifier == "C10":
        track = _track(client, actor, text)
        aliases = [
            re.sub(r"(?:으로|로)$", "", item)
            for item in re.findall(r"(?:별칭|별명)(?:을|를|은|는)?\s*([^\s,]+)", text)
        ]
        tags = [
            re.sub(r"(?:으로|로)$", "", item)
            for item in re.findall(r"태그(?:을|를|은|는)?\s*([^\s,]+)", text)
        ]
        if not aliases and not tags and "제작자" not in text:
            raise DomainError("natural_missing_argument")
        with client.db.connect() as conn:
            row = conn.execute(
                "SELECT annotations_json FROM tracks WHERE guild_id=? AND id=?",
                (actor.guild_id, track),
            ).fetchone()
        previous = json.loads(row[0]) if row else {}
        prior_aliases, prior_tags = previous.get("aliases", []), previous.get("tags", [])
        action, args = (
            Action.CATALOG_ANNOTATE,
            {"track_id": track, "aliases": aliases or prior_aliases, "tags": tags or prior_tags},
        )
        if "추가" in text:
            args["aliases"] = list(dict.fromkeys(prior_aliases + aliases))
            args["tags"] = list(dict.fromkeys(prior_tags + tags))
        creator = re.search(r"제작자(?:를|는|를)?\s*([^\s,]+)", text)
        if creator:
            args["creator"] = creator[1]
    elif identifier == "C11":
        chosen_track: str | None = (
            _track(client, actor, text.split("목록에", 1)[-1])
            if not re.search(r"현재곡|지금\s*곡", text)
            else None
        )
        if chosen_track is None:
            with client.db.connect() as conn:
                row = conn.execute(
                    "SELECT current_track_id FROM sessions WHERE guild_id=?", (actor.guild_id,)
                ).fetchone()
                chosen_track = row[0] if row else None
        if not chosen_track:
            raise DomainError("natural_missing_argument")
        action, args = (
            Action.PLAYLIST_ADD,
            {
                "playlist_id": playlist,
                "track_ids": [chosen_track],
                "allow_duplicates": bool(re.search("중복.*허용", text)),
            },
        )
    elif identifier in {"C12", "C13", "C19", "C20"}:
        numbers = _numbers(text)
        moving = identifier in {"C13", "C20"}
        edge = re.search(r"맨\s*(앞|뒤|끝)", text) if moving else None
        if len(numbers) < (1 if edge else 2 if moving else 1):
            raise DomainError("natural_missing_argument")
        with client.db.connect() as conn:
            if playlist:
                rows = conn.execute(
                    "SELECT id FROM playlist_entries WHERE guild_id=? "
                    "AND playlist_id=? ORDER BY position",
                    (actor.guild_id, playlist),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id FROM queue_entries WHERE guild_id=? ORDER BY position",
                    (actor.guild_id,),
                ).fetchall()
        destination = (1 if edge[1] == "앞" else len(rows)) if edge else (
            numbers[1] if moving else None
        )
        if not 1 <= numbers[0] <= len(rows) or (
            destination is not None and not 1 <= destination <= len(rows)
        ):
            raise DomainError("entry_not_found")
        args = {"entry_id": rows[numbers[0] - 1][0]}
        if playlist:
            args["playlist_id"] = playlist
        if moving and destination is not None:
            args["position"] = destination - 1
        action = {
            "C12": Action.PLAYLIST_REMOVE,
            "C13": Action.PLAYLIST_MOVE,
            "C19": Action.QUEUE_REMOVE,
            "C20": Action.QUEUE_MOVE,
        }[identifier]
    elif identifier in {"C14", "C15"}:
        query = _query(text, identifier == "C15")
        if identifier == "C14":
            action, args = Action.CATALOG_SEARCH, {"query": query}
        else:
            probe = client.make_plan(actor, request, Action.CATALOG_SEARCH, {"query": query})
            authorize(probe, actor, client.request_policy(actor, request))
            results = await client.youtube_api().search(query)
            from changgeun.discord_adapter.client import safe

            await entry.followup.send(
                "\n".join(
                    safe(item.title) + "\nhttps://www.youtube.com/watch?v=" + item.external_id
                    for item in results
                )[:1900]
                or "찾은 곡이 없어.",
                ephemeral=True,
            )
            return
    elif identifier == "C16":
        action = Action.QUEUE_SHOW
    elif identifier == "C17":
        action = Action.QUEUE_CLEAR
    elif identifier == "C18":
        match_name = re.search(r"대기열을\s*([\w가-힣-]+)\s*목록으로", text)
        action, args = (
            Action.QUEUE_SAVE,
            {
                "name": match_name[1] if match_name else _name(text),
                "include_current": bool(re.search("현재곡.*포함", text)),
            },
        )
    elif identifier == "C21":
        mention = re.search(r"<#(\d{17,20})>", text)
        channel = mention[1] if mention else actor.voice_channel_id
        if mention is None and entry.guild is not None:
            named = [
                str(c.id)
                for c in entry.guild.voice_channels
                if c.name in text and str(c.id) in client.config.policy.voice_channel_ids
            ]
            if len(named) == 1:
                channel = named[0]
            elif len(named) > 1:
                raise DomainError("natural_missing_argument")
        if not channel:
            raise DomainError("same_voice_required")
        action, args = (
            (
                Action.VOICE_MOVE
                if actor.bot_voice_channel_id and actor.bot_voice_channel_id != channel
                else Action.VOICE_JOIN
            ),
            {"channel_id": channel},
        )
    elif identifier == "C22":
        action = Action.VOICE_LEAVE
    elif identifier == "C23":
        target = actor.bot_voice_channel_id or actor.voice_channel_id
        if target is None:
            raise DomainError("same_voice_required")
        urls = URL.findall(text)
        if len(urls) == 1:
            action, args = (
                Action.TRACK_PLAY,
                {"track_id": "youtube:" + youtube_id(urls[0]), "channel_id": target},
            )
        elif playlist:
            with client.db.connect() as conn:
                rows = conn.execute(
                    "SELECT track_id FROM playlist_entries WHERE guild_id=? "
                    "AND playlist_id=? ORDER BY position",
                    (actor.guild_id, playlist),
                ).fetchall()
            action, args = (
                Action.PLAYLIST_PLAY,
                {
                    "playlist_id": playlist,
                    "track_ids": [row[0] for row in rows],
                    "channel_id": target,
                },
            )
        else:
            try:
                selected_track = _track(client, actor, text)
            except DomainError:
                selected_track = None
            if selected_track is not None:
                action, args = Action.TRACK_PLAY, {"track_id": selected_track, "channel_id": target}
            elif re.search("유튜브에서|검색해서|찾아서", text):
                query = _query(text, True)
                probe = client.make_plan(
                    actor, request, Action.TRACK_PLAY, {"track_id": "pending", "channel_id": target}
                )
                authorize(probe, actor, client.request_policy(actor, request))
                results = [
                    m
                    for m in await client.youtube_api().search(query)
                    if m.duration_seconds is not None and 0 < m.duration_seconds <= 1800
                ]
                if not results:
                    raise DomainError("youtube_unsupported")
                from changgeun.discord_adapter.client import YouTubeSelection

                view = YouTubeSelection(
                    client,
                    actor,
                    [m.external_id for m in results],
                    [m.title for m in results],
                    request,
                    probe.expected_versions["queue"],
                    probe.execution_generation,
                )
                await entry.followup.send(
                    "재생할 영상을 골라줘. 60초 안에 선택할 수 있어.", view=view, ephemeral=True
                )
                return
            else:
                raise DomainError("natural_missing_argument")
    elif identifier in {"C24", "C26", "C27", "C30"}:
        action = {
            "C24": Action.PLAYBACK_PAUSE,
            "C26": Action.PLAYBACK_SKIP,
            "C27": Action.PLAYBACK_STOP,
            "C30": Action.PLAYBACK_SHUFFLE,
        }[identifier]
        if identifier == "C30":
            args = {"seed": random.randrange(2**31)}
    elif identifier == "C25":
        action = Action.PLAYBACK_RESUME
        with client.db.connect() as conn:
            state = conn.execute(
                "SELECT desired_state FROM sessions WHERE guild_id=?", (actor.guild_id,)
            ).fetchone()[0]
        if state != "paused":
            action = Action.PLAYBACK_START
        if actor.bot_voice_channel_id is None:
            if actor.voice_channel_id is None:
                raise DomainError("same_voice_required")
            join = replace(
                client.make_plan(
                    actor,
                    request + ".join",
                    Action.VOICE_JOIN,
                    {"channel_id": actor.voice_channel_id},
                ),
                origin="natural_language",
                inference=decision.trace,
                expires_at=decision.expires_at,
            )
            authorize(join, actor, client.request_policy(actor, request))
            joined = client.executor.execute(join, actor)
            await client.audio.apply(actor.guild_id, join.action, joined)
            actor = await client.fresh_actor(entry)
    elif identifier == "C28":
        match = re.search(r"(?:볼륨|음량).*?(\d{1,3})\s*(?:%|퍼센트)?", text)
        if not match:
            raise DomainError("natural_missing_argument")
        volume = int(match[1])
        if re.search(r"올려|높여|줄여|낮춰", text):
            with client.db.connect() as conn:
                current = conn.execute(
                    "SELECT volume FROM sessions WHERE guild_id=?", (actor.guild_id,)
                ).fetchone()
            if current is None:
                raise DomainError("guild_not_allowed")
            volume = int(current[0]) + volume * (1 if re.search(r"올려|높여", text) else -1)
        if not 0 <= volume <= 100:
            raise DomainError("natural_missing_argument")
        action, args = Action.PLAYBACK_VOLUME, {"percent": volume}
    elif identifier == "C29":
        modes = [
            mode
            for pattern, mode in (
                (r"끄|해제|하지\s*마", "off"),
                (r"한\s*곡|이\s*곡", "one"),
                (r"대기열|전체", "queue"),
            )
            if re.search(pattern, text)
        ]
        if len(modes) != 1:
            raise DomainError("natural_missing_argument")
        action, args = Action.PLAYBACK_REPEAT, {"mode": modes[0]}
    elif identifier == "C32":
        action, args = (
            Action.PROPOSAL_CREATE,
            {"playlist_id": playlist, "track_id": _track(client, actor, text)},
        )
    elif identifier == "C33":
        action = Action.PROPOSAL_LIST
    elif identifier in {"C34", "C35"}:
        numbers = _numbers(text)
        with client.db.connect() as conn:
            rows = conn.execute(
                "SELECT p.id,p.playlist_id FROM proposals p JOIN playlists l "
                "ON l.guild_id=p.guild_id AND l.id=p.playlist_id "
                "WHERE p.guild_id=? AND p.status='pending' AND l.deleted_at IS NULL "
                "ORDER BY p.created_at,p.id",
                (actor.guild_id,),
            ).fetchall()
        if len(numbers) != 1 or not 1 <= numbers[0] <= len(rows):
            raise DomainError("natural_missing_argument")
        row = rows[numbers[0] - 1]
        action, args = (
            (Action.PROPOSAL_APPROVE if identifier == "C34" else Action.PROPOSAL_REJECT),
            {"proposal_id": row["id"]},
        )
    elif identifier == "C36":
        action = Action.HISTORY_LIST
    elif identifier == "C37":
        if re.search(r"(?:내|제가|내가)\s*(?:마지막|최근|한)\s*(?:편집|변경)", text):
            raise DomainError("natural_missing_argument")
        with client.db.connect() as conn:
            undo_actions = sorted(item.value for item in undo.PLAYLIST_EDITS | undo.QUEUE_EDITS)
            marks = ",".join("?" for _ in undo_actions)
            row = conn.execute(
                "SELECT e.id FROM change_events e WHERE e.guild_id=? "
                + f"AND e.action IN ({marks}) "
                + "AND NOT EXISTS(SELECT 1 FROM edit_undos u WHERE u.guild_id=e.guild_id "
                "AND u.event_id=e.id) ORDER BY e.created_at DESC,e.rowid DESC LIMIT 1",
                (actor.guild_id, *undo_actions),
            ).fetchone()
        if row is None:
            raise DomainError("undo_not_found")
        action, args = Action.EDIT_UNDO, {"event_id": row[0]}
    if action is None:
        raise DomainError("action_not_implemented")
    plan = replace(
        client.make_plan(actor, request, action, args),
        origin="natural_language",
        inference=decision.trace,
        expires_at=decision.expires_at,
    )
    if identifier == "C34":
        with client.db.connect() as conn:
            version = conn.execute(
                "SELECT version FROM playlists WHERE guild_id=? AND id=?",
                (actor.guild_id, row["playlist_id"]),
            ).fetchone()
        if version is None:
            raise DomainError("proposal_not_pending")
        plan = replace(plan, expected_versions={row["playlist_id"]: version[0]})
    authorize(plan, actor, client.request_policy(actor, request))
    await client.submit_plan(entry, plan, actor=actor)
