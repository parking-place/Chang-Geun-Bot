"""One active dispatch, four pending requests; late results cannot be reused."""

from __future__ import annotations

import asyncio
import copy
import time
from typing import Any, Literal

from changgeun_inference.contracts import DecisionRequest, DecisionResponse
from changgeun_inference.ledger import Ledger, LedgerError, fingerprint
from changgeun_inference.providers import Provider


class ServiceError(Exception):
    def __init__(self, code: str, status: int = 409) -> None:
        self.code, self.status = code, status
        super().__init__(code)


class DecisionService:
    def __init__(
        self,
        provider: Provider,
        ledger: Ledger,
        *,
        provider_name: Literal["jev-api", "mock"],
        profile_id: str,
        config_hash: str,
        run_id: str,
        max_run_calls: int = 20,
    ) -> None:
        if provider_name not in {"jev-api", "mock"}:
            raise ValueError("only Jev API or an isolated mock is supported")
        self.provider, self.ledger = provider, ledger
        self.provider_name, self.profile_id, self.config_hash = (
            provider_name,
            profile_id,
            config_hash,
        )
        self.run_id, self.max_run_calls = run_id, max_run_calls
        self.slot = asyncio.Semaphore(1)
        self.inflight: dict[tuple[str, int], tuple[str, asyncio.Task[dict[str, Any]]]] = {}
        self.pending = 0
        self.closed = False

    async def decide(self, request: DecisionRequest) -> dict[str, Any]:
        if (request.provider, request.profile_id, request.config_hash) != (
            self.provider_name,
            self.profile_id,
            self.config_hash,
        ):
            raise ServiceError("profile_binding_mismatch")
        key, body_hash = (request.request_id, request.stage_index), fingerprint(request)
        owner = False
        if key in self.inflight:
            previous_hash, task = self.inflight[key]
            if previous_hash != body_hash:
                raise ServiceError("stage_body_conflict")
        else:
            try:
                cached = self.ledger.lookup(request)
            except LedgerError as exc:
                raise ServiceError(exc.code) from exc
            if cached is not None:
                return self._cached(cached)
            if self.closed:
                raise ServiceError("service_draining", 503)
            if self.pending >= 5:
                raise ServiceError("queue_full", 429)
            self.pending += 1
            owner = True
            timeout = min(
                4.0, request.remaining_timeout_ms / 1000, request.request_expires_at - time.time()
            )
            if timeout <= 0:
                self.pending -= 1
                raise ServiceError("deadline_expired", 408)
            deadline = time.monotonic() + timeout
            task = asyncio.create_task(self._dispatch(request, deadline))
            self.inflight[key] = (body_hash, task)
            task.add_done_callback(lambda finished: self._done(key, finished))
        timeout = min(
            4.0, request.remaining_timeout_ms / 1000, request.request_expires_at - time.time()
        )
        try:
            # Cancellation/HTTP timeout does not free an occupied dispatch slot.
            result = await asyncio.wait_for(asyncio.shield(task), max(0, timeout))
            return result if owner else self._cached(result)
        except TimeoutError as exc:
            raise ServiceError("stage_timeout", 408) from exc

    @staticmethod
    def _cached(result: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(result)
        result["usage"]["provider_calls"] = 0
        result["usage"]["questions"] = 0
        result["usage"]["cached"] = True
        return result

    def _done(self, key: tuple[str, int], task: asyncio.Task[dict[str, Any]]) -> None:
        self.inflight.pop(key, None)
        self.pending -= 1
        if not task.cancelled():
            task.exception()  # Observe late errors without logging request text.

    async def _dispatch(self, request: DecisionRequest, deadline: float) -> dict[str, Any]:
        async with self.slot:
            if time.monotonic() >= deadline:
                raise ServiceError("queue_deadline_expired", 408)
            if (
                request.stage_index == 3
                and min(
                    request.request_expires_at - time.time(),
                    self.ledger.remaining(request.request_id),
                )
                < 1
            ):
                raise ServiceError("insufficient_stage_three_budget", 408)
            try:
                total = self.ledger.reserve(request, self.run_id, self.max_run_calls)
            except LedgerError as exc:
                raise ServiceError(exc.code) from exc
            try:
                remaining = min(
                    deadline - time.monotonic(), self.ledger.remaining(request.request_id)
                )
                if remaining <= 0:
                    raise ServiceError("deadline_expired", 408)
                result = await self.provider.decide(request, remaining)
                if time.monotonic() >= deadline or self.ledger.remaining(request.request_id) <= 0:
                    raise ServiceError("late_result_discarded", 408)
                result.validate_candidates(request)
                if self.provider_name == "jev-api" and (
                    result.forward_passes is not None or result.model_revision is not None
                ):
                    raise ServiceError("unavailable_provenance_violation", 502)
                response = DecisionResponse(
                    provider=self.provider_name,
                    profile_id=self.profile_id,
                    config_hash=self.config_hash,
                    request_id=request.request_id,
                    stage_index=request.stage_index,
                    task=request.task,
                    context_snapshot_id=request.context_snapshot_id,
                    candidate_set_id=request.candidate_set_id,
                    selected_id=result.selected_id,
                    probabilities=result.probabilities,
                    usage={
                        "provider_calls": 1,
                        "request_provider_calls_total": total,
                        "questions": 1,
                        "request_questions_total": total,
                        "request_stages_total": total,
                        "forward_passes": None,
                        "request_forward_passes_total": None,
                        "forward_passes_source": "unavailable",
                        "input_tokens": result.input_tokens,
                    },
                    provenance={
                        "model": result.model,
                        "model_revision": result.model_revision,
                        "model_revision_source": "unavailable",
                        "adapter": "changgeun-single-dispatch-v1",
                        "observed_at": time.time(),
                    },
                ).model_dump()
                self.ledger.finish(request, response)
                return response
            except BaseException as exc:
                self.ledger.finish(request, None)
                if isinstance(exc, ServiceError):
                    raise
                raise ServiceError("provider_failed", 502) from exc

    async def drain(self) -> None:
        self.closed = True
        await asyncio.gather(*(task for _, task in self.inflight.values()), return_exceptions=True)
