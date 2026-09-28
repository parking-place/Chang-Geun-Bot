"""Deterministic raw-span values; collection-backed objects live in collections.py."""

from __future__ import annotations

import re
from dataclasses import dataclass

from changgeun.nlp.pipeline import korean_number
from changgeun.parser.contracts import Evidence, ParseError
from changgeun.parser.normalizer import NormalizedInput

_URL = re.compile(r"(?<![\w@./:-])(?:https?://[^\s<>]+|(?:(?:www\.|m\.)?"
                  r"youtube\.com|youtu\.be)/[^\s<>]+)", re.IGNORECASE)
_MENTION = re.compile(r"<@!?\d+>|<@&\d+>|<#\d+>")
_NUMBER = re.compile(r"(?<![\w])(?:\d{1,3}|첫|한|하나|두|둘|세|셋|네|넷|"
                     r"다섯|여섯|일곱|여덟|아홉|열|스물|서른|백)(?:번째|번|개|곡|초)?(?![\w])")
_QUOTE = re.compile(r"[\"“‘']([^\"”’']+)[\"”’']")


@dataclass(frozen=True)
class SourceValue:
    value: str | int
    evidence: Evidence
    derivation: str


def _raw(view: NormalizedInput, start: int, end: int) -> Evidence:
    evidence = Evidence("span", view.original_text[start:end], start, end)
    if not view.verify(evidence):
        raise ParseError("source_mismatch")
    return evidence


def _content_start(view: NormalizedInput) -> int:
    return view.removed_invocation.end if view.removed_invocation else 0


def urls(view: NormalizedInput) -> tuple[SourceValue, ...]:
    return tuple(SourceValue(match.group(), _raw(view, match.start(), match.end()), "url")
                 for match in _URL.finditer(view.original_text)
                 if match.start() >= _content_start(view))


def mentions(view: NormalizedInput) -> tuple[SourceValue, ...]:
    return tuple(SourceValue(match.group(), _raw(view, match.start(), match.end()), "mention")
                 for match in _MENTION.finditer(view.original_text)
                 if match.start() >= _content_start(view))


def numbers(view: NormalizedInput) -> tuple[SourceValue, ...]:
    result = []
    for match in _NUMBER.finditer(view.original_text):
        if match.start() < _content_start(view):
            continue
        value = re.sub(r"(?:번째|번|개|곡|초)$", "", match.group())
        parsed = korean_number(value)
        if parsed is not None:
            result.append(SourceValue(parsed, _raw(view, match.start(), match.end()),
                                      "korean_number"))
    return tuple(result)


def quoted_text(view: NormalizedInput) -> tuple[SourceValue, ...]:
    return tuple(SourceValue(match.group(1), _raw(view, match.start(1), match.end(1)),
                             "quoted_text") for match in _QUOTE.finditer(view.original_text)
                 if match.start() >= _content_start(view))


def text_spans(view: NormalizedInput, *, max_words: int = 8,
               max_candidates: int = 80) -> tuple[SourceValue, ...]:
    """All contiguous short spans, never a silently truncated candidate prefix."""
    words = list(re.finditer(r"\S+", view.normalized_text))
    if sum(min(max_words, len(words) - i) for i in range(len(words))) > max_candidates:
        raise ParseError("source_candidate_overflow")
    result = []
    for index, word in enumerate(words):
        for following in words[index:index + max_words]:
            evidence = view.raw_span(word.start(), following.end())
            result.append(SourceValue(evidence.raw, evidence, "contiguous_span"))
    return tuple(result)
