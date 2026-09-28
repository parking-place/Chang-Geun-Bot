import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from changgeun_inference.contracts import DecisionRequest
from changgeun_inference.contracts_v2 import CallResponse, ParseCall, RootRequest, TokenUsage


def root():
    return RootRequest(request_id="request", scope_hash="a"*64, original_hash="b"*64,
                       config_hash="c"*64, created_at=100.0, expires_at=135.0)


def test_versions_and_deadlines_do_not_silently_migrate():
    with pytest.raises(ValidationError):
        DecisionRequest.model_validate(root().model_dump())
    for end in (136.0, float("nan"), float("inf"), 100.0):
        with pytest.raises(ValidationError):
            RootRequest.model_validate({**root().model_dump(), "expires_at": end})


def test_batched_questions_are_one_call_and_pass_is_explicit():
    questions = {key: {"type": "choice", "instructions": "Select", "criteria": {
        "a": "A", "__NONE__": "No match"}} for key in ("input_kind", "command")}
    call = ParseCall(root=root(), call_id="call", operation="command_select",
                     pass_id="initial", stage_index=1, state={}, questions=questions)
    assert len(call.questions) == 2
    for changes in ({"stage_index": 2}, {"pass_id": None}, {"operation": "rewrite"}):
        with pytest.raises(ValidationError):
            ParseCall.model_validate({**call.model_dump(), **changes})


def test_limits_never_trim_actual_list_and_usage_is_not_fabricated():
    with pytest.raises(ValidationError):
        ParseCall(root=root(), call_id="call", operation="argument_select",
                  pass_id="initial", stage_index=2, state={}, questions={"arg": {
                      "type": "choice", "instructions": "Select",
                      "criteria": {str(n): "row" for n in range(256)}}})
    assert TokenUsage().total_tokens is None
    for invalid in ({"input_tokens": True}, {"input_tokens": 3, "cached_input_tokens": 4},
                    {"input_tokens": 3, "output_tokens": 2, "total_tokens": 6}):
        with pytest.raises(ValidationError):
            TokenUsage(**invalid)


def test_response_schema_matches_public_contract():
    schema = json.loads(Path('shared/schemas/parser-response-v2.json').read_text())
    schema.pop('$schema', None)
    assert schema == CallResponse.model_json_schema()
