from types import SimpleNamespace

import pytest

from changgeun.application.commands import CommandService
from changgeun.domain.models import Actor, Policy
from changgeun.parser.collections import resolve_collection
from changgeun.parser.contracts import CommandDraft, Evidence, ParseError
from changgeun.parser.jev import _choice_set
from changgeun.parser.llm_schema import full_parse_schema
from changgeun.parser.normalizer import InputNormalizer
from changgeun.parser.registry import ArgumentSpec, CommandSpec
from changgeun.parser.validation import DraftValidator
from changgeun.storage.database import Database


def setup(tmp_path, *, required=True, attachments=()):
    db = Database(tmp_path / 'db.sqlite')
    policy = Policy(frozenset({'g'}), frozenset({'dj'}), frozenset(), frozenset())
    actor = Actor('g', 'u', frozenset({'dj'}), 'text')
    argument = ArgumentSpec('파일', 'attachment', required, source='collection',
                            collection='attachments')
    spec = CommandSpec('C09', '첨부 가져오기', '첨부 시험', (argument,), 'dj', 'write')
    selected = resolve_collection(spec, argument, actor, policy, db, root_id='r',
                                  pass_id='initial', scope_hash='scope',
                                  attachments=attachments)
    service = CommandService({'C09': spec}, {'C09': async_noop})
    validator = DraftValidator(service, db, policy, {selected.snapshot_id: selected},
                               attachments=attachments)
    return spec, argument, selected, validator, actor


async def async_noop(_entry, _values):
    pass


def test_only_current_message_attachments_are_listed_and_rechecked(tmp_path):
    first = SimpleNamespace(id=101, filename='mix.mp3', size=42,
                            url='https://private.invalid/secret')
    _spec, _arg, selected, validator, actor = setup(tmp_path, attachments=(first,))
    assert selected.original_count == selected.delivered_count == 1
    assert 'secret' not in repr(selected.criteria())
    choice = selected.selections[0]
    draft = CommandDraft('C09', {'파일': '101'}, {'파일': Evidence(
        'collection', snapshot_id=selected.snapshot_id, selection_id=choice.token)})
    view = InputNormalizer().normalize('!!창근아 이 첨부파일 가져와',
                                       invocation='!!창근아')
    args = dict(root_id='r', pass_id='initial', scope_hash='scope', watch_allowed=True)
    assert validator.validate(draft, view, actor, **args).arguments['파일'] == '101'
    validator.attachments = ()
    named = InputNormalizer().normalize('!!창근아 mix.mp3 파일 가져와',
                                        invocation='!!창근아')
    with pytest.raises(ParseError, match='stale_collection'):
        validator.validate(draft, named, actor, **args)


def test_multiple_attachments_need_filename_or_trusted_selection(tmp_path):
    files = (SimpleNamespace(id=101, filename='A.mp3', size=1),
             SimpleNamespace(id=102, filename='B.mp3', size=2))
    _spec, _arg, selected, validator, actor = setup(tmp_path, attachments=files)
    choice = next(item for item in selected.selections if item.item.object_id == '101')
    draft = CommandDraft('C09', {'파일': '101'}, {'파일': Evidence(
        'collection', snapshot_id=selected.snapshot_id, selection_id=choice.token)})
    vague = InputNormalizer().normalize('!!창근아 첨부파일 가져와', invocation='!!창근아')
    args = dict(root_id='r', pass_id='initial', scope_hash='scope', watch_allowed=True)
    with pytest.raises(ParseError, match='collection_not_mentioned'):
        validator.validate(draft, vague, actor, **args)
    named = InputNormalizer().normalize('!!창근아 A.mp3 파일 가져와',
                                        invocation='!!창근아')
    assert validator.validate(draft, named, actor, **args).arguments['파일'] == '101'


def test_optional_empty_attachment_list_is_null_without_model_choice(tmp_path):
    spec, arg, selected, _validator, _actor = setup(tmp_path, required=False)
    view = InputNormalizer().normalize('!!창근아 링크로 가져와', invocation='!!창근아')
    with pytest.raises(ParseError, match='optional_unmentioned'):
        _choice_set(arg, view, snapshot=selected)
    schema = full_parse_schema({'C09': spec}, collections={('C09', '파일'): selected})
    branch = schema['properties']['decision']['anyOf'][0]['properties']['plan']['anyOf'][0]
    assert branch['properties']['arguments']['properties']['파일'] == {'type': 'null'}
