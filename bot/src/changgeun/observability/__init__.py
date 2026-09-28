"""Bounded, identifier-free counters for development diagnostics."""

from __future__ import annotations

from collections import Counter

BUCKETS_MS = (10, 25, 50, 100, 250, 500, 1000, 2000, 4000, 8000, 12000)
MEASURES = frozenset({"request", "snapshot", "decision", "gateway_ready", "gateway_choose"})
OUTCOMES = frozenset(
    {
        "selected",
        "clarified",
        "rejected",
        "failed",
        "cancelled",
        "new_call",
        "reused_call",
        "unknown_call",
    }
)


class Metrics:
    """Fixed-cardinality histograms; no text, IDs, labels, or unbounded samples."""

    def __init__(self) -> None:
        self.durations: Counter[tuple[str, int | str]] = Counter()
        self.outcomes: Counter[str] = Counter()

    def duration(self, measure: str, seconds: float) -> None:
        if measure not in MEASURES:
            raise ValueError("unsupported measure")
        milliseconds = max(0, int(seconds * 1000))
        bucket: int | str = next((edge for edge in BUCKETS_MS if milliseconds <= edge), "over")
        self.durations[measure, bucket] += 1

    def outcome(self, name: str) -> None:
        if name not in OUTCOMES:
            raise ValueError("unsupported outcome")
        self.outcomes[name] += 1

    def snapshot(self) -> dict[str, dict[str, int]]:
        return {
            "durations_ms": {
                f"{name}:{bucket}": count for (name, bucket), count in self.durations.items()
            },
            "outcomes": dict(self.outcomes),
        }
