"""Conservative interpretation view with code-point provenance to immutable input."""

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from changgeun.parser.contracts import Evidence, ParseError, TracePort

_OPAQUE = re.compile(
    r"(?:https?://|www\.|(?:youtube\.com|youtu\.be)/)[^\s<>]+"
    r"|<@!?\d+>|<@&\d+>|<#[0-9]+>", re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int


@dataclass(frozen=True)
class NormalizedInput:
    original_text: str
    normalized_text: str
    source_map: tuple[SourceSpan, ...]
    protected_spans: tuple[SourceSpan, ...]
    removed_invocation: SourceSpan | None = None

    def raw_span(self, start: int, end: int) -> Evidence:
        """Return raw evidence for a nonempty normalized substring, or fail closed."""
        if not 0 <= start < end <= len(self.source_map):
            raise ParseError("invalid_source_range")
        spans = self.source_map[start:end]
        if any(a.start > b.start or a.end > b.end
               for a, b in zip(spans, spans[1:], strict=False)):
            raise ParseError("non_monotonic_source_map")
        raw_start, raw_end = spans[0].start, spans[-1].end
        if not 0 <= raw_start < raw_end <= len(self.original_text):
            raise ParseError("invalid_source_range")
        raw = self.original_text[raw_start:raw_end]
        if not raw or self.original_text[raw_start:raw_end] != raw:
            raise ParseError("source_mismatch")
        return Evidence(source="span", raw=raw, start=raw_start, end=raw_end)

    def verify(self, evidence: Evidence) -> bool:
        return (evidence.source == "span" and evidence.start is not None
                and evidence.end is not None
                and 0 <= evidence.start < evidence.end <= len(self.original_text)
                and self.original_text[evidence.start:evidence.end] == evidence.raw)


def _protect(text: str, start: int, known_names: Iterable[str]) -> tuple[SourceSpan, ...]:
    found = [SourceSpan(m.start(), m.end()) for m in _OPAQUE.finditer(text, start)]
    quote_start: int | None = None
    for index in range(start, len(text)):
        if text[index] in {'"', "'", "“", "”", "‘", "’"}:
            if quote_start is None:
                quote_start = index
            else:
                found.append(SourceSpan(quote_start, index + 1))
                quote_start = None
    if quote_start is not None:
        found.append(SourceSpan(quote_start, len(text)))
    for name in known_names:
        if not name:
            continue
        offset = start
        while (index := text.find(name, offset)) >= 0:
            found.append(SourceSpan(index, index + len(name)))
            offset = index + len(name)
    found.sort(key=lambda span: (span.start, -span.end))
    merged: list[SourceSpan] = []
    for span in found:
        if merged and span.start <= merged[-1].end:
            merged[-1] = SourceSpan(merged[-1].start, max(merged[-1].end, span.end))
        else:
            merged.append(span)
    return tuple(merged)


def _nfc_piece(piece: str, offset: int) -> tuple[str, list[SourceSpan]]:
    """Incremental NFC accounts for Hangul Jamo and combining-mark composition."""
    value = ""
    mapping: list[SourceSpan] = []
    for index, _char in enumerate(piece):
        updated = unicodedata.normalize("NFC", piece[:index + 1])
        common = 0
        while common < min(len(value), len(updated)) and value[common] == updated[common]:
            common += 1
        merged_start = mapping[common].start if common < len(mapping) else offset + index
        mapping = mapping[:common] + [SourceSpan(merged_start, offset + index + 1)
                                      for _ in updated[common:]]
        value = updated
    return value, mapping


class InputNormalizer:
    version = "1.2.0-p3"

    def __init__(self, *, max_codepoints: int = 2000) -> None:
        self.max_codepoints = max_codepoints

    def normalize(
        self, original_text: str, *, invocation: str | None = None,
        known_names: Iterable[str] = (), request_id: str = "",
        trace: TracePort | None = None,
    ) -> NormalizedInput:
        started = time.monotonic()
        if not isinstance(original_text, str) or len(original_text) > self.max_codepoints:
            raise ParseError("input_too_long")
        start = 0
        while start < len(original_text) and original_text[start] in " \t":
            start += 1
        removed = None
        if invocation is not None:
            if not invocation or not original_text.startswith(invocation, start):
                raise ParseError("invalid_invocation")
            removed = SourceSpan(0, start + len(invocation))
            start += len(invocation)
        protected = _protect(original_text, start, known_names)
        output: list[str] = []
        source: list[SourceSpan] = []
        index = start
        protected_index = 0
        while index < len(original_text):
            if protected_index < len(protected) and index == protected[protected_index].start:
                span = protected[protected_index]
                output.extend(original_text[span.start:span.end])
                source.extend(SourceSpan(k, k + 1) for k in range(span.start, span.end))
                index = span.end
                protected_index += 1
                continue
            if original_text[index].isspace():
                end = index + 1
                while end < len(original_text) and original_text[end].isspace() and (
                    protected_index == len(protected) or end < protected[protected_index].start
                ):
                    end += 1
                if output and end < len(original_text):
                    output.append(" ")
                    source.append(SourceSpan(index, end))
                index = end
                continue
            end = index + 1
            while end < len(original_text) and not original_text[end].isspace() and (
                protected_index == len(protected) or end < protected[protected_index].start
            ):
                end += 1
            normalized, spans = _nfc_piece(original_text[index:end], index)
            output.extend(normalized)
            source.extend(spans)
            index = end
        if not output:
            raise ParseError("empty_input")
        result = NormalizedInput(original_text, "".join(output), tuple(source),
                                 protected, removed)
        if trace is not None:
            trace.event(request_id, "code.normalize", {
                "version": self.version, "rules": "protected-whitespace-nfc",
                "changed": result.normalized_text != original_text,
                "duration_ms": round((time.monotonic() - started) * 1000, 3),
                "protected_count": len(protected),
            })
        return result
