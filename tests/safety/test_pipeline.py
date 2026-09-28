from dataclasses import replace

import pytest

from changgeun.application.executor import Executor
from changgeun.domain.models import Action, ActionPlan, Actor, DomainError, Policy
from changgeun.nlp.pipeline import ContextCache, Pipeline, Selection, korean_number
from changgeun.storage.database import Database


class Port:
    provider, profile_id, config_hash = "mock", "test-mock", "a" * 64

    def __init__(self, answers):
        self.answers, self.requests = list(answers), []

    async def choose(self, payload, timeout):
        self.requests.append(payload)
        choice = self.answers.pop(0)
        ids = [c["id"] for c in payload["candidates"]]
        return Selection(
            choice,
            {k: 0.99 if k == choice else 0.01 / (len(ids) - 1) for k in ids},
            payload["stage_index"],
        )


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "db.sqlite")
    db.ensure_guild("1")
    actor = Actor("1", "999999999999999999", frozenset({"dj"}), "text", "voice", "voice")
    policy = Policy(frozenset({"1"}), frozenset({"dj"}), frozenset({"text"}), frozenset({"voice"}))
    executor = Executor(db, policy)
    tracks = []
    for i in range(3):
        tracks.append(
            executor.execute(
                ActionPlan(
                    f"t{i}",
                    "1",
                    actor.user_id,
                    Action.CATALOG_REGISTER,
                    {"source_type": "approved_audio", "external_id": str(i), "title": f"곡 {i}"},
                ),
                actor,
            )["track_id"]
        )
    executor.execute(
        ActionPlan(
            "enqueue", "1", actor.user_id, Action.QUEUE_ENQUEUE, {"track_ids": tracks}, {"queue": 0}
        ),
        actor,
    )
    playlists = []
    for i, name in enumerate(["새벽 노동요", "새벽 작업곡"]):
        playlist = executor.execute(
            ActionPlan(f"p{i}", "1", actor.user_id, Action.PLAYLIST_CREATE, {"name": name}), actor
        )["playlist_id"]
        executor.execute(
            ActionPlan(
                f"add{i}",
                "1",
                actor.user_id,
                Action.PLAYLIST_ADD,
                {"playlist_id": playlist, "track_ids": tracks},
                {playlist: 0},
            ),
            actor,
        )
        playlists.append(playlist)
    return db, actor, policy, executor, tracks, playlists


def pipeline(env, answers):
    db, actor, policy, *_ = env
    port = Port(answers)
    return Pipeline(db, policy, port, confidence=0.7, margin=0.1, prompt_version="mock-v1"), port


@pytest.mark.parametrize("text,value", [("세", 3), ("스무", 20), ("100", 100), ("9999", None)])
def test_contextual_korean_numbers(text, value):
    assert korean_number(text) == value


@pytest.mark.asyncio
async def test_exact_queue_target_exits_after_one_dispatch_but_requires_confirmation(env):
    route, port = pipeline(env, ["queue_edit"])
    plan = await route.interpret("대기열 세 번째 곡 빼줘", env[1])
    assert plan.action == Action.QUEUE_REMOVE
    assert plan.arguments["entry_id"] == route._snapshot("1")["queue"][2]["id"]
    assert len(port.requests) == 1
    with pytest.raises(DomainError, match="confirmation_required"):
        env[3].execute(plan, env[1])


@pytest.mark.asyncio
async def test_single_action_negation_moves_instead_of_removes(env):
    route, port = pipeline(env, ["queue_edit"])
    plan = await route.interpret("대기열 세 번째 곡 지우지 말고 맨 뒤로 보내", env[1])
    assert plan.action == Action.QUEUE_MOVE
    assert len(port.requests) == 1


@pytest.mark.asyncio
async def test_ambiguous_candidate_requires_second_stage(env):
    route, port = pipeline(env, ["play_request", "c2"])
    # Two names occur explicitly, so a closed action selection is needed.
    plan = await route.interpret("새벽 노동요 혹은 새벽 작업곡 재생해줘", env[1])
    assert plan.action == Action.PLAYLIST_PLAY
    assert len(port.requests) == 2
    assert port.requests[0]["request_id"] == port.requests[1]["request_id"]
    metrics = route.metrics.snapshot()
    assert metrics["outcomes"] == {"selected": 1}
    assert (
        sum(value for key, value in metrics["durations_ms"].items() if key.startswith("decision:"))
        == 2
    )
    assert (
        sum(value for key, value in metrics["durations_ms"].items() if key.startswith("request:"))
        == 1
    )


@pytest.mark.asyncio
async def test_valid_context_only_enters_third_stage_and_keeps_action(env):
    db, actor, _, _, tracks, playlists = env
    with db.transaction() as conn:
        conn.execute(
            "UPDATE sessions SET current_entry_id='current',current_track_id=? WHERE guild_id='1'",
            (tracks[0],),
        )
    route, port = pipeline(env, ["playlist_edit", "c1", "r1"])
    route.context.remember(actor, playlists[0], "새벽 노동요")
    plan = await route.interpret("지금 틀지 말고 아까 그 목록에 지금 곡만 넣어줘", actor)
    assert plan.action == Action.PLAYLIST_ADD
    assert plan.arguments["track_ids"] == [tracks[0]]
    assert len(port.requests) == 3
    assert port.requests[0]["context"] == {"recent_playlist": "새벽 노동요"}
    assert {p["task"] for p in port.requests} == {
        "classify_intent",
        "select_action",
        "resolve_context",
    }


@pytest.mark.asyncio
async def test_no_context_and_negation_or_compound_never_dispatch(env):
    for text in ["곡을 지우지 마", "목록을 삭제하고 재생해", "좋은 노래야", "x" * 501]:
        route, port = pipeline(env, [])
        if len(text) > 500:
            with pytest.raises(DomainError, match="input_too_large"):
                await route.interpret(text, env[1])
        else:
            assert await route.interpret(text, env[1]) is None
        assert not port.requests


@pytest.mark.asyncio
async def test_clarify_ends_without_second_question(env):
    route, port = pipeline(env, ["clarify"])
    assert await route.interpret("대기열 세 번째 곡 빼줘", env[1]) is None
    assert len(port.requests) == 1


@pytest.mark.asyncio
async def test_non_dj_denial_never_enters_paid_stage(env):
    route, port = pipeline(env, ["play_request"])
    with pytest.raises(DomainError, match="dj_required"):
        await route.interpret(
            "새벽 노동요 혹은 새벽 작업곡 재생해줘", replace(env[1], role_ids=frozenset())
        )
    assert len(port.requests) == 0


def test_context_never_crosses_actor_channel_guild_or_ttl(env):
    actor = env[1]
    clock = [0]
    cache = ContextCache(clock=lambda: clock[0])
    cache.remember(actor, "playlist", "목록")
    for altered in [
        replace(actor, user_id="other"),
        replace(actor, text_channel_id="other"),
        replace(actor, guild_id="other"),
    ]:
        assert cache.get(altered) == []
    clock[0] = 120
    assert cache.get(actor) == []


def test_playlist_ranking_prefers_specific_name_and_never_hides_overflow(env):
    route, _ = pipeline(env, [])
    with env[0].transaction() as conn:
        for index, name in enumerate("가나다라마바사아자차카타"):
            conn.execute(
                "INSERT INTO playlists(guild_id,id,name,normalized_name) VALUES(?,?,?,?)",
                ("1", f"extra-{index}", name, name),
            )
    snapshot = route._snapshot("1")
    group, candidates = route._candidates("새벽 노동요 목록 재생해줘", env[1], "request", snapshot)
    assert group == "play_request"
    assert candidates[0].plan.arguments["playlist_id"] == env[5][0]
    group, candidates = route._candidates(
        "가나다라마바사아자차카타 목록 재생해줘", env[1], "request", snapshot
    )
    assert group == "clarify" and candidates == []


@pytest.mark.asyncio
async def test_followup_stage_reads_only_session_marker(env):
    route, _ = pipeline(env, ["play_request", "c1"])
    reads = []
    original = route._snapshot

    def snapshot(guild):
        reads.append("full")
        return original(guild)

    route._snapshot = snapshot
    plan = await route.interpret("새벽 노동요 혹은 새벽 작업곡 재생해줘", env[1])
    assert plan is not None
    assert reads == ["full"]


@pytest.mark.asyncio
async def test_profile_mutation_during_request_is_rejected(env):
    route, port = pipeline(env, ["queue_edit"])
    original = port.choose

    async def changed(payload, timeout):
        result = await original(payload, timeout)
        port.provider = "jev-api"
        return result

    port.choose = changed
    with pytest.raises(DomainError, match="inference_profile_mismatch"):
        await route.interpret("대기열 세 번째 곡 빼줘", env[1])


@pytest.mark.asyncio
async def test_late_generation_and_deadline_never_execute(env):
    route, port = pipeline(env, ["queue_edit"])
    plan = await route.interpret("대기열 세 번째 곡 빼줘", env[1])
    with env[0].transaction() as conn:
        conn.execute("UPDATE sessions SET generation=generation+1 WHERE guild_id='1'")
    with pytest.raises(DomainError, match="generation_conflict"):
        env[3].execute(plan, env[1])
    with pytest.raises(DomainError, match="execution_deadline_expired"):
        env[3].execute(replace(plan, expires_at=1), env[1])


@pytest.mark.asyncio
async def test_cooldown_and_minimal_external_payload(env):
    route, port = pipeline(env, ["queue_edit"])
    await route.interpret("대기열 세 번째 곡 빼줘", env[1])
    with pytest.raises(DomainError, match="user_cooldown"):
        await route.interpret("대기열 세 번째 곡 빼줘", env[1])
    import json

    wire = json.dumps(port.requests)
    assert env[1].user_id not in wire
    assert env[4][0] not in wire
    assert env[5][0] not in wire


@pytest.mark.parametrize(
    "text",
    [
        "대기열을 비우고 다음 곡으로 넘겨줘",
        "대기열을 지우고 음성채널에서 나가줘",
        "목록을 만들고 재생해줘",
        "음성채널 입장하고 목록 재생해줘",
        "정지 명령이 무엇이야",
        "일시정지 사용법 알려줘",
    ],
)
@pytest.mark.asyncio
async def test_compound_or_explanation_never_selects_one_mutation_or_dispatches(env, text):
    route, port = pipeline(env, [])
    assert await route.interpret(text, env[1]) is None
    assert port.requests == []


@pytest.mark.asyncio
async def test_first_stage_uses_feasible_intent_and_keeps_noncommand_clarification(env):
    route, port = pipeline(env, ["non_command"])
    assert await route.interpret("새벽 노동요 목록 틀어줘", env[1]) is None
    candidates = {item["id"] for item in port.requests[0]["candidates"]}
    assert candidates == {"play_request", "non_command", "clarify"}
    assert len(port.requests) == 1


@pytest.mark.asyncio
async def test_classifier_sees_validated_action_data_without_discord_identifiers(env):
    route, port = pipeline(env, ["play_request"])
    plan = await route.interpret("새벽 노동요 목록 틀어줘", env[1])
    assert plan.action == Action.PLAYLIST_PLAY
    context = port.requests[0]["context"]
    assert context["feasible_action"] == "등록된 새벽 노동요 목록 재생"
    assert not any(key in context for key in ("guild_id", "user_id", "role_ids", "channel_id"))


@pytest.mark.parametrize(
    "url",
    [
        "youtube.com/watch?v=GD_rjpO7CIQ",
        "https://www.youtube.com/watch?v=GD_rjpO7CIQ",
        "www.youtube.com/watch?v=GD_rjpO7CIQ",
        "m.youtube.com/watch?v=GD_rjpO7CIQ",
        "youtu.be/GD_rjpO7CIQ",
        "youtube.com/shorts/GD_rjpO7CIQ",
    ],
)
@pytest.mark.asyncio
async def test_explicit_youtube_link_preserves_id_and_precedes_named_playlist(env, url):
    route, port = pipeline(env, ["play_request"])
    selected = await route.interpret(f"새벽 노동요 대신 {url} 틀어줘", env[1])
    assert selected.action == Action.TRACK_PLAY
    assert selected.arguments == {"track_id": "youtube:GD_rjpO7CIQ", "channel_id": "voice"}
    assert len(port.requests) == 1


@pytest.mark.parametrize(
    "text",
    [
        "youtube.com/watch?v=GD_rjpO7CIQ 틀지 말아줘",
        "새벽 노동요 youtube.com/watch?v=GD_rjpO7CIQ https://youtu.be/ABCDEFGHIJK 틀어줘",
        "https://example.com/youtube.com/watch?v=GD_rjpO7CIQ 틀어줘",
        "user@youtube.com/watch?v=GD_rjpO7CIQ 틀어줘",
    ],
)
@pytest.mark.asyncio
async def test_negated_ambiguous_or_embedded_links_never_dispatch(env, text):
    route, port = pipeline(env, [])
    assert await route.interpret(text, env[1]) is None
    assert port.requests == []
