"""Pure playback transitions; async results must carry a matching generation."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import StrEnum

from changgeun.domain.models import DomainError


class PlaybackState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    RESOLVING = "resolving"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPING = "stopping"
    RECONNECTING = "reconnecting"


@dataclass(frozen=True)
class Entry:
    id: str
    track_id: str


@dataclass
class Session:
    state: PlaybackState = PlaybackState.DISCONNECTED
    generation: int = 0
    version: int = 0
    current: Entry | None = None
    queue: list[Entry] = field(default_factory=list)
    volume: int = 30
    repeat: str = "off"
    failed_tracks: int = 0
    retry_count: int = 0
    eligible_ids: frozenset[str] | None = None

    def _change(self) -> None:
        self.generation += 1
        self.version += 1

    def _preserve_current(self) -> None:
        if self.current:
            self.queue = [e for e in self.queue if e.id != self.current.id]
            self.queue.insert(0, self.current)
            self.current = None

    def join(self) -> int:
        if self.state != PlaybackState.DISCONNECTED:
            raise DomainError("already_connected")
        self._change()
        self.state = PlaybackState.CONNECTING
        return self.generation

    def connected(self, generation: int) -> bool:
        if generation != self.generation or self.state != PlaybackState.CONNECTING:
            return False
        self.state = PlaybackState.IDLE
        self.version += 1
        return True

    def start(self) -> int:
        if self.state == PlaybackState.PAUSED:
            raise DomainError("paused_use_resume")
        if self.state not in {PlaybackState.IDLE}:
            raise DomainError("playback_not_idle")
        if not self.queue:
            raise DomainError("queue_empty")
        self._change()
        index = next(
            (
                i
                for i, entry in enumerate(self.queue)
                if self.eligible_ids is None or entry.id in self.eligible_ids
            ),
            None,
        )
        if index is None:
            raise DomainError("queue_no_approval")
        self.current = self.queue.pop(index)
        self.state = PlaybackState.RESOLVING
        self.retry_count = 0
        return self.generation

    def resolved(self, generation: int) -> bool:
        if generation != self.generation or self.state != PlaybackState.RESOLVING:
            return False
        self.state = PlaybackState.PLAYING
        self.version += 1
        return True

    def pause(self) -> None:
        if self.state != PlaybackState.PLAYING:
            raise DomainError("not_playing")
        self.state = PlaybackState.PAUSED
        self.version += 1

    def resume(self) -> None:
        if self.state != PlaybackState.PAUSED:
            raise DomainError("not_paused")
        self.state = PlaybackState.PLAYING
        self.version += 1

    def stop(self, *, leave: bool = False) -> None:
        disconnected = self.state == PlaybackState.DISCONNECTED
        self._change()
        self._preserve_current()
        self.state = PlaybackState.DISCONNECTED if leave or disconnected else PlaybackState.IDLE
        self.retry_count = 0

    def finished(self, generation: int, *, skipped: bool = False, failed: bool = False) -> bool:
        if generation != self.generation or self.state not in {
            PlaybackState.PLAYING,
            PlaybackState.PAUSED,
            PlaybackState.RESOLVING,
        }:
            return False
        if failed and self.current:
            if self.retry_count < 1:
                self.retry_count += 1
                self._change()
                self.state = PlaybackState.RESOLVING
                return True
            self.failed_tracks += 1
        elif not failed:
            self.failed_tracks = 0
        if self.current and not skipped and not failed:
            if self.repeat == "one":
                self.queue.insert(0, self.current)
            elif self.repeat == "queue":
                self.queue.append(self.current)
        self.current = None
        self._change()
        self.state = PlaybackState.IDLE
        if self.failed_tracks >= 3:
            return True
        if any(self.eligible_ids is None or e.id in self.eligible_ids for e in self.queue):
            self.start()
        return True

    def skip(self) -> None:
        if not self.current:
            raise DomainError("no_current_track")
        self.finished(self.generation, skipped=True)

    def recover_restart(self) -> None:
        self.stop(leave=True)

    def shuffle(self, seed: int) -> None:
        random.Random(seed).shuffle(self.queue)
        self.version += 1

    def auto_leave_due(
        self,
        *,
        now: float,
        empty_since: float | None,
        idle_since: float | None,
        paused_since: float | None,
        listener_count: int,
    ) -> bool:
        if self.state == PlaybackState.DISCONNECTED:
            return False
        if listener_count == 0 and empty_since is not None and now - empty_since >= 180:
            return True
        if self.state == PlaybackState.IDLE and not self.queue and idle_since is not None:
            return now - idle_since >= 300
        if self.state == PlaybackState.PAUSED and paused_since is not None:
            return now - paused_since >= 1800
        return False
