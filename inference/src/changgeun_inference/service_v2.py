"""Bounded parser dispatch; no operation can grant its own budget."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Callable
from typing import Any, Protocol

from changgeun_inference.contracts_v2 import CallResponse, ParseCall, TokenUsage
from changgeun_inference.ledger import LedgerError
from changgeun_inference.ledger_v2 import ParserLedger
from changgeun_inference.service import ServiceError


class ParserProvider(Protocol):
    async def parse(self, call: ParseCall, timeout: float) -> tuple[dict[str, Any],
                                                                    TokenUsage, str | None]: ...


class ParserService:
    def __init__(
        self, provider: ParserProvider, ledger: ParserLedger, *, config_hash: str,
        run_id: str, max_jev_run_calls: int,
        llm_reservation: Callable[[ParseCall], int] | None = None,
        slot: asyncio.Semaphore | None = None,
    ) -> None:
        self.provider, self.ledger = provider, ledger
        self.config_hash, self.run_id = config_hash, run_id
        self.max_jev_run_calls, self.llm_reservation = max_jev_run_calls, llm_reservation
        self.slot = slot or asyncio.Semaphore(1)
        self.pending = 0
        self.closed = False
        self.inflight: dict[tuple[str, str], tuple[str, asyncio.Task[dict[str, Any]]]] = {}
        self.inflight_lock = asyncio.Lock()

    async def parse(self, call: ParseCall) -> dict[str, Any]:
        if call.root.config_hash != self.config_hash:
            raise ServiceError("profile_binding_mismatch")
        if self.closed:
            raise ServiceError("service_draining", 503)
        key = (call.root.request_id, call.call_id)
        body_hash = hashlib.sha256(call.model_dump_json().encode()).hexdigest()
        owner = False
        async with self.inflight_lock:
            if key in self.inflight:
                previous_hash, task = self.inflight[key]
                if previous_hash != body_hash:
                    raise ServiceError("call_body_conflict")
            else:
                try:
                    cached = self.ledger.lookup(call)
                except LedgerError as exc:
                    raise ServiceError(exc.code) from exc
                if cached is not None:
                    return CallResponse.model_validate({**cached, "cache_hit": True}).model_dump()
                if self.pending >= 5:
                    raise ServiceError("queue_full", 429)
                self.pending += 1
                owner = True
                task = asyncio.create_task(self._queued(call))
                self.inflight[key] = (body_hash, task)
                task.add_done_callback(lambda finished: self._done(key, finished))
        remaining = call.root.expires_at - time.time()
        try:
            if remaining <= 0:
                raise ServiceError("deadline_expired", 408)
            result = await asyncio.wait_for(asyncio.shield(task), remaining)
            return result if owner else CallResponse.model_validate(
                {**result, "cache_hit": True}).model_dump()
        except TimeoutError as exc:
            raise ServiceError("deadline_expired", 408) from exc

    async def _queued(self, call: ParseCall) -> dict[str, Any]:
        try:
            remaining = call.root.expires_at - time.time()
            if remaining <= 0:
                raise ServiceError("deadline_expired", 408)
            async with asyncio.timeout(remaining):
                async with self.slot:
                    return await self._dispatch(call)
        except TimeoutError as exc:
            raise ServiceError("deadline_expired", 408) from exc
        finally:
            self.pending -= 1

    def _done(self, key: tuple[str, str], task: asyncio.Task[dict[str, Any]]) -> None:
        self.inflight.pop(key, None)
        if not task.cancelled():
            task.exception()

    async def _dispatch(self, call: ParseCall) -> dict[str, Any]:
        remaining = call.root.expires_at - time.time()
        if remaining <= 0:
            raise ServiceError("deadline_expired", 408)
        is_llm = call.operation in {"rewrite", "full_parse"}
        if is_llm and self.llm_reservation is None:
            raise ServiceError("llm_disabled")
        cost = self.llm_reservation(call) if is_llm and self.llm_reservation else 0
        try:
            attempt = self.ledger.reserve(call, run_id=self.run_id,
                                          max_jev_run_calls=self.max_jev_run_calls,
                                          llm_cost_micro_usd=cost)
        except LedgerError as exc:
            raise ServiceError(exc.code) from exc
        try:
            self.ledger.mark_attempted(call)
            cap = 10.0 if is_llm else 5.0
            timeout = min(cap, call.root.expires_at - time.time())
            if timeout <= 0:
                raise ServiceError("deadline_expired", 408)
            result, usage, model = await asyncio.wait_for(self.provider.parse(call, timeout),
                                                            timeout=timeout)
            if call.root.expires_at <= time.time():
                raise ServiceError("late_result_discarded", 408)
            if not isinstance(result, dict):
                raise ServiceError("invalid_provider_result", 502)
            response = CallResponse(request_id=call.root.request_id, call_id=call.call_id,
                                    operation=call.operation, attempt_no=attempt,
                                    remote_attempted=True, status="completed",
                                    result=result, usage=usage, model=model).model_dump()
            self.ledger.finish(call, response)
            return response
        except BaseException as exc:
            try:
                self.ledger.finish(call, None)
            except LedgerError:
                pass
            if isinstance(exc, ServiceError):
                raise
            if isinstance(exc, TimeoutError):
                raise ServiceError("provider_timeout", 408) from exc
            if isinstance(exc, LedgerError):
                raise ServiceError(exc.code) from exc
            raise ServiceError("provider_failed", 502) from exc

    def cancel(self, request_id: str) -> None:
        self.ledger.cancel(request_id)

    def drain(self) -> None:
        self.closed = True
