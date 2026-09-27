"""Authenticated gateway entry point; external bindings require TLS."""

from __future__ import annotations

import argparse
import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from changgeun_inference.config import read_profile
from changgeun_inference.contracts import DecisionRequest
from changgeun_inference.ledger import Ledger
from changgeun_inference.providers import HostedProvider, MockProvider, Provider
from changgeun_inference.service import DecisionService, ServiceError


class RequestBoundary:
    """Authenticate before JSON parsing and bound even chunked request bodies."""

    def __init__(self, app: ASGIApp, token: str, max_body: int = 32768) -> None:
        self.app, self.token, self.max_body = app, token, max_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        values = [value for key, value in scope["headers"] if key.lower() == b"authorization"]
        if len(values) != 1 or not hmac.compare_digest(
            values[0], ("Bearer " + self.token).encode()
        ):
            await JSONResponse({"detail": "unauthorized"}, status_code=401)(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_body:
                await JSONResponse({"detail": "body_too_large"}, status_code=413)(
                    scope, receive, send
                )
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)


def create_app(service: DecisionService, token: str) -> FastAPI:
    if len(token) < 32:
        raise ValueError("internal token must have at least 32 characters")

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        yield
        await service.drain()

    app = FastAPI(
        title="ChangGeun decision gateway",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(RequestBoundary, token=token)

    def authenticate(authorization: str) -> None:
        if not hmac.compare_digest(authorization, "Bearer " + token):
            raise HTTPException(401, "unauthorized")

    @app.get("/health")
    async def health(authorization: str = Header(default="")) -> dict[str, Any]:
        authenticate(authorization)
        return {
            "ready": not service.closed,
            "provider": service.provider_name,
            "profile_id": service.profile_id,
            "config_hash": service.config_hash,
        }

    @app.post("/v1/decide")
    async def decide(
        request: DecisionRequest, authorization: str = Header(default="")
    ) -> dict[str, Any]:
        authenticate(authorization)
        try:
            return await service.decide(request)
        except ServiceError as exc:
            raise HTTPException(exc.status, exc.code) from exc

    return app


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--tombstones", type=Path)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--tls-cert", type=Path)
    parser.add_argument("--tls-key", type=Path)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1"} and not (args.tls_cert and args.tls_key):
        parser.error("external binding requires TLS certificate and key")
    config, config_hash = read_profile(args.profile, allow_mock=args.test_mode)
    provider: Provider
    if config["provider"] == "jev-api":
        hosted = config["hosted"]
        provider = HostedProvider(
            hosted["endpoint"], hosted["model"], os.environ.get("JEV_HOSTED_API_KEY", "")
        )
        max_calls = hosted["max_calls_per_run"]
    else:
        provider = MockProvider()
        max_calls = 100000
    service = DecisionService(
        provider,
        Ledger(args.ledger, args.tombstones),
        provider_name=config["provider"],
        profile_id=config["profile_id"],
        config_hash=config_hash,
        run_id=args.run_id,
        max_run_calls=max_calls,
    )
    app = create_app(service, args.token_file.read_text().strip())
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=1,
        access_log=False,
        ssl_certfile=str(args.tls_cert) if args.tls_cert else None,
        ssl_keyfile=str(args.tls_key) if args.tls_key else None,
    )


if __name__ == "__main__":
    main()
