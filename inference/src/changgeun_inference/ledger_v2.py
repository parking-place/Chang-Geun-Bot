"""Durable parser root budget alongside the unchanged API 1.2 ledger."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any

from changgeun_inference.contracts_v2 import ParseCall, RootRequest
from changgeun_inference.ledger import Ledger, LedgerError

GPT_VALIDATION_LIMIT_MICRO_USD = 1_000_000
GPT_VALIDATION_BUDGET_KEY = "gpt-5-nano-validation"


def _hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class ParserLedger:
    def __init__(self, legacy: Ledger) -> None:
        if legacy.tombstones is None:
            raise ValueError("parser v2 needs durable request ownership tombstones")
        self.legacy = legacy
        with legacy.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS v2_roots(
                 id TEXT PRIMARY KEY,binding TEXT NOT NULL,deadline REAL NOT NULL,
                 cancelled INTEGER NOT NULL DEFAULT 0 CHECK(cancelled IN(0,1)),
                 calls INTEGER NOT NULL DEFAULT 0 CHECK(calls<=8));
                CREATE TABLE IF NOT EXISTS v2_calls(
                 request_id TEXT NOT NULL,call_id TEXT NOT NULL,body_hash TEXT NOT NULL,
                 operation TEXT NOT NULL,pass_id TEXT,stage_index INTEGER,
                 attempt_no INTEGER NOT NULL,status TEXT NOT NULL,
                 remote_attempted INTEGER NOT NULL DEFAULT 0,
                 response TEXT,cost_reserved_micro_usd INTEGER NOT NULL DEFAULT 0,
                 cost_actual_micro_usd INTEGER,
                 PRIMARY KEY(request_id,call_id));
                CREATE TABLE IF NOT EXISTS v2_spend(
                 budget_key TEXT PRIMARY KEY,reserved_micro_usd INTEGER NOT NULL DEFAULT 0,
                 actual_micro_usd INTEGER NOT NULL DEFAULT 0);
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(v2_calls)")}
            if "cost_actual_micro_usd" not in columns:
                conn.execute("ALTER TABLE v2_calls ADD COLUMN cost_actual_micro_usd INTEGER")
        with sqlite3.connect(legacy.tombstones) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS v2_owners("
                         "id TEXT PRIMARY KEY,binding TEXT NOT NULL,run_id TEXT NOT NULL)")

    def _claim_owner(self, root: RootRequest, run_id: str) -> None:
        assert self.legacy.tombstones is not None
        binding = _hash(root.model_dump())
        with sqlite3.connect(self.legacy.tombstones, timeout=5) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT binding,run_id FROM v2_owners WHERE id=?",
                               (root.request_id,)).fetchone()
            if row and row != (binding, run_id):
                raise LedgerError("previous_run_request_conflict")
            conn.execute("INSERT OR IGNORE INTO v2_owners VALUES(?,?,?)",
                         (root.request_id, binding, run_id))

    def lookup(self, call: ParseCall) -> dict[str, Any] | None:
        with self.legacy.connect() as conn:
            root = conn.execute("SELECT binding,cancelled FROM v2_roots WHERE id=?",
                                (call.root.request_id,)).fetchone()
            if root is not None and root["binding"] != _hash(call.root.model_dump()):
                raise LedgerError("root_binding_conflict")
            if root is not None and root["cancelled"]:
                raise LedgerError("root_cancelled")
            row = conn.execute("SELECT body_hash,status,response FROM v2_calls "
                               "WHERE request_id=? AND call_id=?",
                               (call.root.request_id, call.call_id)).fetchone()
            if row is None:
                return None
            if row["body_hash"] != _hash(call.model_dump()):
                raise LedgerError("call_body_conflict")
            if row["status"] != "completed":
                raise LedgerError("dispatch_unknown_or_failed")
            return json.loads(row["response"])  # type: ignore[no-any-return]

    def reserve(self, call: ParseCall, *, run_id: str, max_jev_run_calls: int,
                llm_cost_micro_usd: int = 0) -> int:
        """A reservation consumes a slot even if later dispatch status becomes unknown."""
        self._claim_owner(call.root, run_id)
        conn = self.legacy.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            root = conn.execute("SELECT * FROM v2_roots WHERE id=?",
                                (call.root.request_id,)).fetchone()
            binding = _hash(call.root.model_dump())
            if root is None:
                if call.operation != "command_select" or call.pass_id != "initial":
                    raise LedgerError("first_call_required")
                conn.execute("INSERT INTO v2_roots(id,binding,deadline) VALUES(?,?,?)",
                             (call.root.request_id, binding, call.root.expires_at))
                count = 0
            else:
                if root["binding"] != binding:
                    raise LedgerError("root_binding_conflict")
                if root["cancelled"]:
                    raise LedgerError("root_cancelled")
                count = int(root["calls"])
            if call.root.expires_at <= time.time():
                raise LedgerError("deadline_expired")
            if count >= 8:
                raise LedgerError("root_budget_exhausted")
            existing = conn.execute(
                "SELECT body_hash FROM v2_calls WHERE request_id=? AND call_id=?",
                (call.root.request_id, call.call_id),
            ).fetchone()
            if existing is not None:
                raise LedgerError("call_already_reserved" if existing[0] == _hash(call.model_dump())
                                  else "call_body_conflict")
            rows = conn.execute("SELECT operation,pass_id,stage_index,status FROM v2_calls "
                                "WHERE request_id=? ORDER BY attempt_no",
                                (call.root.request_id,)).fetchall()
            if rows and rows[-1]["status"] != "completed":
                raise LedgerError("previous_call_not_completed")
            self._check_order(call, rows)
            is_jev = call.operation not in {"rewrite", "full_parse"}
            if is_jev:
                if llm_cost_micro_usd:
                    raise LedgerError("invalid_cost_reservation")
                conn.execute("INSERT OR IGNORE INTO run_budget(run_id) VALUES(?)", (run_id,))
                used = conn.execute("SELECT calls FROM run_budget WHERE run_id=?",
                                    (run_id,)).fetchone()[0]
                if used >= max_jev_run_calls:
                    raise LedgerError("run_budget_exhausted")
                conn.execute("UPDATE run_budget SET calls=calls+1 WHERE run_id=?", (run_id,))
            else:
                if not 0 < llm_cost_micro_usd <= GPT_VALIDATION_LIMIT_MICRO_USD:
                    raise LedgerError("llm_cost_reservation_required")
                conn.execute("INSERT OR IGNORE INTO v2_spend(budget_key) VALUES(?)",
                             (GPT_VALIDATION_BUDGET_KEY,))
                used = conn.execute(
                    "SELECT reserved_micro_usd FROM v2_spend WHERE budget_key=?",
                    (GPT_VALIDATION_BUDGET_KEY,),
                ).fetchone()[0]
                if used + llm_cost_micro_usd > GPT_VALIDATION_LIMIT_MICRO_USD:
                    raise LedgerError("gpt_validation_budget_exhausted")
                conn.execute("UPDATE v2_spend SET reserved_micro_usd=reserved_micro_usd+? "
                             "WHERE budget_key=?",
                             (llm_cost_micro_usd, GPT_VALIDATION_BUDGET_KEY))
            conn.execute("INSERT INTO v2_calls(request_id,call_id,body_hash,operation,pass_id,"
                         "stage_index,attempt_no,status,remote_attempted,response,"
                         "cost_reserved_micro_usd) VALUES(?,?,?,?,?,?,?,?,0,NULL,?)", (
                call.root.request_id, call.call_id, _hash(call.model_dump()),
                call.operation, call.pass_id, call.stage_index, count + 1,
                "reserved", llm_cost_micro_usd,
            ))
            conn.execute("UPDATE v2_roots SET calls=calls+1 WHERE id=?",
                         (call.root.request_id,))
            conn.commit()
            return count + 1
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _check_order(call: ParseCall, rows: list[sqlite3.Row]) -> None:
        operation = call.operation
        if operation in {"command_select", "argument_select", "context_select"}:
            stages = [row for row in rows if row["pass_id"] == call.pass_id]
            if call.stage_index != len(stages) + 1:
                raise LedgerError("stage_order_violation")
            if call.pass_id == "initial" and any(
                row["operation"] == "rewrite" for row in rows
            ):
                raise LedgerError("initial_pass_closed")
            if call.pass_id == "after_rewrite" and not any(
                row["operation"] == "rewrite" for row in rows
            ):
                raise LedgerError("rewrite_required")
            if any(row["operation"] == "full_parse" for row in rows):
                raise LedgerError("final_parse_already_used")
        elif operation == "rewrite":
            if not rows or any(row["operation"] == "rewrite" for row in rows):
                raise LedgerError("rewrite_order_violation")
            if any(row["pass_id"] == "after_rewrite" or row["operation"] == "full_parse"
                   for row in rows):
                raise LedgerError("rewrite_order_violation")
        elif operation == "full_parse":
            if not rows or any(row["operation"] == "full_parse" for row in rows):
                raise LedgerError("full_parse_order_violation")

    def mark_attempted(self, call: ParseCall) -> None:
        with self.legacy.connect() as conn:
            updated = conn.execute("UPDATE v2_calls SET remote_attempted=1,status='attempted' "
                                   "WHERE request_id=? AND call_id=? AND status='reserved'",
                                   (call.root.request_id, call.call_id))
            if updated.rowcount != 1:
                raise LedgerError("dispatch_not_reserved")

    def finish(self, call: ParseCall, response: dict[str, Any] | None) -> None:
        with self.legacy.connect() as conn:
            root = conn.execute("SELECT cancelled FROM v2_roots WHERE id=?",
                                (call.root.request_id,)).fetchone()
            if root is None or root[0]:
                raise LedgerError("root_cancelled")
            updated = conn.execute("UPDATE v2_calls SET status=?,response=? "
                                   "WHERE request_id=? AND call_id=? "
                                   "AND status IN('reserved','attempted')",
                                   ("completed" if response is not None else "failed",
                                    json.dumps(response) if response is not None else None,
                                    call.root.request_id, call.call_id))
            if updated.rowcount != 1:
                raise LedgerError("dispatch_not_reserved")

    def cancel(self, request_id: str) -> None:
        with self.legacy.connect() as conn:
            conn.execute("UPDATE v2_roots SET cancelled=1 WHERE id=?", (request_id,))

    def record_actual(self, call: ParseCall, actual_micro_usd: int | None) -> None:
        if call.operation not in {"rewrite", "full_parse"} or actual_micro_usd is None:
            return
        if actual_micro_usd < 0:
            raise LedgerError("invalid_actual_cost")
        conn = self.legacy.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT cost_reserved_micro_usd,cost_actual_micro_usd,status "
                               "FROM v2_calls WHERE request_id=? AND call_id=?",
                               (call.root.request_id, call.call_id)).fetchone()
            if row is None or row["status"] != "completed":
                raise LedgerError("cost_call_not_finished")
            if row["cost_actual_micro_usd"] is not None:
                if row["cost_actual_micro_usd"] != actual_micro_usd:
                    raise LedgerError("cost_reconciliation_conflict")
                return
            conn.execute("UPDATE v2_calls SET cost_actual_micro_usd=? "
                         "WHERE request_id=? AND call_id=?",
                         (actual_micro_usd, call.root.request_id, call.call_id))
            conn.execute("UPDATE v2_spend SET actual_micro_usd=actual_micro_usd+? "
                         "WHERE budget_key=?", (actual_micro_usd, GPT_VALIDATION_BUDGET_KEY))
            conn.commit()
            if actual_micro_usd > row["cost_reserved_micro_usd"]:
                raise LedgerError("cost_reservation_exceeded")
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def usage(self, run_id: str) -> dict[str, int]:
        with self.legacy.connect() as conn:
            jev = conn.execute("SELECT calls FROM run_budget WHERE run_id=?", (run_id,)).fetchone()
            gpt = conn.execute("SELECT reserved_micro_usd,actual_micro_usd FROM v2_spend "
                               "WHERE budget_key=?", (GPT_VALIDATION_BUDGET_KEY,)).fetchone()
            unknown = conn.execute("SELECT COUNT(*) FROM v2_calls WHERE operation IN "
                                   "('rewrite','full_parse') AND remote_attempted=1 "
                                   "AND cost_actual_micro_usd IS NULL").fetchone()[0]
        return {"jev_run_reserved": int(jev[0]) if jev else 0,
                "gpt_reserved_micro_usd": int(gpt[0]) if gpt else 0,
                "gpt_actual_micro_usd": int(gpt[1]) if gpt else 0,
                "gpt_unknown_cost_calls": int(unknown),
                "gpt_limit_micro_usd": GPT_VALIDATION_LIMIT_MICRO_USD}
