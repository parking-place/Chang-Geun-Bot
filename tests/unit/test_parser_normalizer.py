import random

import pytest

from changgeun.parser.contracts import ParseError
from changgeun.parser.normalizer import InputNormalizer


class Trace:
    def __init__(self):
        self.events = []

    def event(self, request_id, name, data):
        self.events.append((request_id, name, data))


@pytest.mark.parametrize("name", ["너에게", "쉼,표", "RED", "none", "ㅋㅋㅋㅋ"])
def test_existing_exact_names_remain_opaque(name):
    value = InputNormalizer().normalize(f"  !!창근아   {name}  틀어줘 ",
                                        invocation="!!창근아", known_names=[name])
    assert name in value.normalized_text
    at = value.normalized_text.index(name)
    evidence = value.raw_span(at, at + len(name))
    assert evidence.raw == name
    assert value.verify(evidence)


def test_quotes_url_mention_and_unclosed_quote_preserve_original():
    original = '!!창근아 "퇴근  후" youtube.com/watch?v=GD_rjpO7CIQ <#1234> 틀어줘'
    value = InputNormalizer().normalize(original, invocation="!!창근아")
    for expected in ('"퇴근  후"', 'youtube.com/watch?v=GD_rjpO7CIQ', '<#1234>'):
        assert expected in value.normalized_text
        at = value.normalized_text.index(expected)
        assert value.raw_span(at, at + len(expected)).raw == expected
    unclosed = InputNormalizer().normalize('!!창근아 "퇴근  후', invocation='!!창근아')
    assert unclosed.normalized_text == '"퇴근  후'


def test_source_map_codepoints_nfc_and_repeated_values():
    original = '   !!창근아   한  한  😀  e\u0301'
    value = InputNormalizer().normalize(original, invocation='!!창근아')
    assert value.normalized_text == '한 한 😀 é'
    first = value.normalized_text.index('한')
    second = value.normalized_text.index('한', first + 1)
    assert value.raw_span(first, first + 1).raw == '한'
    assert value.raw_span(second, second + 1).raw == '한'
    assert value.raw_span(value.normalized_text.index('é'),
                          len(value.normalized_text)).raw == 'e\u0301'
    assert value.source_map[first].start != value.source_map[second].start


def test_invalid_invocation_empty_input_and_outside_evidence_fail_closed():
    normalizer = InputNormalizer()
    with pytest.raises(ParseError, match='invalid_invocation'):
        normalizer.normalize('please !!창근아 목록', invocation='!!창근아')
    with pytest.raises(ParseError, match='empty_input'):
        normalizer.normalize(' !!창근아   ', invocation='!!창근아')
    value = normalizer.normalize('!!창근아 목록', invocation='!!창근아')
    with pytest.raises(ParseError, match='invalid_source_range'):
        value.raw_span(0, len(value.source_map) + 1)
    assert not value.verify(value.raw_span(1, 2).__class__(source='span', raw='X', start=7, end=8))


def test_trace_has_metadata_only_and_no_model_call():
    trace = Trace()
    InputNormalizer().normalize('!!창근아 쉼,표', invocation='!!창근아',
                                request_id='request-1', trace=trace)
    assert len(trace.events) == 1
    assert trace.events[0][1] == 'code.normalize'
    assert '쉼,표' not in repr(trace.events)


def test_random_unicode_ranges_are_valid_and_monotonic():
    rng = random.Random(120)
    alphabet = ['가', 'ᄒ', 'ᅡ', 'ᆫ', '😀', 'e', '\u0301', ' ', '\t', 'ㅋㅋ', '/', ',']
    normalizer = InputNormalizer()
    for _ in range(500):
        original = '!!창근아 ' + ''.join(rng.choices(alphabet, k=rng.randrange(1, 80)))
        try:
            value = normalizer.normalize(original, invocation='!!창근아')
        except ParseError as error:
            assert error.code == 'empty_input'
            continue
        assert len(value.normalized_text) == len(value.source_map)
        for span in value.source_map:
            assert 0 <= span.start < span.end <= len(original)
        for start in range(len(value.source_map)):
            end = min(start + 2, len(value.source_map))
            assert value.verify(value.raw_span(start, end))
