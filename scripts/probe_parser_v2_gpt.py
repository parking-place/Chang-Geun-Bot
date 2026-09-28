#!/usr/bin/env python3
"""One synthetic Jev→GPT rewrite on the active budgeted LXC gateway.

Requires explicit opt-in. Uses no Discord user content or service execution.
There is no retry after a network failure or unknown provider result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REWRITE_SCHEMA: dict[str, object] = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": [
            "rewritten", "unchanged", "needs_clarification", "unsupported",
            "multiple_intents"]},
        "rewritten_text": {"type": ["string", "null"]},
        "unresolved_references": {"type": "array", "items": {"type": "string"}},
        "question": {"type": ["string", "null"]},
    },
    "required": ["status", "rewritten_text", "unresolved_references", "question"],
}
FULL_PARSE_SCHEMA: dict[str, object] = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": [
            "parsed", "needs_clarification", "unsupported", "multiple_intents"]},
        "plan": {"anyOf": [
            {"type": "object", "additionalProperties": False,
             "properties": {
                 "command": {"type": "string", "enum": ["C01"]},
                 "arguments": {"type": "object", "additionalProperties": False,
                               "properties": {}, "required": []},
             }, "required": ["command", "arguments"]},
            {"type": "null"},
        ]},
        "unresolved_arguments": {"type": "array", "items": {"type": "string"}},
        "question": {"type": ["string", "null"]},
    },
    "required": ["status", "plan", "unresolved_arguments", "question"],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--operation", choices=("rewrite", "full_parse"), required=True)
    parser.add_argument("--one-gpt-call", action="store_true", required=True)
    args = parser.parse_args()
    if args.base_url != "https://127.0.0.1:8443":
        parser.error("only the audited loopback TLS gateway is allowed")
    token = args.token_file.read_text().strip()
    context = ssl.create_default_context(cafile=str(args.ca_file))

    def request(path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
        message = urllib.request.Request(
            args.base_url + path, data=data,
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/json"},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(message, context=context, timeout=15) as response:
                body = response.read(65537)
                if len(body) > 65536:
                    raise ValueError("gateway response too large")
                result = json.loads(body)
                if not isinstance(result, dict):
                    raise ValueError("gateway response is not an object")
                return result
        except urllib.error.HTTPError as exc:
            raise RuntimeError("gateway HTTP status " + str(exc.code)) from None

    health = request("/health")
    if health.get("parser_v2_ready") is not True or (
        health.get("parser_llm_profile") != "gpt-5-nano"
    ):
        raise SystemExit("GPT validation profile is not ready")
    before = request("/v2/usage")
    reserved = before.get("gpt_reserved_micro_usd")
    limit = before.get("gpt_limit_micro_usd")
    if type(reserved) is not int or limit != 1_000_000 or limit - reserved < 20_000:
        raise SystemExit("cumulative GPT validation budget insufficient")
    message = ("리슷 보여줘" if args.operation == "rewrite"
               else "저장된 재생목록 보여줘")
    now = time.time()
    root = {"schema_version": "parser-api-v2",
            "request_id": "gpt-probe-" + uuid.uuid4().hex,
            "scope_hash": hashlib.sha256(b"synthetic-gpt-validation-only").hexdigest(),
            "original_hash": hashlib.sha256(message.encode()).hexdigest(),
            "config_hash": health["config_hash"],
            "created_at": now, "expires_at": now + 35}
    initial = request("/v2/parse", {
        "root": root, "call_id": "initial-" + uuid.uuid4().hex,
        "operation": "command_select", "pass_id": "initial", "stage_index": 1,
        "state": {"message": message, "original_message": message,
                  "normalized_message": message, "pass_id": "initial",
                  "message_variant": "normalized"},
        "questions": {
            "input_kind": {"type": "choice", "instructions": "실행 요청인지 고르세요.",
                           "criteria": {"single": "명령 하나", "multiple": "명령 여러 개",
                                        "not_request": "명령 아님", "unclear": "불명확"}},
            "command": {"type": "choice", "instructions": "허용 명령만 고르세요.",
                        "criteria": {"C01": "저장된 재생목록 조회",
                                     "__NONE__": "해당 명령 없음"}},
        },
    })
    if initial.get("status") != "completed":
        raise SystemExit("initial Jev call did not complete; GPT was not called")
    try:
        final = request("/v2/parse", {
            "root": root, "call_id": args.operation + "-" + uuid.uuid4().hex,
            "operation": args.operation, "state": ({
                "original_message": message, "normalized_message": message,
                "initial_failure": "interpretation_unclear"}
                if args.operation == "rewrite" else {
                    "original_message": message, "normalized_message": message,
                    "commands": {"C01": "저장된 재생목록 조회"},
                    "scope": "reparse"}),
            "output_schema": (REWRITE_SCHEMA if args.operation == "rewrite"
                              else FULL_PARSE_SCHEMA),
        })
    except RuntimeError as exc:
        after = request("/v2/usage")
        print(json.dumps({"gpt_outcome": str(exc),
                          "gpt_reserved_before": reserved,
                          "gpt_reserved_after": after.get("gpt_reserved_micro_usd"),
                          "gpt_actual_micro_usd": after.get("gpt_actual_micro_usd")}))
        raise SystemExit(1) from None
    after = request("/v2/usage")
    result = final.get("result")
    text = result.get("rewritten_text") if isinstance(result, dict) else None
    plan = result.get("plan") if isinstance(result, dict) else None
    print(json.dumps({
        "operation": args.operation,
        "initial_status": initial.get("status"),
        "gpt_status": final.get("status"), "gpt_error_code": final.get("error_code"),
        "gpt_result_status": result.get("status") if isinstance(result, dict) else None,
        "rewrite_mentions_playlist": isinstance(text, str) and "목록" in text,
        "parsed_command": plan.get("command") if isinstance(plan, dict) else None,
        "gpt_remote_attempted": final.get("remote_attempted"),
        "gpt_usage": final.get("usage"),
        "gpt_reserved_before": reserved,
        "gpt_reserved_after": after.get("gpt_reserved_micro_usd"),
        "gpt_actual_micro_usd": after.get("gpt_actual_micro_usd"),
        "gpt_unknown_calls": after.get("gpt_unknown_calls"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
