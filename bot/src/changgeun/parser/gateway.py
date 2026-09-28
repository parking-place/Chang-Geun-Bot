"""Internal parser-api-v2 session over the existing authenticated TLS client."""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

from changgeun.nlp.client import GatewayClient
from changgeun.parser.contracts import ParseError
from changgeun.parser.trace import SafeTraceRecorder


class ParserSession:
    def __init__(self, gateway: GatewayClient, *, request_id: str,
                 scope_hash: str, original_text: str, seconds: float = 35.0,
                 trace: SafeTraceRecorder | None = None) -> None:
        created = time.time()
        self.gateway = gateway
        self.trace = trace
        self.root: dict[str, Any] = {
            "schema_version": "parser-api-v2", "request_id": request_id,
            "scope_hash": scope_hash,
            "original_hash": hashlib.sha256(original_text.encode()).hexdigest(),
            "config_hash": gateway.config_hash,
            "created_at": created, "expires_at": created + min(seconds, 35.0),
        }

    async def call(
        self, operation: str, state: dict[str, Any], *,
        pass_id: str | None = None, stage_index: int | None = None,
        questions: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.gateway._closed or self.gateway._file_version() != (
            self.gateway._credential_version
        ):
            raise ParseError("gateway_credentials_changed")
        remaining = self.root["expires_at"] - time.time()
        if remaining <= 0:
            raise ParseError("deadline_expired")
        call_id = secrets.token_urlsafe(18)
        payload = {"root": self.root, "call_id": call_id, "operation": operation,
                   "pass_id": pass_id, "stage_index": stage_index, "state": state,
                   "questions": questions or {}, "output_schema": output_schema}
        client = await self.gateway._http()
        try:
            async with client.stream(
                "POST", self.gateway.base_url + "/v2/parse", json=payload,
                headers={"Authorization": "Bearer " + self.gateway.token},
                timeout=min(remaining, 12.0),
            ) as response:
                response.raise_for_status()
                result = await self.gateway._bounded_json(response)
        except Exception:
            if self.trace is not None:
                self.trace.event(self.root["request_id"], "model.call_unknown",
                                 {"operation": operation, "pass_id": pass_id,
                                  "stage_index": stage_index})
            raise
        if (result.get("schema_version") != "parser-api-v2"
                or result.get("request_id") != self.root["request_id"]
                or result.get("call_id") != call_id
                or result.get("operation") != operation):
            raise ParseError("gateway_response_binding_mismatch")
        if self.trace is not None and type(result.get("attempt_no")) is int:
            usage = result.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
            usage_status = ("reported" if type(input_tokens) is int and
                            type(output_tokens) is int else "partial" if
                            type(input_tokens) is int or type(output_tokens) is int else "unknown")
            self.trace.call(
                self.root["request_id"], call_id, result["attempt_no"], operation,
                pass_id, stage_index, remote_attempted=result.get("remote_attempted") is True,
                status=result["status"], usage={
                    "status": usage_status,
                    "input_tokens": input_tokens if type(input_tokens) is int else None,
                    "output_tokens": output_tokens if type(output_tokens) is int else None,
                    "cached_tokens": usage.get("cached_input_tokens"),
                    "reasoning_tokens": usage.get("reasoning_tokens"),
                },
            )
        if result.get("status") != "completed" or not isinstance(result.get("result"), dict):
            raise ParseError("gateway_provider_failed")
        return result["result"]  # type: ignore[no-any-return]

    async def cancel(self) -> None:
        client = await self.gateway._http()
        async with client.stream(
            "POST", self.gateway.base_url + "/v2/cancel",
            json={"request_id": self.root["request_id"]},
            headers={"Authorization": "Bearer " + self.gateway.token},
            timeout=2.0,
        ) as response:
            response.raise_for_status()
