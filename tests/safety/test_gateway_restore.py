import importlib.util
import sqlite3
import time
from pathlib import Path

import pytest

from changgeun_inference.contracts import DecisionRequest
from changgeun_inference.ledger import Ledger, LedgerError

spec = importlib.util.spec_from_file_location(
    "backup_runtime", Path(__file__).resolve().parents[2] / "scripts/backup_runtime.py"
)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_restored_unknown_reservation_preserves_budget_and_owner_without_redispatch(tmp_path):
    owner = tmp_path / "owners.db"
    ledger = Ledger(tmp_path / "ledger.db", owner)
    request = DecisionRequest(
        schema_version="1.2",
        provider="jev-api",
        profile_id="test-jev-api",
        config_hash="a" * 64,
        request_id="unknown-at-crash",
        stage_index=1,
        task="classify_intent",
        request_expires_at=time.time() + 12,
        remaining_timeout_ms=4000,
        context_snapshot_id="snapshot",
        candidate_set_id="set",
        utterance="synthetic",
        prompt_version="test",
        candidates=[{"id": "play", "description": "play"}, {"id": "clarify", "description": "ask"}],
    )
    ledger.reserve(request, "original", 20)
    binding = {"provider": "jev-api", "profile_id": "test-jev-api", "config_hash": "a" * 64}
    backup.snapshot(
        tmp_path / "snapshot",
        "gateway",
        {"ledger.db": ledger.path, "tombstones.db": owner},
        binding,
    )
    backup.restore(tmp_path / "snapshot", tmp_path / "restored", binding)
    restored = Ledger(tmp_path / "restored/ledger.db", tmp_path / "restored/tombstones.db")
    with sqlite3.connect(restored.path) as conn:
        assert conn.execute("SELECT calls FROM run_budget").fetchone()[0] == 1
        assert conn.execute("SELECT status FROM stages").fetchone()[0] == "failed"
    with pytest.raises(LedgerError):
        restored.reserve(request, "original", 20)
    with pytest.raises(LedgerError, match="previous_run_request_conflict"):
        restored.reserve(request, "new-run", 20)
