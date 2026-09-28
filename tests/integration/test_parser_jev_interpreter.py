import pytest

from changgeun.application.commands import CommandService
from changgeun.domain.models import Actor, Policy
from changgeun.parser.jev import JevInterpreter
from changgeun.parser.normalizer import InputNormalizer
from changgeun.parser.registry import ArgumentSpec, CommandSpec
from changgeun.storage.database import Database


class Model:
    def __init__(self, command='C05', kind='single'):
        self.command, self.kind = command, kind
        self.calls = []

    async def call(self, operation, state, *, pass_id=None, stage_index=None,
                   questions=None, output_schema=None):
        self.calls.append((operation, pass_id, stage_index, questions))
        answers = {}
        for key, question in questions.items():
            criteria = question['criteria']
            if key == 'input_kind':
                selected = self.kind
            elif key == 'command':
                selected = self.command
            elif key == 'arg_목록':
                selected = next(k for k, v in criteria.items() if '운동' in v)
            elif key == 'arg_새이름':
                selected = next(k for k, v in criteria.items() if '퇴근  후' in v)
            elif key == 'arg_번호':
                selected = next(k for k, v in criteria.items() if '2번' in v)
            else:
                selected = '__MISSING__'
            rest = 0.04 / (len(criteria) - 1)
            answers[key] = {'type': 'choice', 'choice': selected,
                            'probabilities': {k: 0.96 if k == selected else rest
                                              for k in criteria}, 'confidence': 0.91}
        return {'answers': answers}

    async def cancel(self):
        pass


def setup(tmp_path):
    db = Database(tmp_path / 'catalog.sqlite')
    db.ensure_guild('g')
    with db.transaction() as conn:
        for index in range(12):
            conn.execute('INSERT INTO playlists(guild_id,id,name,normalized_name) '
                         'VALUES(?,?,?,?)', ('g', f'p{index}',
                                              '운동' if index == 0 else f'그외{index}',
                                              f'n{index}'))
        conn.execute("INSERT INTO tracks(guild_id,id,source_type,external_id,title) "
                     "VALUES('g','t','approved','t','RED')")
        for index in range(2):
            conn.execute('INSERT INTO playlist_entries VALUES(?,?,?,?,?)',
                         ('g', 'p0', f'e{index}', 't', index))
    rename = CommandSpec('C05', '목록 이름변경', '기존 목록의 새 이름', (
        ArgumentSpec('목록', 'string', True, source='collection', collection='playlists'),
        ArgumentSpec('새이름', 'string', True, source='source_span'),
    ), 'dj', 'write')
    remove = CommandSpec('C12', '목록 제거', '기존 목록의 곡 제거', (
        ArgumentSpec('목록', 'string', True, source='collection', collection='playlists'),
        ArgumentSpec('번호', 'integer', True, source='collection',
                     collection='playlist_entries', depends_on='목록'),
    ), 'dj', 'write')
    async def noop(_entry, _args):
        raise AssertionError('parser must not execute')
    service = CommandService({'C05': rename, 'C12': remove},
                             {'C05': noop, 'C12': noop})
    actor = Actor('g', 'u', frozenset({'dj'}), 'text')
    policy = Policy(frozenset({'g'}), frozenset({'dj'}), frozenset(), frozenset())
    return db, service, actor, policy


@pytest.mark.asyncio
async def test_two_questions_then_batched_arguments_use_full_actual_list(tmp_path):
    db, service, actor, policy = setup(tmp_path)
    model = Model()
    view = InputNormalizer().normalize('!!창근아 운동 목록 이름을 "퇴근  후"로 바꿔줘',
                                       invocation='!!창근아')
    result = await JevInterpreter(service, model, db, policy).interpret(
        view, actor, root_id='r', pass_id='initial', scope_hash='scope')
    assert result.status == 'parsed'
    assert result.draft.arguments['목록'] == 'p0'
    assert result.draft.arguments['새이름'] == '퇴근  후'
    assert view.verify(result.draft.evidence['새이름'])
    assert [item[0] for item in model.calls] == ['command_select', 'argument_select']
    assert len(model.calls[0][3]) == 2 and len(model.calls[1][3]) == 2
    assert len(model.calls[1][3]['arg_목록']['criteria']) == 15


@pytest.mark.asyncio
async def test_dependent_entry_lookup_requires_third_stage(tmp_path):
    db, service, actor, policy = setup(tmp_path)
    model = Model(command='C12')
    view = InputNormalizer().normalize('!!창근아 운동 목록 2번 빼줘', invocation='!!창근아')
    result = await JevInterpreter(service, model, db, policy).interpret(
        view, actor, root_id='r', pass_id='initial', scope_hash='scope')
    assert result.status == 'parsed'
    assert result.draft.arguments == {'목록': 'p0', '번호': 2}
    assert [item[0] for item in model.calls] == [
        'command_select', 'argument_select', 'context_select']


@pytest.mark.asyncio
async def test_multiple_intents_do_not_execute_selected_command(tmp_path):
    db, service, actor, policy = setup(tmp_path)
    model = Model(kind='multiple')
    view = InputNormalizer().normalize('!!창근아 목록 바꾸고 틀어줘', invocation='!!창근아')
    result = await JevInterpreter(service, model, db, policy).interpret(
        view, actor, root_id='r', pass_id='initial', scope_hash='scope')
    assert result.status == 'multiple' and result.draft is None
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_after_rewrite_reselects_command_instead_of_reusing_first(tmp_path):
    db, service, actor, policy = setup(tmp_path)
    model = Model(command='C12')
    view = InputNormalizer().normalize('!!창근아 운동 목록 2번 빼줘', invocation='!!창근아')
    result = await JevInterpreter(service, model, db, policy).interpret(
        view, actor, root_id='r', pass_id='after_rewrite', scope_hash='scope',
        rewritten_text='운동 재생목록 두 번째 곡 제거')
    assert result.status == 'parsed' and result.draft.command_id == 'C12'
    assert all(item[1] == 'after_rewrite' for item in model.calls)
