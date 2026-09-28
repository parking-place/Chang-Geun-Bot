from concurrent.futures import ThreadPoolExecutor

import pytest

from changgeun.application.commands import CommandService
from changgeun.domain.models import Actor, Policy
from changgeun.parser.collections import resolve_collection
from changgeun.parser.contracts import CommandDraft, Evidence, ParseError
from changgeun.parser.followup import TypedQuestion, answer_typed
from changgeun.parser.normalizer import InputNormalizer
from changgeun.parser.pending import PendingStore
from changgeun.parser.registry import ArgumentSpec, CommandSpec
from changgeun.parser.validation import DraftValidator
from changgeun.storage.database import Database


def setup(tmp_path):
    db = Database(tmp_path / 'db.sqlite')
    db.ensure_guild('g')
    with db.transaction() as conn:
        conn.execute("INSERT INTO playlists(guild_id,id,name,normalized_name) "
                     "VALUES('g','p','운동','운동')")
    arg = ArgumentSpec('목록', 'string', True, source='collection', collection='playlists')
    spec = CommandSpec('C05', '목록 이름변경', '이름 변경', (arg,), 'dj', 'write')
    invoked = []
    async def handler(_entry, values):
        invoked.append(values)
    service = CommandService({'C05': spec}, {'C05': handler})
    actor = Actor('g', 'u', frozenset({'dj'}), 'text')
    policy = Policy(frozenset({'g'}), frozenset({'dj'}), frozenset(), frozenset())
    snapshot = resolve_collection(spec, arg, actor, policy, db, root_id='r',
                                  pass_id='initial', scope_hash='scope')
    choice = snapshot.selections[0]
    draft = CommandDraft('C05', {'목록': 'p'}, {'목록': Evidence(
        'collection', snapshot_id=snapshot.snapshot_id, selection_id=choice.token)})
    validator = DraftValidator(service, db, policy, {snapshot.snapshot_id: snapshot})
    view = InputNormalizer().normalize('!!창근아 운동 목록 이름변경', invocation='!!창근아')
    args = dict(root_id='r', pass_id='initial', scope_hash='scope', watch_allowed=True)
    return validator, draft, view, actor, args, db, invoked


@pytest.mark.asyncio
async def test_fresh_collection_and_confirmation_gate(tmp_path):
    validator, draft, view, actor, args, _db, invoked = setup(tmp_path)
    checked = validator.validate(draft, view, actor, **args)
    assert checked.requires_confirmation
    with pytest.raises(ParseError, match='confirmation_required'):
        await validator.invoke(checked, None, actor, view, **args,
                               confirmation_consumed=False)
    await validator.invoke(checked, None, actor, view, **args,
                           confirmation_consumed=True)
    assert invoked == [{'목록': 'p'}]


@pytest.mark.asyncio
async def test_stale_collection_and_role_revoke_block_execution(tmp_path):
    validator, draft, view, actor, args, db, invoked = setup(tmp_path)
    checked = validator.validate(draft, view, actor, **args)
    with db.transaction() as conn:
        conn.execute("UPDATE playlists SET version=version+1 WHERE guild_id='g' AND id='p'")
    with pytest.raises(ParseError, match='stale_collection'):
        await validator.invoke(checked, None, actor, view, **args,
                               confirmation_consumed=True)
    assert invoked == []
    revoked = Actor('g', 'u', frozenset(), 'text')
    with pytest.raises(ParseError, match='command_not_allowed'):
        validator.validate(draft, view, revoked, **args)


def test_missing_or_forged_evidence_and_unmentioned_object_fail(tmp_path):
    validator, draft, view, actor, args, _db, _invoked = setup(tmp_path)
    with pytest.raises(ParseError, match='missing_evidence'):
        validator.validate(CommandDraft('C05', {'목록': 'p'}, {}), view, actor, **args)
    wrong = CommandDraft('C05', {'목록': 'other'}, draft.evidence)
    with pytest.raises(ParseError, match='selection_value_mismatch'):
        validator.validate(wrong, view, actor, **args)
    unmentioned = InputNormalizer().normalize('!!창근아 목록 이름변경', invocation='!!창근아')
    with pytest.raises(ParseError, match='collection_not_mentioned'):
        validator.validate(draft, unmentioned, actor, **args)


def test_pending_60_300_owner_expiry_and_atomic_single_use():
    store = PendingStore()
    attrs = dict(root_id='r', guild_id='g', channel_id='c', actor_id='u')
    typed = store.issue(kind='typed', command_id='C05', argument='목록',
                        payload={'allowed': True}, now=100, **attrs)
    with pytest.raises(ParseError, match='pending_owner_mismatch'):
        store.consume(typed, kind='typed', now=101,
                      **{**attrs, 'actor_id': 'stranger'})
    assert store.consume(typed, kind='typed', now=159.999, **attrs).argument == '목록'
    with pytest.raises(ParseError, match='pending_unknown_or_used'):
        store.consume(typed, kind='typed', now=160, **attrs)
    confirmation = store.issue(kind='confirm', command_id='C05', payload=True,
                               now=100, **attrs)
    with pytest.raises(ParseError, match='pending_expired'):
        store.consume(confirmation, kind='confirm', now=400, **attrs)


def test_duplicate_confirmation_only_one_wins():
    store = PendingStore()
    attrs = dict(root_id='r', guild_id='g', channel_id='c', actor_id='u')
    token = store.issue(kind='confirm', command_id='C05', payload=True, now=100,
                        **attrs)
    def click(_):
        try:
            store.consume(token, kind='confirm', now=101, **attrs)
            return True
        except ParseError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(click, range(2))) == [False, True]


@pytest.mark.asyncio
async def test_typed_collection_answer_is_bound_and_rechecked(tmp_path):
    validator, draft, view, actor, args, db, invoked = setup(tmp_path)
    original = InputNormalizer().normalize('!!창근아 목록 이름변경', invocation='!!창근아')
    snapshot = next(iter(validator.snapshots.values()))
    store = PendingStore()
    attrs = dict(root_id='r', guild_id='g', channel_id='text', actor_id='u')
    token = store.issue(kind='typed', command_id='C05', argument='목록',
                        payload=TypedQuestion(CommandDraft('C05', {}, {}), snapshot), **attrs)
    action = store.consume(token, kind='typed', **attrs)
    typed, context = answer_typed(action, '운동', validator.service.specs['C05'],
                                  guild_id='g', channel_id='text', actor_id='u')
    kwargs = {**args, 'contexts': {context.context_id: context}}
    checked = validator.validate(typed, original, actor, **kwargs)
    await validator.invoke(checked, None, actor, original,
                           confirmation_consumed=True, **kwargs)
    assert invoked == [{'목록': 'p'}]
    with pytest.raises(ParseError, match='foreign_context'):
        validator.validate(typed, original, actor, **args)
    with db.transaction() as conn:
        conn.execute("UPDATE playlists SET version=version+1 WHERE guild_id='g' AND id='p'")
    with pytest.raises(ParseError, match='stale_collection'):
        validator.validate(typed, original, actor, **kwargs)


def test_typed_reply_does_not_reinterpret_command_or_other_argument():
    spec = CommandSpec('C20', '반복', '반복 설정',
                       (ArgumentSpec('횟수', 'integer', True),), 'dj', 'write')
    store = PendingStore()
    attrs = dict(root_id='r', guild_id='g', channel_id='c', actor_id='u')
    token = store.issue(kind='typed', command_id='C20', argument='횟수',
                        payload=TypedQuestion(CommandDraft('C20', {}, {})), **attrs)
    action = store.consume(token, kind='typed', **attrs)
    with pytest.raises(ParseError, match='invalid_integer'):
        answer_typed(action, '5번 하고 목록 삭제', spec,
                     guild_id='g', channel_id='c', actor_id='u')
    replacement = store.issue(kind='confirm', command_id='C20', payload=True, **attrs)
    newer = store.issue(kind='confirm', command_id='C20', payload=True, **attrs)
    with pytest.raises(ParseError, match='pending_unknown_or_used'):
        store.consume(replacement, kind='confirm', **attrs)
    assert store.consume(newer, kind='confirm', **attrs).command_id == 'C20'


def test_typed_zero_large_integer_and_false_remain_explicit():
    store = PendingStore()
    attrs = dict(root_id='r', guild_id='g', channel_id='c', actor_id='u')
    spec = CommandSpec('C20', '범위', '값', (
        ArgumentSpec('횟수', 'integer', True, minimum=0, maximum=10000),
        ArgumentSpec('교체', 'boolean', True),
    ), 'dj', 'write')
    draft = CommandDraft('C20', {}, {})
    first = store.issue(kind='typed', command_id='C20', argument='횟수',
                        payload=TypedQuestion(draft), **attrs)
    parsed, _ = answer_typed(store.consume(first, kind='typed', **attrs), '0', spec,
                             guild_id='g', channel_id='c', actor_id='u')
    assert parsed.arguments['횟수'] == 0
    second = store.issue(kind='typed', command_id='C20', argument='횟수',
                         payload=TypedQuestion(draft), **attrs)
    parsed, _ = answer_typed(store.consume(second, kind='typed', **attrs), '1234', spec,
                             guild_id='g', channel_id='c', actor_id='u')
    assert parsed.arguments['횟수'] == 1234
    third = store.issue(kind='typed', command_id='C20', argument='교체',
                        payload=TypedQuestion(parsed), **attrs)
    parsed, _ = answer_typed(store.consume(third, kind='typed', **attrs), '아니요', spec,
                             guild_id='g', channel_id='c', actor_id='u')
    assert parsed.arguments['교체'] is False
