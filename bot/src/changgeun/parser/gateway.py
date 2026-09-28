"""Internal parser-api-v2 session over the existing authenticated TLS client."""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

from changgeun.nlp.client import GatewayClient
from changgeun.parser.contracts import ParseError


class ParserSession:
    def __init__(self, gateway: GatewayClient, *, request_id: str,
                 scope_hash: str, original_text: str, seconds: float = 35.0) -> None:
        created = time.time()
        self.gateway = gateway
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
        async with client.stream(
            "POST", self.gateway.base_url + "/v2/parse", json=payload,
            headers={"Authorization": "Bearer " + self.gateway.token},
            timeout=min(remaining, 12.0),
        ) as response:
            response.raise_for_status()
            result = await self.gateway._bounded_json(response)
        if (result.get("schema_version") != "parser-api-v2"
                or result.get("request_id") != self.root["request_id"]
                or result.get("call_id") != call_id
                or result.get("operation") != operation
                or result.get("status") != "completed"
                or not isinstance(result.get("result"), dict)):
            raise ParseError("gateway_response_binding_mismatch")
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
