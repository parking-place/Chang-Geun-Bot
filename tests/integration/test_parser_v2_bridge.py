import time
from types import SimpleNamespace

import pytest

from changgeun.application.commands import CommandService
from changgeun.discord_adapter import parser_v2
from changgeun.domain.models import Actor, Policy
from changgeun.parser.contracts import CommandDraft
from changgeun.parser.normalizer import InputNormalizer
from changgeun.parser.registry import ArgumentSpec, CommandSpec
from changgeun.parser.validation import ValidatedCommand
from changgeun.storage.database import Database


class FakeSession:
    def __init__(self, gateway, *, request_id, scope_hash, original_text):
        self.root = {'expires_at': time.time() + 35}
        self.calls = 0

    async def call(self, operation, state, *, pass_id=None, stage_index=None,
                   questions=None, output_schema=None):
        self.calls += 1
        assert operation == 'command_select'
        answers = {}
        for name, question in questions.items():
            criteria = question['criteria']
            selected = 'single' if name == 'input_kind' else 'C01'
            answers[name] = {'type': 'choice', 'choice': selected, 'confidence': 0.99,
                             'probabilities': {key: float(key == selected) for key in criteria}}
        return {'answers': answers}

    async def cancel(self):
        pass


@pytest.mark.asyncio
async def test_opt_in_read_uses_validated_shared_callback(tmp_path, monkeypatch):
    monkeypatch.setattr(parser_v2, 'ParserSession', FakeSession)
    db = Database(tmp_path / 'db.sqlite')
    db.ensure_guild('g')
    policy = Policy(frozenset({'g'}), frozenset({'dj'}), frozenset({'c'}), frozenset())
    actor = Actor('g', 'u', frozenset(), 'c')
    invoked = []

    async def callback(entry, arguments):
        assert entry.response.is_done()
        await entry.response.defer(ephemeral=True)
        invoked.append(arguments)
        await entry.followup.send('목록 화면', ephemeral=True)

    service = CommandService({'C01': CommandSpec('C01', '목록 보기', '목록', (),
                                                 'public', 'read')},
                             {'C01': callback})
    responses = []

    async def send(content, **kwargs):
        responses.append((content, kwargs))

    async def member(_):
        return SimpleNamespace(id='u')

    async def ready():
        pass

    async def fresh(_):
        return actor

    guild = SimpleNamespace(fetch_member=member)
    source = SimpleNamespace(guild=guild, user=SimpleNamespace(id='u'),
                             followup=SimpleNamespace(send=send),
                             response=SimpleNamespace(is_done=lambda: True))
    client = SimpleNamespace(gateway=SimpleNamespace(ready=ready), db=db,
                             command_service=service,
                             config=SimpleNamespace(policy=policy,
                                                    parser_llm_fallback='disabled'),
                             fresh_actor=fresh)
    await parser_v2.ParserV2Bridge(client).parse(source, '목록 보여줘', actor, 'r')
    assert invoked == [{}]
    assert responses == [('목록 화면', {'ephemeral': True})]


@pytest.mark.asyncio
async def test_confirmation_button_is_owned_and_single_use():
    calls = []
    actor = Actor('g', 'u', frozenset({'dj'}), 'c')

    async def fresh(_):
        return actor

    async def member(_):
        return SimpleNamespace(id='u')

    async def invoke(*args, **kwargs):
        calls.append(kwargs)

    def component(user):
        events = []
        response = SimpleNamespace(
            done=False,
            is_done=lambda: response.done,
        )
        async def defer(**kwargs):
            response.done = True
            events.append('defer')
        async def send_message(content, **kwargs):
            response.done = True
            events.append(content)
        response.defer, response.send_message = defer, send_message
        async def followup_send(content, **kwargs):
            events.append(content)
        return SimpleNamespace(guild_id='g', channel_id='c',
                               user=SimpleNamespace(id=user), response=response,
                               followup=SimpleNamespace(send=followup_send), events=events)

    guild = SimpleNamespace(fetch_member=member)
    source = SimpleNamespace(guild=guild)
    bridge = parser_v2.ParserV2Bridge(SimpleNamespace(fresh_actor=fresh))
    view = InputNormalizer().normalize('목록 이름변경')
    validated = ValidatedCommand(CommandDraft('C03', {}, {}), {}, 'g', 'u', True)
    pending = parser_v2._Confirmation(validated, source, source, view, 'r', 'initial',
                                      'scope', SimpleNamespace(invoke=invoke), guild)
    token = bridge.pending.issue(kind='confirm', root_id='r', guild_id='g', channel_id='c',
                                 actor_id='u', command_id='C03', payload=pending)
    buttons = parser_v2._ConfirmView(bridge, token, pending)
    foreign = component('other')
    await buttons.children[0].callback(foreign)
    assert calls == []
    assert '실행하지 않았어' in foreign.events[-1]
    owner = component('u')
    await buttons.children[0].callback(owner)
    assert len(calls) == 1 and calls[0]['confirmation_consumed'] is True
    again = component('u')
    await buttons.children[0].callback(again)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_typed_modal_completes_only_missing_argument_then_confirms(tmp_path, monkeypatch):
    model_calls = []

    class MissingSession(FakeSession):
        async def call(self, operation, state, *, pass_id=None, stage_index=None,
                       questions=None, output_schema=None):
            model_calls.append(operation)
            answers = {}
            for name, question in questions.items():
                criteria = question['criteria']
                selected = ('single' if name == 'input_kind' else 'C02'
                            if name == 'command' else '__MISSING__')
                answers[name] = {
                    'type': 'choice', 'choice': selected, 'confidence': 0.99,
                    'probabilities': {key: float(key == selected) for key in criteria},
                }
            return {'answers': answers}

    monkeypatch.setattr(parser_v2, 'ParserSession', MissingSession)
    db = Database(tmp_path / 'db.sqlite')
    db.ensure_guild('g')
    policy = Policy(frozenset({'g'}), frozenset({'dj'}), frozenset({'c'}), frozenset())
    actor = Actor('g', 'u', frozenset({'dj'}), 'c')
    calls, sent = [], []

    async def callback(entry, arguments):
        calls.append(arguments)

    async def send(content, **kwargs):
        sent.append((content, kwargs))

    async def member(_):
        return SimpleNamespace(id='u')

    async def ready():
        pass

    async def fresh(_):
        return actor

    service = CommandService({'C02': CommandSpec(
        'C02', '목록 생성', '새 목록', (ArgumentSpec('이름', 'string', True),),
        'dj', 'write')}, {'C02': callback})
    guild = SimpleNamespace(id='g', fetch_member=member)
    source = SimpleNamespace(guild=guild, channel_id='c', user=SimpleNamespace(id='u'),
                             followup=SimpleNamespace(send=send),
                             response=SimpleNamespace(is_done=lambda: True))
    client = SimpleNamespace(gateway=SimpleNamespace(ready=ready), db=db,
                             command_service=service, fresh_actor=fresh,
                             config=SimpleNamespace(policy=policy,
                                                    parser_llm_fallback='disabled'))
    bridge = parser_v2.ParserV2Bridge(client)
    await bridge.parse(source, '목록 만들어줘', actor, 'r')
    typed_view = sent[-1][1]['view']
    assert isinstance(typed_view, parser_v2._TypedView)
    assert calls == [] and model_calls == ['command_select', 'argument_select']

    def component(user='u'):
        events = []
        response = SimpleNamespace(done=False)
        response.is_done = lambda: response.done
        async def send_modal(modal):
            response.done = True
            events.append(modal)
        async def defer(**kwargs):
            response.done = True
        async def send_message(content, **kwargs):
            response.done = True
            events.append(content)
        response.send_modal, response.defer = send_modal, defer
        response.send_message = send_message
        async def followup_send(content, **kwargs):
            events.append(content)
        return SimpleNamespace(guild_id='g', channel_id='c',
                               user=SimpleNamespace(id=user), response=response,
                               followup=SimpleNamespace(send=followup_send), events=events)

    outsider = component('other')
    await typed_view.children[0].callback(outsider)
    assert outsider.events == ['요청자만 답할 수 있어.']
    click = component()
    await typed_view.children[0].callback(click)
    modal = click.events[0]
    modal.answer._value = '운동'
    submit = component()
    await modal.on_submit(submit)
    confirm_view = sent[-1][1]['view']
    assert isinstance(confirm_view, parser_v2._ConfirmView)
    assert calls == [] and len(model_calls) == 2
    await confirm_view.children[0].callback(component())
    assert calls == [{'이름': '운동'}]
    assert len(model_calls) == 2
