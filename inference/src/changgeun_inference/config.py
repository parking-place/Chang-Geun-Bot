"""Startup-only explicit profiles. Credentials are excluded from configuration hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml


def read_profile(path: Path, *, allow_mock: bool = False) -> tuple[dict[str, Any], str]:
    config = yaml.safe_load(path.read_text())
    if not isinstance(config, dict):
        raise ValueError("profile must be a mapping")
    required = {
        "profile_id",
        "provider",
        "api_schema_version",
        "automatic_provider_retries",
        "automatic_fallback",
        "max_provider_calls_per_request",
    }
    allowed = required | {"hosted", "mock", "decision"}
    if required - config.keys() or config.keys() - allowed:
        raise ValueError("unknown/missing profile fields")
    if (
        config["api_schema_version"] != "1.2"
        or config["automatic_provider_retries"] != 0
        or config["automatic_fallback"] is not False
        or config["max_provider_calls_per_request"] != 3
    ):
        raise ValueError("unsafe profile policy")
    provider = config["provider"]
    if provider not in {"jev-api", "mock"}:
        raise ValueError("unknown provider")
    if provider == "mock" and not allow_mock:
        raise ValueError("mock requires explicit test mode")
    if provider == "jev-api" and ("hosted" not in config or "mock" in config):
        raise ValueError("Jev API requires only hosted settings")
    if provider == "mock" and "hosted" in config:
        raise ValueError("test double cannot contain hosted settings")
    if "<REPLACE_" in json.dumps(config):
        raise ValueError("unresolved profile placeholder")
    decision = config.get("decision", {})
    if decision:
        if (
            set(decision) != {"prompt_version", "confidence_threshold", "margin_threshold"}
            or not isinstance(decision["prompt_version"], str)
            or not 0.5 <= decision["confidence_threshold"] <= 1
            or not 0 <= decision["margin_threshold"] < 1
        ):
            raise ValueError("invalid decision calibration")
    if provider == "jev-api":
        hosted = config.get("hosted", {})
        url = urlsplit(hosted.get("endpoint", ""))
        # Audited official wire endpoint; arbitrary hosts/redirects are never accepted.
        if (
            url.scheme != "https"
            or url.netloc != "api.typesafe.ai"
            or url.path != "/v1/systemone"
            or url.query
            or url.fragment
        ):
            raise ValueError("unverified hosted endpoint")
        required_hosted = {"endpoint", "model", "api_key_env", "max_calls_per_run"}
        if (
            not required_hosted <= hosted.keys()
            or set(hosted) - required_hosted - {"run_purpose"}
            or hosted["api_key_env"] != "JEV_HOSTED_API_KEY"
            or type(hosted["max_calls_per_run"]) is not int
            or not 1 <= hosted["max_calls_per_run"] <= 3000
        ):
            raise ValueError("invalid hosted run budget/fields")
        purpose = hosted.get("run_purpose", "smoke")
        if purpose not in {"smoke", "development-evaluation", "release-evaluation"}:
            raise ValueError("invalid hosted run purpose")
        if hosted["max_calls_per_run"] > 20 and (
            purpose == "smoke" or not config["profile_id"].startswith("eval-")
        ):
            raise ValueError("large budget requires an explicit evaluation profile/purpose")
    serialized = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return config, hashlib.sha256(serialized.encode()).hexdigest()
