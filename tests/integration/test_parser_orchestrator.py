import time

import httpx
import pytest

from changgeun.application.commands import CommandService
from changgeun.domain.models import Actor, Policy
from changgeun.parser.contracts import CommandDraft, ParseError, ParserOutcome
from changgeun.parser.normalizer import InputNormalizer
from changgeun.parser.orchestrator import ParserOrchestrator, RewritePolicyValidator
from changgeun.parser.registry import CommandSpec
from changgeun.storage.database import Database


class Interpreter:
    def __init__(self, first, after=None):
        self.first, self.after = first, after
        self.calls = []

    async def interpret(self, _view, _actor, *, pass_id, **_kwargs):
        self.calls.append(pass_id)
        answer = self.first if pass_id == 'initial' else self.after
        if isinstance(answer, Exception):
            raise answer
        return answer


class Model:
    def __init__(self, rewrite=None, full=None):
        self.rewrite, self.full = rewrite, full
        self.calls = []

    async def call(self, operation, state, **_kwargs):
        self.calls.append(operation)
        return self.rewrite if operation == 'rewrite' else self.full

    async def cancel(self):
        pass


def environment(tmp_path, interpreter, model, *, fallback=False, llm=True):
    db = Database(tmp_path / 'db.sqlite')
    async def noop(_entry, _args):
        raise AssertionError('no command execution in parser')
    command = CommandSpec('C25', '목록 보기', '재생목록 보기', (), 'public', 'read')
    commands = CommandService({'C25': command}, {'C25': noop})
    policy = Policy(frozenset({'g'}), frozenset(), frozenset(), frozenset())
    actor = Actor('g', 'u', frozenset(), 'text')
    parser = ParserOrchestrator(interpreter, model, commands, db, policy,
                                llm_enabled=llm, fallback_on_jev_unavailable=fallback)
    view = InputNormalizer().normalize('!!창근아 목록 보여줘', invocation='!!창근아')
    return parser, view, actor


def full_success():
    return {'status': 'parsed', 'plan': {'command': 'C25', 'arguments': {}},
            'unresolved_arguments': [], 'question': None}


@pytest.mark.asyncio
async def test_initial_success_has_no_fallback(tmp_path):
    initial = ParserOutcome('parsed', CommandDraft('C25', {}, {}))
    interpreter, model = Interpreter(initial), Model()
    parser, view, actor = environment(tmp_path, interpreter, model)
    outcome = await parser.parse(view, actor, root_id='r', scope_hash='scope',
                                 expires_at=time.time() + 30)
    assert outcome.status == 'parsed' and model.calls == []
    assert interpreter.calls == ['initial']


@pytest.mark.asyncio
async def test_valid_rewrite_reinterprets_once_and_preserves_llm_assistance(tmp_path):
    interpreter = Interpreter(ParserOutcome('failed', code='interpretation_unclear'),
                              ParserOutcome('parsed', CommandDraft('C25', {}, {})))
    model = Model(rewrite={'status': 'rewritten', 'rewritten_text': '재생목록 보여줘',
                           'unresolved_references': [], 'question': None})
    parser, view, actor = environment(tmp_path, interpreter, model)
    outcome = await parser.parse(view, actor, root_id='r', scope_hash='scope',
                                 expires_at=time.time() + 30)
    assert outcome.status == 'parsed' and outcome.draft.llm_assisted
    assert outcome.draft.parser_source == 'jev_after_rewrite'
    assert interpreter.calls == ['initial', 'after_rewrite']
    assert model.calls == ['rewrite']


@pytest.mark.asyncio
async def test_unchanged_skips_second_jev_and_uses_one_full_parse(tmp_path):
    interpreter = Interpreter(ParserOutcome('failed', code='interpretation_unclear'))
    model = Model(rewrite={'status': 'unchanged', 'rewritten_text': '목록 보여줘',
                           'unresolved_references': [], 'question': None},
                  full=full_success())
    parser, view, actor = environment(tmp_path, interpreter, model)
    outcome = await parser.parse(view, actor, root_id='r', scope_hash='scope',
                                 expires_at=time.time() + 30)
    assert outcome.status == 'parsed' and outcome.draft.parser_source == 'llm_full_parse'
    assert interpreter.calls == ['initial']
    assert model.calls == ['rewrite', 'full_parse']


@pytest.mark.asyncio
async def test_multiple_and_deadline_never_call_fallback(tmp_path):
    interpreter = Interpreter(ParserOutcome('multiple', code='multiple_intents'))
    model = Model()
    parser, view, actor = environment(tmp_path, interpreter, model)
    result = await parser.parse(view, actor, root_id='r', scope_hash='scope',
                                expires_at=time.time() + 30)
    assert result.status == 'multiple' and model.calls == []
    result = await parser.parse(view, actor, root_id='r', scope_hash='scope',
                                expires_at=time.time() - 1)
    assert result.status == 'failed' and result.code == 'deadline_expired'


@pytest.mark.asyncio
async def test_jev_unavailable_requires_explicit_opt_in(tmp_path):
    unavailable = httpx.ConnectError('unavailable')
    interpreter, model = Interpreter(unavailable), Model(full=full_success())
    parser, view, actor = environment(tmp_path, interpreter, model, fallback=False)
    result = await parser.parse(view, actor, root_id='r', scope_hash='scope',
                                expires_at=time.time() + 30)
    assert result.code == 'jev_unavailable' and model.calls == []
    parser, view, actor = environment(tmp_path, interpreter, model, fallback=True)
    result = await parser.parse(view, actor, root_id='r', scope_hash='scope',
                                expires_at=time.time() + 30)
    assert result.status == 'parsed' and model.calls == ['full_parse']


def test_rewrite_guard_rejects_protected_literal_number_and_negation_changes():
    validator = RewritePolicyValidator()
    view = InputNormalizer().normalize('!!창근아 "퇴근  후" 3곡 말고 2곡 틀어줘',
                                       invocation='!!창근아')
    def output(text):
        return {'status': 'rewritten', 'rewritten_text': text,
                'unresolved_references': [], 'question': None}
    with pytest.raises(ParseError, match='rewrite_literal_changed'):
        validator.check(view, output('퇴근 후 3곡 말고 2곡 틀어줘'))
    with pytest.raises(ParseError, match='rewrite_quantity_changed'):
        validator.check(view, output('"퇴근  후" 3곡 말고 4곡 틀어줘'))
    with pytest.raises(ParseError, match='rewrite_control_changed'):
        validator.check(view, output('"퇴근  후" 3곡 2곡 틀어줘'))


@pytest.mark.asyncio
async def test_conflicting_reinterpretation_requires_clarification(tmp_path):
    initial = ParserOutcome('failed', code='low_confidence',
                            options={'selected_command': 'C05'})
    after = ParserOutcome('parsed', CommandDraft('C25', {}, {}))
    interpreter = Interpreter(initial, after)
    model = Model(rewrite={'status': 'rewritten', 'rewritten_text': '재생목록 보여줘',
                           'unresolved_references': [], 'question': None},
                  full=full_success())
    parser, view, actor = environment(tmp_path, interpreter, model)
    result = await parser.parse(view, actor, root_id='r', scope_hash='scope',
                                expires_at=time.time() + 30)
    assert result.status == 'clarify' and result.code == 'interpretation_conflict'
    assert model.calls == ['rewrite']


@pytest.mark.asyncio
async def test_invalid_rewrite_returns_to_original_full_parse(tmp_path):
    interpreter = Interpreter(ParserOutcome('failed', code='interpretation_unclear'))
    model = Model(rewrite={'status': 'rewritten', 'rewritten_text': '다른 목록 보여줘',
                           'unresolved_references': [], 'question': None},
                  full=full_success())
    parser, _view, actor = environment(tmp_path, interpreter, model)
    view = InputNormalizer().normalize('!!창근아 "운동" 목록 보여줘',
                                       invocation='!!창근아')
    result = await parser.parse(view, actor, root_id='r', scope_hash='scope',
                                expires_at=time.time() + 30)
    assert result.status == 'parsed'
    assert interpreter.calls == ['initial']
    assert model.calls == ['rewrite', 'full_parse']
