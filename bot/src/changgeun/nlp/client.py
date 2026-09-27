"""TLS decision client: no retries, redirect following, or provider fallback."""

from __future__ import annotations

import ssl
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from changgeun.domain.models import DomainError
from changgeun.nlp.pipeline import Selection


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
        self.token = Path(config["token_file"]).read_text().strip()
        self.tls = ssl.create_default_context(cafile=str(config["ca_file"]))

    async def ready(self) -> None:
        async with httpx.AsyncClient(
            transport=self.transport,
            verify=self.tls,
            timeout=2,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            response = await client.get(
                self.base_url + "/health", headers={"Authorization": "Bearer " + self.token}
            )
            response.raise_for_status()
            result = response.json()
        if not result.get("ready") or (
            result.get("provider"),
            result.get("profile_id"),
            result.get("config_hash"),
        ) != (self.provider, self.profile_id, self.config_hash):
            raise DomainError("inference_profile_mismatch")

    async def choose(self, payload: dict[str, Any], timeout: float) -> Selection:
        async with httpx.AsyncClient(
            transport=self.transport,
            verify=self.tls,
            timeout=timeout,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                self.base_url + "/v1/decide",
                json=payload,
                headers={"Authorization": "Bearer " + self.token},
            )
            response.raise_for_status()
            if len(response.content) > 65536:
                raise DomainError("inference_response_too_large")
            result = response.json()
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
        return Selection(result["selected_id"], result["probabilities"], total)
