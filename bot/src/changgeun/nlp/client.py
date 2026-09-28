"""TLS decision client: no retries, redirect following, or provider fallback."""

from __future__ import annotations

import asyncio
import json
import ssl
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from changgeun.domain.models import DomainError
from changgeun.nlp.pipeline import Selection
from changgeun.observability import Metrics


class GatewayClient:
    def __init__(
        self, config: dict[str, Any], *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.transport = transport
        self.provider = str(config["provider"])
        if self.provider != "jev-api":
            raise ValueError("Discord gateway client supports Jev API only")
        self.profile_id = str(config["profile_id"])
        self.config_hash = str(config["config_hash"])
        self.base_url = str(config["base_url"]).rstrip("/")
        url = urlsplit(self.base_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("verified internal HTTPS endpoint required")
        self.token_file = Path(config["token_file"])
        self.ca_file = Path(config["ca_file"])
        self.token = self.token_file.read_text().strip()
        self.tls = ssl.create_default_context(cafile=str(self.ca_file))
        self.metrics = Metrics()
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()
        self._ready_lock = asyncio.Lock()
        self._ready_binding: tuple[Any, ...] | None = None
        self._ready_until = 0.0
        self._credential_version = self._file_version()
        self._consecutive_failures = 0
        self._blocked_until = 0.0
        self._closed = False

    def _file_version(self) -> tuple[int, int]:
        return self.token_file.stat().st_mtime_ns, self.ca_file.stat().st_mtime_ns

    async def _http(self) -> httpx.AsyncClient:
        async with self._client_lock:
            if self._closed:
                raise DomainError("inference_temporarily_unavailable")
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    transport=self.transport,
                    verify=self.tls,
                    timeout=4,
                    limits=httpx.Limits(
                        max_connections=5, max_keepalive_connections=5, keepalive_expiry=15
                    ),
                    trust_env=False,
                    follow_redirects=False,
                )
            return self._client

    async def close(self) -> None:
        self._ready_until = 0
        async with self._client_lock:
            self._closed = True
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def _bounded_json(self, response: httpx.Response) -> dict[str, Any]:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            if len(body) + len(chunk) > 65536:
                raise DomainError("inference_response_too_large")
            body.extend(chunk)
        result = json.loads(body)
        if not isinstance(result, dict):
            raise DomainError("invalid_inference_response")
        return result

    async def ready(self) -> None:
        observed_at = time.monotonic()
        try:
            await self._ready()
        finally:
            self.metrics.duration("gateway_ready", time.monotonic() - observed_at)

    async def parser_ready(self, llm_profile: str) -> None:
        """Fail startup closed when the explicitly selected v2 profile is absent."""
        if llm_profile not in {"disabled", "gpt-5-nano"}:
            raise ValueError("invalid parser LLM profile")
        await self.ready()
        client = await self._http()
        async with client.stream(
            "GET", self.base_url + "/health",
            headers={"Authorization": "Bearer " + self.token}, timeout=2,
        ) as response:
            response.raise_for_status()
            result = await self._bounded_json(response)
        if (result.get("ready"), result.get("provider"), result.get("profile_id"),
                result.get("config_hash"), result.get("parser_v2_ready"),
                result.get("parser_llm_profile")) != (
                    True, self.provider, self.profile_id, self.config_hash,
                    True, llm_profile):
            raise DomainError("inference_profile_mismatch")

    async def usage(self) -> dict[str, int]:
        """Authenticated bounded read; shared-run values are never guild attribution."""
        if self._closed or self._file_version() != self._credential_version:
            raise DomainError("inference_profile_mismatch")
        client = await self._http()
        async with client.stream(
            "GET",
            self.base_url + "/v1/usage",
            headers={"Authorization": "Bearer " + self.token},
            timeout=2,
        ) as response:
            response.raise_for_status()
            result = await self._bounded_json(response)
        if (
            result.get("scope"),
            result.get("provider"),
            result.get("profile_id"),
            result.get("config_hash"),
        ) != ("shared_run", self.provider, self.profile_id, self.config_hash):
            raise DomainError("inference_profile_mismatch")
        calls, limit = result.get("reserved_calls"), result.get("limit")
        if type(calls) is not int or type(limit) is not int or not 0 <= calls <= limit:
            raise DomainError("invalid_inference_response")
        return {"reserved_calls": calls, "limit": limit}

    async def _ready(self) -> None:
        if self._closed:
            raise DomainError("inference_temporarily_unavailable")
        if self._file_version() != self._credential_version:
            self._ready_until = 0
            raise DomainError("inference_profile_mismatch")
        binding = (self.provider, self.profile_id, self.config_hash, self._credential_version)
        if self._ready_binding == binding and time.monotonic() < self._ready_until:
            return
        async with self._ready_lock:
            if self._ready_binding == binding and time.monotonic() < self._ready_until:
                return
            self._ready_until = 0
            client = await self._http()
            async with client.stream(
                "GET",
                self.base_url + "/health",
                headers={"Authorization": "Bearer " + self.token},
                timeout=2,
            ) as response:
                response.raise_for_status()
                result = await self._bounded_json(response)
            if not result.get("ready") or (
                result.get("provider"),
                result.get("profile_id"),
                result.get("config_hash"),
            ) != (self.provider, self.profile_id, self.config_hash):
                raise DomainError("inference_profile_mismatch")
            self._ready_binding = binding
            self._ready_until = time.monotonic() + 2

    async def choose(self, payload: dict[str, Any], timeout: float) -> Selection:
        observed_at = time.monotonic()
        dispatched = False
        try:
            if self._closed:
                raise DomainError("inference_temporarily_unavailable")
            if self._file_version() != self._credential_version:
                self._ready_until = 0
                raise DomainError("inference_profile_mismatch")
            if observed_at < self._blocked_until:
                raise DomainError("inference_temporarily_unavailable")
            dispatched = True
            result = await self._choose(payload, timeout)
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            self.metrics.outcome("unknown_call")
            if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in {
                429,
                500,
                502,
                503,
                504,
            }:
                self._consecutive_failures += 1
                if self._consecutive_failures >= 3:
                    self._blocked_until = time.monotonic() + 5
            else:
                self._consecutive_failures = 0
            raise
        except BaseException:
            if dispatched:
                self.metrics.outcome("unknown_call")
            raise
        else:
            self._consecutive_failures = 0
            self._blocked_until = 0
            return result
        finally:
            self.metrics.duration("gateway_choose", time.monotonic() - observed_at)

    async def _choose(self, payload: dict[str, Any], timeout: float) -> Selection:
        client = await self._http()
        async with client.stream(
            "POST",
            self.base_url + "/v1/decide",
            json=payload,
            headers={"Authorization": "Bearer " + self.token},
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            result = await self._bounded_json(response)
        if (
            result.get("schema_version"),
            result.get("provider"),
            result.get("profile_id"),
            result.get("config_hash"),
            result.get("request_id"),
            result.get("stage_index"),
        ) != (
            "1.2",
            self.provider,
            self.profile_id,
            self.config_hash,
            payload["request_id"],
            payload["stage_index"],
        ):
            raise DomainError("inference_response_binding_mismatch")
        usage = result["usage"]
        for key in ("task", "context_snapshot_id", "candidate_set_id"):
            if result.get(key) != payload[key]:
                raise DomainError("inference_response_binding_mismatch")
        total = payload["stage_index"]
        new_calls = usage.get("provider_calls")
        if (
            new_calls not in {0, 1}
            or usage.get("request_provider_calls_total") != total
            or usage.get("questions") != new_calls
            or usage.get("request_questions_total") != total
            or usage.get("request_stages_total") != total
        ):
            raise DomainError("inference_usage_mismatch")
        if self.provider == "jev-api":
            if (
                usage.get("forward_passes") is not None
                or usage.get("request_forward_passes_total") is not None
                or usage.get("forward_passes_source") != "unavailable"
            ):
                raise DomainError("inference_forward_provenance_mismatch")
        self.metrics.outcome("new_call" if new_calls == 1 else "reused_call")
        reported_tokens = usage.get("input_tokens")
        tokens = reported_tokens if type(reported_tokens) is int and reported_tokens >= 0 else None
        return Selection(result["selected_id"], result["probabilities"], total, tokens)
