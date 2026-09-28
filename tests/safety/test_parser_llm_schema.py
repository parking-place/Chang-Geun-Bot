import pytest

from changgeun.parser.collections import CollectionItem, snapshot
from changgeun.parser.contracts import ParseError
from changgeun.parser.llm_schema import (
    full_parse_schema,
    rewrite_schema,
    validate_full_output,
    validate_rewrite_output,
)
from changgeun.parser.registry import ArgumentSpec, CommandSpec
from changgeun_inference.openai_v2 import validate_schema_value


def commands():
    return {'C05': CommandSpec('C05', '목록 이름변경', '기존 목록 변경', (
        ArgumentSpec('목록', 'string', True, source='collection', collection='playlists'),
        ArgumentSpec('새이름', 'string', True),
    ), 'dj', 'write')}


def collections():
    actual = snapshot([CollectionItem('internal-id', '운동')], collection_key='playlists',
                      root_id='r', pass_id='initial', argument='목록', scope_hash='scope')
    return {('C05', '목록'): actual}


def test_rewrite_contract_rejects_command_injection_and_extra_fields():
    valid = {'status': 'rewritten', 'rewritten_text': '운동 목록 이름 바꿔줘',
             'unresolved_references': [], 'question': None}
    assert validate_schema_value(valid, rewrite_schema())
    assert validate_rewrite_output(valid) == valid
    with pytest.raises(ParseError, match='invalid_rewrite_output'):
        validate_rewrite_output({**valid, 'command': 'C05'})


def test_full_contract_uses_only_real_opaque_member_ids():
    inventory, actual = commands(), collections()
    schema = full_parse_schema(inventory, collections=actual)
    token = actual[('C05', '목록')].selections[0].token
    output = {'status': 'parsed', 'plan': {'command': 'C05',
              'arguments': {'목록': {'candidate_id': token, 'query': None},
                            '새이름': '퇴근 후'}},
              'unresolved_arguments': [], 'question': None}
    assert validate_schema_value(output, schema)
    assert validate_full_output(output, commands=inventory, collections=actual) == output
    forged = {**output, 'plan': {**output['plan'], 'arguments': {
        **output['plan']['arguments'], '목록': {'candidate_id': 'forged', 'query': None}}}}
    assert not validate_schema_value(forged, schema)
    with pytest.raises(ParseError, match='foreign_selection'):
        validate_full_output(forged, commands=inventory, collections=actual)
    with pytest.raises(ParseError, match='collection_required_for_llm'):
        full_parse_schema(inventory, collections={})
