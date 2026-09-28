"""Jev multi-question adapter using the documented typed-answer wire."""

from __future__ import annotations

import json
import math
from typing import Any

from changgeun_inference.contracts_v2 import ParseCall, Question, TokenUsage
from changgeun_inference.providers import HostedProvider


def _probability(value: Any) -> float:
    if type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("invalid_provider_probability")
    return float(value)


def validate_answers(questions: dict[str, Question], answers: Any) -> dict[str, Any]:
    if not isinstance(answers, dict) or answers.keys() != questions.keys():
        raise ValueError("provider_question_mismatch")
    checked = {}
    for key, question in questions.items():
        answer = answers[key]
        if not isinstance(answer, dict) or answer.get("type") != question.type:
            raise ValueError("provider_answer_type_mismatch")
        if question.type == "noul":
            checked[key] = {"type": "noul", "noul": _probability(answer.get("noul"))}
            continue
        choice, probabilities = answer.get("choice"), answer.get("probabilities")
        if (choice not in question.criteria or not isinstance(probabilities, dict)
                or probabilities.keys() != question.criteria.keys()):
            raise ValueError("provider_choice_out_of_scope")
        scores = {name: _probability(score) for name, score in probabilities.items()}
        if abs(sum(scores.values()) - 1.0) > 0.02:
            raise ValueError("provider_probabilities_invalid")
        confidence = _probability(answer.get("confidence"))
        checked[key] = {"type": "choice", "choice": choice,
                        "probabilities": scores, "confidence": confidence}
    return checked


class HostedParserProvider(HostedProvider):
    async def parse(self, call: ParseCall, timeout: float) -> tuple[dict[str, Any],
                                                                    TokenUsage, str | None]:
        if call.operation in {"rewrite", "full_parse"}:
            raise ValueError("LLM operation sent to Jev")
        payload = {"model": self.model, "state": call.state,
                   "questions": {key: {
                       "type": question.type, "instructions": question.instructions,
                       **({"criteria": question.criteria} if question.type == "choice" else {}),
                   } for key, question in call.questions.items()}}
        client = await self._http()
        async with client.stream(
            "POST", self.endpoint, json=payload,
            headers={"Authorization": "Bearer " + self.api_key,
                     "Content-Type": "application/json"}, timeout=timeout,
        ) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > 262144:
                    raise ValueError("provider_response_too_large")
                body.extend(chunk)
        raw = json.loads(body)
        if not isinstance(raw, dict):
            raise ValueError("invalid_provider_response")
        answers = validate_answers(call.questions, raw.get("answers"))
        usage_data = raw.get("usage", {})
        if not isinstance(usage_data, dict):
            raise ValueError("invalid_provider_usage")
        usage = TokenUsage(input_tokens=usage_data.get("input_tokens"),
                           output_tokens=usage_data.get("output_tokens"))
        model = raw.get("model")
        if model is not None and not isinstance(model, str):
            raise ValueError("invalid_provider_model")
        return {"answers": answers}, usage, model
