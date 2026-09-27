"""Durable, atomic reservations. Failed or unknown dispatches never refund budgets."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from changgeun_inference.contracts import DecisionRequest


class LedgerError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def fingerprint(request: DecisionRequest) -> str:
    value = json.dumps(request.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()


class Ledger:
    def __init__(self, path: Path, tombstones: Path | None = None) -> None:
        self.path = path
        self.tombstones = tombstones
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS requests(
                 id TEXT PRIMARY KEY, binding TEXT NOT NULL, deadline REAL NOT NULL,
                 calls INTEGER NOT NULL DEFAULT 0 CHECK(calls<=3));
                CREATE TABLE IF NOT EXISTS stages(
                 request_id TEXT NOT NULL, stage INTEGER NOT NULL CHECK(stage BETWEEN 1 AND 3),
                 body_hash TEXT NOT NULL, status TEXT NOT NULL, response TEXT,
                 PRIMARY KEY(request_id,stage));
                CREATE TABLE IF NOT EXISTS run_budget(
                 run_id TEXT PRIMARY KEY, calls INTEGER NOT NULL DEFAULT 0);
            """)
        path.chmod(0o600)
        if tombstones is not None:
            tombstones.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(tombstones) as registry:
                registry.execute(
                    "CREATE TABLE IF NOT EXISTS request_owners("
                    "id TEXT PRIMARY KEY,binding TEXT NOT NULL,run_id TEXT NOT NULL)"
                )
            tombstones.chmod(0o600)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @staticmethod
    def binding(request: DecisionRequest) -> str:
        value = json.dumps(
            [
                request.provider,
                request.profile_id,
                request.config_hash,
                request.context_snapshot_id,
                request.utterance,
                request.prompt_version,
                request.request_expires_at,
            ]
        )
        return hashlib.sha256(value.encode()).hexdigest()

    def _claim_owner(self, request: DecisionRequest, run_id: str) -> None:
        if self.tombstones is None:
            return
        with sqlite3.connect(self.tombstones, timeout=5) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT binding,run_id FROM request_owners WHERE id=?", (request.request_id,)
            ).fetchone()
            if row and row != (self.binding(request), run_id):
                raise LedgerError("previous_run_request_conflict")
            conn.execute(
                "INSERT OR IGNORE INTO request_owners VALUES(?,?,?)",
                (request.request_id, self.binding(request), run_id),
            )

    def lookup(self, request: DecisionRequest) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM requests WHERE id=?", (request.request_id,)
            ).fetchone()
            if row and row["binding"] != self.binding(request):
                raise LedgerError("request_binding_conflict")
            stage = conn.execute(
                "SELECT * FROM stages WHERE request_id=? AND stage=?",
                (request.request_id, request.stage_index),
            ).fetchone()
            if not stage:
                return None
            if stage["body_hash"] != fingerprint(request):
                raise LedgerError("stage_body_conflict")
            if stage["status"] != "completed":
                raise LedgerError("dispatch_unknown_or_failed")
            return json.loads(stage["response"])  # type: ignore[no-any-return]

    def reserve(self, request: DecisionRequest, run_id: str, max_run_calls: int) -> int:
        # Ownership is committed first. A crash can leave a conservative tombstone,
        # but a dispatch is never possible before the per-run reservation commits.
        self._claim_owner(request, run_id)
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM requests WHERE id=?", (request.request_id,)
            ).fetchone()
            if not row:
                if request.stage_index != 1:
                    raise LedgerError("stage_order_violation")
                deadline = min(request.request_expires_at, time.time() + 12)
                conn.execute(
                    "INSERT INTO requests(id,binding,deadline) VALUES(?,?,?)",
                    (request.request_id, self.binding(request), deadline),
                )
                calls = 0
            else:
                if row["binding"] != self.binding(request):
                    raise LedgerError("request_binding_conflict")
                deadline, calls = row["deadline"], row["calls"]
            if deadline <= time.time():
                raise LedgerError("deadline_expired")
            if calls >= 3 or request.stage_index != calls + 1:
                raise LedgerError("stage_order_or_budget_violation")
            if calls:
                previous = conn.execute(
                    "SELECT status FROM stages WHERE request_id=? AND stage=?",
                    (request.request_id, calls),
                ).fetchone()
                if not previous or previous[0] != "completed":
                    raise LedgerError("previous_stage_not_completed")
            conn.execute("INSERT OR IGNORE INTO run_budget(run_id) VALUES(?)", (run_id,))
            run_calls = conn.execute(
                "SELECT calls FROM run_budget WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            if run_calls >= max_run_calls:
                raise LedgerError("run_budget_exhausted")
            conn.execute(
                "INSERT INTO stages VALUES(?,?,?,'reserved',NULL)",
                (request.request_id, request.stage_index, fingerprint(request)),
            )
            conn.execute("UPDATE requests SET calls=calls+1 WHERE id=?", (request.request_id,))
            conn.execute("UPDATE run_budget SET calls=calls+1 WHERE run_id=?", (run_id,))
            conn.commit()
            return int(calls + 1)
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def remaining(self, request_id: str) -> float:
        with self.connect() as conn:
            row = conn.execute("SELECT deadline FROM requests WHERE id=?", (request_id,)).fetchone()
            if not row:
                raise LedgerError("unknown_request")
            return max(0.0, float(row[0]) - time.time())

    def finish(self, request: DecisionRequest, response: dict[str, Any] | None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE stages SET status=?,response=? WHERE request_id=? AND stage=?",
                (
                    "completed" if response is not None else "failed",
                    json.dumps(response) if response is not None else None,
                    request.request_id,
                    request.stage_index,
                ),
            )
