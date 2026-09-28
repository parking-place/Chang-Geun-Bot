"""Gateway-only LLM profile and conservative GPT-5 nano price bound."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from changgeun_inference.contracts_v2 import ParseCall, TokenUsage

PRICE_VERSION = "gpt-5-nano-standard-2026-09-28"
MAX_INPUT_BYTES = 196608
INPUT_MICRO_USD_HUNDREDTHS = 5    # $0.05 / 1M input tokens
OUTPUT_MICRO_USD_HUNDREDTHS = 40  # $0.40 / 1M output tokens


@dataclass(frozen=True)
class LLMProfile:
    profile_id: str
    model_id: str | None
    max_rewrite_tokens: int = 1024
    max_full_tokens: int = 2048
    price_version: str = PRICE_VERSION
    api_key: str | None = field(default=None, repr=False)

    @property
    def enabled(self) -> bool:
        return self.model_id is not None

    def max_tokens(self, call: ParseCall) -> int:
        if call.operation == "rewrite":
            return self.max_rewrite_tokens
        if call.operation == "full_parse":
            return self.max_full_tokens
        raise ValueError("not an LLM operation")

    def quote(self, call: ParseCall, payload: dict[str, Any]) -> int:
        if not self.enabled or not self.api_key:
            raise ValueError("LLM disabled")
        body_bytes = len(json.dumps(payload, ensure_ascii=False,
                                    separators=(",", ":")).encode())
        if body_bytes > MAX_INPUT_BYTES:
            raise ValueError("LLM input too large")
        # Conservative upper bound: at most two tokens per input byte, no cached discount.
        return ((body_bytes * 2 * INPUT_MICRO_USD_HUNDREDTHS
                 + self.max_tokens(call) * OUTPUT_MICRO_USD_HUNDREDTHS + 99) // 100)

    def actual_micro_usd(self, usage: TokenUsage) -> int | None:
        if usage.input_tokens is None or usage.output_tokens is None:
            return None
        return ((usage.input_tokens * INPUT_MICRO_USD_HUNDREDTHS
                 + usage.output_tokens * OUTPUT_MICRO_USD_HUNDREDTHS + 99) // 100)


def profile_from_environment(values: Mapping[str, str]) -> LLMProfile:
    deprecated = {"OPENAI_FALLBACK_MODEL", "LLM_FALLBACK_TIMEOUT_SECONDS",
                  "LLM_FALLBACK_MAX_OUTPUT_TOKENS"}
    if deprecated.intersection(values):
        raise ValueError("deprecated LLM setting conflict")
    selected = values.get("LLM_FALLBACK", "gpt-5-nano")
    if selected == "disabled":
        return LLMProfile("disabled", None)
    if selected in {"gemini", "luna"}:
        raise ValueError("LLM profile not implemented")
    if selected != "gpt-5-nano":
        raise ValueError("unknown LLM profile")
    key = values.get("OPENAI_API_KEY", "")
    if not key:
        raise ValueError("OpenAI key missing on gateway")
    return LLMProfile("gpt-5-nano", "gpt-5-nano", api_key=key)
