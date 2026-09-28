import pytest

from changgeun.parser.contracts import ParseError
from changgeun.parser.normalizer import InputNormalizer
from changgeun.parser.values import mentions, numbers, quoted_text, text_spans, urls


def test_deterministic_values_keep_raw_spans_and_exclude_invocation_mention():
    view = InputNormalizer().normalize(
        '<@1234>  "퇴근  후"  youtube.com/watch?v=GD_rjpO7CIQ '
        '<#9876> 3곡 틀어줘', invocation='<@1234>')
    assert [item.value for item in quoted_text(view)] == ['퇴근  후']
    assert [item.value for item in urls(view)] == ['youtube.com/watch?v=GD_rjpO7CIQ']
    assert [item.value for item in mentions(view)] == ['<#9876>']
    assert [item.value for item in numbers(view)] == [3]
    for item in (*quoted_text(view), *urls(view), *mentions(view), *numbers(view)):
        assert view.verify(item.evidence)


def test_text_spans_are_contiguous_and_reject_overflow():
    view = InputNormalizer().normalize('!!창근아 퇴근 후 목록', invocation='!!창근아')
    values = text_spans(view)
    assert any(value.value == '퇴근 후' for value in values)
    assert all(view.verify(value.evidence) for value in values)
    long = InputNormalizer().normalize(' '.join(['단어'] * 20))
    with pytest.raises(ParseError, match='source_candidate_overflow'):
        text_spans(long)
