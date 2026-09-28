#!/usr/bin/env python3
"""One synthetic parser-v2 Jev call through the active, budgeted TLS gateway.

Run only on DiscordBotLXC with explicit private credential/CA paths. This never
reads a hosted key, user message, DB, or GPT credential. No automatic retry.
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--case", choices=("ambiguous_list", "explicit_playlists"),
                        required=True)
    parser.add_argument("--one-budgeted-call", action="store_true", required=True)
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
        with urllib.request.urlopen(message, context=context, timeout=15) as response:
            if int(response.headers.get("content-length", "0")) > 65536:
                raise ValueError("gateway response too large")
            body = response.read(65537)
            if len(body) > 65536:
                raise ValueError("gateway response too large")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError("gateway response is not an object")
            return result

    health = request("/health")
    if health.get("parser_v2_ready") is not True or health.get("parser_llm_profile") != "disabled":
        raise SystemExit("parser v2 disabled profile is not ready")
    before = request("/v1/usage")
    used, limit = before.get("reserved_calls"), before.get("limit")
    if type(used) is not int or type(limit) is not int or used >= limit:
        raise SystemExit("shared Jev budget unavailable")
    message = {"ambiguous_list": "목록 보여줘",
               "explicit_playlists": "저장된 재생목록 보여줘"}[args.case]
    now = time.time()
    root_id = "probe-" + uuid.uuid4().hex
    call_id = "call-" + uuid.uuid4().hex
    questions = {
        "input_kind": {"type": "choice", "instructions": "실행 요청 하나인지 고르세요.",
                       "criteria": {"single": "명령 하나", "multiple": "명령 여러 개",
                                    "not_request": "명령이 아님", "unclear": "불명확"}},
        "command": {"type": "choice", "instructions": "허용 명령 하나만 고르세요.",
                    "criteria": {"C01": "저장된 재생목록을 조회", "C16": "대기열을 조회",
                                 "__NONE__": "해당 명령 없음"}},
    }
    payload = {
        "root": {"schema_version": "parser-api-v2", "request_id": root_id,
                 "scope_hash": hashlib.sha256(b"synthetic-evaluation-only").hexdigest(),
                 "original_hash": hashlib.sha256(message.encode()).hexdigest(),
                 "config_hash": health["config_hash"],
                 "created_at": now, "expires_at": now + 35},
        "call_id": call_id, "operation": "command_select", "pass_id": "initial",
        "stage_index": 1,
        "state": {"message": message, "original_message": message,
                  "normalized_message": message, "pass_id": "initial",
                  "message_variant": "normalized"},
        "questions": questions,
    }
    try:
        response = request("/v2/parse", payload)
        http_status = 200
    except urllib.error.HTTPError as exc:
        response, http_status = {}, exc.code
    after = request("/v1/usage")
    selected = None
    if response.get("status") == "completed":
        result = response.get("result")
        answers = result.get("answers") if isinstance(result, dict) else None
        if isinstance(answers, dict):
            selected = {name: answer.get("choice") for name, answer in answers.items()
                        if isinstance(answer, dict)}
    print(json.dumps({
        "case": args.case,
        "http_status": http_status, "status": response.get("status"),
        "error_code": response.get("error_code"), "selected": selected,
        "remote_attempted": response.get("remote_attempted"),
        "usage": response.get("usage"),
        "jev_reserved_before": used, "jev_reserved_after": after.get("reserved_calls"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
