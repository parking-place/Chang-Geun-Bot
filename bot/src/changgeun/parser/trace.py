"""Separate, short-lived parser observations; never an execution or budget ledger."""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from changgeun.parser.contracts import ParseError

TTL_MS = 7 * 24 * 60 * 60 * 1000
_SECRET_KEY = re.compile(r"(?i)(?:secret|token|password|api[_-]?key|authorization|cookie)")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+")
_KEY_VALUE = re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{20,})\b")
_URL = re.compile(r"https?://[^\s<>\"']+")


def _redact_string(value: str) -> str:
    def url_replace(match: re.Match[str]) -> str:
        raw = match.group()
        parts = urlsplit(raw)
        if not parts.query:
            return raw
        query = urlencode([(key, "[REDACTED]" if _SECRET_KEY.search(key) else item)
                           for key, item in parse_qsl(parts.query, keep_blank_values=True)])
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

    return _KEY_VALUE.sub("[REDACTED]", _BEARER.sub(
        "Bearer [REDACTED]", _URL.sub(url_replace, value)))


def sanitize(value: Any, *, max_chars: int = 8000) -> Any:
    """Bound and redact before queue/storage; output must never become execution evidence."""
    if isinstance(value, str):
        return _redact_string(value[:max_chars])
    if isinstance(value, dict):
        return {str(key)[:100]: "[REDACTED]" if _SECRET_KEY.search(str(key)) else
                sanitize(item, max_chars=max_chars) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item, max_chars=max_chars) for item in value[:256]]
    if value is None or type(value) in {bool, int}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    return "[UNSUPPORTED]"


def _json(value: Any) -> str:
    result = json.dumps(sanitize(value), ensure_ascii=False, allow_nan=False,
                        separators=(",", ":"))
    if len(result.encode()) > 16384:
        return json.dumps({"truncated": True, "original_bytes": len(result.encode())})
    return result


class TraceStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.is_absolute():
            raise ValueError("trace path must be absolute")
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.parent.stat().st_mode & 0o077:
            raise ValueError("trace directory must be private")
        new = not path.exists()
        if new:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        os.chmod(path, 0o600)
        with self._connect() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if not new and version != 2:
                raise ValueError("unknown trace schema; explicit migration required")
            if new:
                conn.executescript("""
                    CREATE TABLE command_requests(
                      request_id TEXT PRIMARY KEY,guild_id TEXT NOT NULL,
                      actor_id TEXT NOT NULL,channel_id TEXT NOT NULL,
                      created_at_ms INTEGER NOT NULL,expires_at_ms INTEGER NOT NULL,
                      input_redacted TEXT NOT NULL,parse_status TEXT,
                      execution_status TEXT,resolved_command TEXT,
                      executed_command TEXT,success INTEGER CHECK(success IN(0,1)));
                    CREATE TABLE model_calls(
                      call_id TEXT PRIMARY KEY,request_id TEXT NOT NULL,
                      attempt_no INTEGER NOT NULL CHECK(attempt_no BETWEEN 1 AND 8),
                      operation TEXT NOT NULL,pass_id TEXT,stage_index INTEGER,
                      remote_attempted INTEGER NOT NULL CHECK(remote_attempted IN(0,1)),
                      status TEXT NOT NULL,usage_status TEXT NOT NULL,
                      input_tokens INTEGER,output_tokens INTEGER,
                      cached_tokens INTEGER,reasoning_tokens INTEGER,
                      FOREIGN KEY(request_id) REFERENCES command_requests(request_id)
                        ON DELETE CASCADE,UNIQUE(request_id,attempt_no));
                    CREATE TABLE trace_events(
                      id INTEGER PRIMARY KEY,request_id TEXT NOT NULL,call_id TEXT,
                      name TEXT NOT NULL,data_json TEXT NOT NULL,created_at_ms INTEGER NOT NULL,
                      FOREIGN KEY(request_id) REFERENCES command_requests(request_id)
                        ON DELETE CASCADE);
                    CREATE TRIGGER immutable_trace_ttl BEFORE UPDATE ON command_requests
                      WHEN NEW.created_at_ms != OLD.created_at_ms OR
                           NEW.expires_at_ms != OLD.expires_at_ms
                      BEGIN SELECT RAISE(ABORT,'immutable trace TTL'); END;
                    CREATE INDEX trace_expiry ON command_requests(expires_at_ms);
                    PRAGMA user_version=2;
                """)
            self.purge(conn=conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=2)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def _now(now_ms: int | None = None) -> int:
        return int(time.time() * 1000) if now_ms is None else now_ms

    def begin(self, request_id: str, guild_id: str, actor_id: str, channel_id: str,
              input_text: str, *, now_ms: int | None = None) -> None:
        moment = self._now(now_ms)
        with self._connect() as conn:
            conn.execute("INSERT INTO command_requests(request_id,guild_id,actor_id,"
                         "channel_id,created_at_ms,expires_at_ms,input_redacted) "
                         "VALUES(?,?,?,?,?,?,?)", (request_id, guild_id, actor_id, channel_id,
                         moment, moment + TTL_MS, _json(input_text)))

    def event(self, request_id: str, name: str, data: dict[str, Any], *,
              call_id: str | None = None, now_ms: int | None = None) -> None:
        moment = self._now(now_ms)
        with self._connect() as conn:
            if call_id is not None and conn.execute(
                "SELECT 1 FROM model_calls WHERE request_id=? AND call_id=?",
                (request_id, call_id),
            ).fetchone() is None:
                raise ParseError("foreign_trace_call")
            if conn.execute("SELECT 1 FROM command_requests WHERE request_id=? "
                            "AND expires_at_ms>?", (request_id, moment)).fetchone() is None:
                raise ParseError("trace_expired_or_missing")
            conn.execute("INSERT INTO trace_events(request_id,call_id,name,data_json,"
                         "created_at_ms) VALUES(?,?,?,?,?)",
                         (request_id, call_id, name[:100], _json(data), moment))

    def call(self, request_id: str, call_id: str, attempt_no: int,
             operation: str, pass_id: str | None, stage_index: int | None,
             *, remote_attempted: bool, status: str, usage: dict[str, Any] | None = None,
             now_ms: int | None = None) -> None:
        moment = self._now(now_ms)
        if not 1 <= attempt_no <= 8:
            raise ParseError("invalid_attempt_no")
        if operation in {"rewrite", "full_parse"}:
            if pass_id is not None or stage_index is not None:
                raise ParseError("invalid_llm_trace_stage")
        elif pass_id not in {"initial", "after_rewrite"} or stage_index not in {1, 2, 3}:
            raise ParseError("invalid_jev_trace_stage")
        usage = usage or {}
        status_value = str(usage.get("status", "unknown"))
        if status_value not in {"reported", "partial", "unknown"}:
            raise ParseError("invalid_usage_status")
        metrics = tuple(usage.get(key) for key in (
            "input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens"))
        if any(value is not None and (type(value) is not int or value < 0)
               for value in metrics):
            raise ParseError("invalid_usage_tokens")
        if metrics[0] is not None and metrics[2] is not None and metrics[2] > metrics[0]:
            raise ParseError("cached_exceeds_input")
        if metrics[1] is not None and metrics[3] is not None and metrics[3] > metrics[1]:
            raise ParseError("reasoning_exceeds_output")
        if status_value == "reported" and (metrics[0] is None or metrics[1] is None):
            raise ParseError("incomplete_reported_usage")
        if status_value == "unknown" and any(value is not None for value in metrics):
            raise ParseError("unknown_usage_has_tokens")
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM command_requests WHERE request_id=? "
                            "AND expires_at_ms>?", (request_id, moment)).fetchone() is None:
                raise ParseError("trace_expired_or_missing")
            conn.execute("INSERT INTO model_calls VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (call_id, request_id, attempt_no, operation, pass_id, stage_index,
                          int(remote_attempted), status, status_value, *metrics))

    def outcome(self, request_id: str, *, parse_status: str,
                execution_status: str | None = None, resolved_command: str | None = None,
                executed_command: str | None = None, success: bool | None = None,
                now_ms: int | None = None) -> None:
        moment = self._now(now_ms)
        if executed_command is not None and execution_status is None:
            raise ParseError("execution_status_required")
        with self._connect() as conn:
            updated = conn.execute("UPDATE command_requests SET parse_status=?,"
                                   "execution_status=?,resolved_command=?,"
                                   "executed_command=?,success=? WHERE request_id=? "
                                   "AND expires_at_ms>?",
                                   (parse_status, execution_status, resolved_command,
                                    executed_command, success, request_id, moment))
            if updated.rowcount != 1:
                raise ParseError("trace_expired_or_missing")

    def get(self, request_id: str, *, now_ms: int | None = None) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM command_requests WHERE request_id=? "
                               "AND expires_at_ms>?", (request_id, self._now(now_ms))).fetchone()
            return dict(row) if row else None

    def calls(self, request_id: str, *, now_ms: int | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT c.* FROM model_calls c JOIN command_requests r "
                "ON r.request_id=c.request_id WHERE r.request_id=? AND r.expires_at_ms>? "
                "ORDER BY c.attempt_no", (request_id, self._now(now_ms)))]

    def usage_summary(self, guild_id: str, *, now_ms: int | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS calls,"
                               "SUM(CASE WHEN c.remote_attempted=1 AND "
                               "c.usage_status='unknown' THEN 1 ELSE 0 END) AS unknown_calls,"
                               "SUM(c.input_tokens) AS known_input_tokens,"
                               "SUM(c.output_tokens) AS known_output_tokens "
                               "FROM model_calls c JOIN command_requests r "
                               "ON r.request_id=c.request_id WHERE r.guild_id=? "
                               "AND r.expires_at_ms>?", (guild_id, self._now(now_ms))).fetchone()
            return {"calls": row["calls"], "unknown_usage_calls": row["unknown_calls"],
                    "known_input_tokens": row["known_input_tokens"],
                    "known_output_tokens": row["known_output_tokens"],
                    "usage_complete": row["unknown_calls"] == 0}

    def purge(self, *, now_ms: int | None = None,
              conn: sqlite3.Connection | None = None, batch: int = 500) -> int:
        if conn is None:
            with self._connect() as owned:
                return self.purge(now_ms=now_ms, conn=owned, batch=batch)
        ids = [row[0] for row in conn.execute(
            "SELECT request_id FROM command_requests WHERE expires_at_ms<=? "
            "LIMIT ?", (self._now(now_ms), batch))]
        conn.executemany("DELETE FROM command_requests WHERE request_id=?",
                         [(item,) for item in ids])
        return len(ids)
