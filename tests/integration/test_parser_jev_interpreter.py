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
@pytest.mark.parametrize('target,text,expected', [
    ('목록', '운동 틀어줘', 'p0'),
    ('곡', 'RED 틀어줘', 't'),
])
async def test_playback_uses_one_strong_actual_target_despite_weak_optional_answers(
    tmp_path, target, text, expected,
):
    db, _, actor, policy = setup(tmp_path)
    spec = CommandSpec('C23', '재생', '곡 또는 저장 목록 재생', (
        ArgumentSpec('곡', 'string', False, source='collection', collection='tracks'),
        ArgumentSpec('목록', 'string', False, source='collection', collection='playlists'),
        ArgumentSpec('검색어', 'string', False),
    ), 'dj', 'write')

    async def noop(_entry, _args):
        raise AssertionError('parser must not execute')

    class PlaybackModel(Model):
        async def call(self, operation, state, **kwargs):
            if operation == 'command_select':
                assert len(state['known_entities']['playlists']) == 12
                assert len(state['known_entities']['tracks']) == 1
                assert {row['name'] for row in state['known_entities']['playlists']} == {
                    '운동', *(f'그외{n}' for n in range(1, 12))}
            result = await super().call(operation, state, **kwargs)
            if operation == 'argument_select':
                for key, answer in result['answers'].items():
                    if key == 'arg_' + target:
                        criterion = kwargs['questions'][key]['criteria']
                        chosen = next(k for k, v in criterion.items()
                                      if (target == '목록' and '운동' in v)
                                      or (target == '곡' and 'RED' in v))
                        answer['choice'] = chosen
                        answer['probabilities'] = {
                            k: 0.96 if k == chosen else 0.04 / (len(criterion) - 1)
                            for k in criterion}
                    else:
                        answer['confidence'] = 0.38
            return result

    model = PlaybackModel(command='C23')
    view = InputNormalizer().normalize('!!창근아 ' + text, invocation='!!창근아')
    result = await JevInterpreter(
        CommandService({'C23': spec}, {'C23': noop}), model, db, policy,
    ).interpret(view, actor, root_id='playback', pass_id='initial', scope_hash='scope')
    assert result.status == 'parsed'
    assert result.draft.arguments == {target: expected}
    assert [call[0] for call in model.calls] == ['command_select', 'argument_select']


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


@pytest.mark.asyncio
@pytest.mark.parametrize('utterance,identifier', [
    ('저장된 재생목록을 보여줘', 'C01'),
    ('지금 대기열에 뭐가 있어?', 'C16'),
    ('사용법을 알려줘', 'C38'),
])
async def test_read_request_hints_still_require_jev_selection(tmp_path, utterance, identifier):
    db = Database(tmp_path / 'catalog.sqlite')
    db.ensure_guild('g')
    specs = {key: CommandSpec(key, key, key, (), 'public', 'read')
             for key in ('C01', 'C16', 'C38')}
    async def noop(_entry, _args):
        raise AssertionError('parser must not execute')
    service = CommandService(specs, {key: noop for key in specs})
    model = Model(command=identifier)
    actor = Actor('g', 'u', frozenset(), 'text')
    policy = Policy(frozenset({'g'}), frozenset(), frozenset(), frozenset())
    view = InputNormalizer().normalize(utterance)
    result = await JevInterpreter(service, model, db, policy).interpret(
        view, actor, root_id='r', pass_id='initial', scope_hash='scope')
    assert result.status == 'parsed' and result.draft.command_id == identifier
    assert set(model.calls[0][3]['command']['criteria']) == {identifier, '__NONE__'}
    assert len(model.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('utterance', [
    '들어와', '들어와줘', '들어와봐', '여기 들어와', '입장해줘',
])
async def test_short_voice_join_uses_slash_default_channel(tmp_path, utterance):
    db = Database(tmp_path / 'voice.sqlite')
    db.ensure_guild('g')
    spec = CommandSpec('C21', '입장', '허용 음성채널 입장', (
        ArgumentSpec('채널', 'string', False, source='collection',
                     collection='voice_channels'),
    ), 'dj', 'write')

    async def noop(_entry, _args):
        raise AssertionError('parser must not execute')

    service = CommandService({'C21': spec}, {'C21': noop})
    actor = Actor('g', 'u', frozenset({'dj'}), 'text', voice_channel_id='voice')
    policy = Policy(frozenset({'g'}), frozenset({'dj'}), frozenset(),
                    frozenset({'voice'}))
    model = Model(command='C21')
    view = InputNormalizer().normalize(utterance)
    result = await JevInterpreter(service, model, db, policy).interpret(
        view, actor, root_id='voice-root', pass_id='initial', scope_hash='scope')
    assert result.status == 'parsed' and result.draft.arguments == {}
    assert [call[0] for call in model.calls] == ['command_select']


@pytest.mark.asyncio
@pytest.mark.parametrize('utterance,expected', [
    ('퇴장해', 'parsed'), ('나가', 'parsed'), ('나가라고 했어', 'failed'),
])
async def test_short_voice_leave_is_request_after_jev_selects_leave(
    tmp_path, utterance, expected,
):
    db = Database(tmp_path / 'voice.sqlite')
    db.ensure_guild('g')
    spec = CommandSpec('C22', '퇴장', '현재 음성채널 퇴장', (), 'dj', 'write')

    async def noop(_entry, _args):
        raise AssertionError('parser must not execute')

    service = CommandService({'C22': spec}, {'C22': noop})
    actor = Actor('g', 'u', frozenset({'dj'}), 'text', voice_channel_id='voice')
    policy = Policy(frozenset({'g'}), frozenset({'dj'}), frozenset(),
                    frozenset({'voice'}))

    class WeakKindModel(Model):
        async def call(self, operation, state, *, pass_id=None, stage_index=None,
                       questions=None, output_schema=None):
            result = await super().call(operation, state, pass_id=pass_id,
                                        stage_index=stage_index, questions=questions,
                                        output_schema=output_schema)
            result['answers']['input_kind'] = {
                'type': 'choice', 'choice': 'not_request', 'confidence': .34,
                'probabilities': {'single': .27, 'multiple': .11,
                                  'not_request': .51, 'unclear': .11},
            }
            result['answers']['command'] = {
                'type': 'choice', 'choice': 'C22', 'confidence': .79,
                'probabilities': {'C22': .8, '__NONE__': .2},
            }
            return result

    model = WeakKindModel(command='C22')
    view = InputNormalizer().normalize(utterance)
    result = await JevInterpreter(service, model, db, policy).interpret(
        view, actor, root_id='voice-root', pass_id='initial', scope_hash='scope')
    assert result.status == expected
    if expected == 'parsed':
        assert result.draft.command_id == 'C22'
    assert [call[0] for call in model.calls] == ['command_select']
