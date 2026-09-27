"""Actual metadata snapshot -> isolated confirmed import/export; no Discord mutation."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from changgeun.application.executor import Executor
from changgeun.application.transfer import parse_export
from changgeun.config import BotConfig
from changgeun.domain.models import Action, ActionPlan, Actor, DomainError
from changgeun.storage.database import Database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--snapshot-file", type=Path, required=True)
    args = parser.parse_args()
    config = BotConfig.read(args.config)
    raw = json.loads(args.snapshot_file.read_text())
    references = parse_export(json.dumps(raw["export"]).encode())
    guild = next(iter(config.policy.guild_ids))
    actor = Actor(
        guild,
        "999999999999999999",
        config.policy.dj_role_ids,
        next(iter(config.policy.text_channel_ids)),
    )
    with tempfile.TemporaryDirectory(dir="/opt/changgeun-dev/runs") as directory:
        db = Database(Path(directory) / "import.db")
        db.ensure_guild(guild)
        executor = Executor(db, config.policy)
        plan = ActionPlan(
            "actual-snapshot",
            guild,
            actor.user_id,
            Action.PLAYLIST_IMPORT,
            {
                "name": "공식 조회 시험",
                "references": references,
                "complete": raw["complete"],
                "unavailable_count": raw["unavailable_count"],
                "accept_partial": False,
                "allow_duplicates": True,
                "source_metadata": raw["source_metadata"],
            },
        )
        try:
            executor.execute(plan, actor)
        except DomainError as exc:
            if exc.code != "confirmation_required":
                raise
        else:
            raise AssertionError("confirmation was bypassed")
        result = executor.execute(plan, actor, confirmation=executor.preview(plan, actor))
        export = executor.execute(
            ActionPlan(
                "export",
                guild,
                actor.user_id,
                Action.PLAYLIST_EXPORT,
                {"playlist_id": result["playlist_id"]},
            ),
            actor,
        )
        roundtrip = parse_export(json.dumps(export).encode())
        expected = [{**reference, "annotations": {}} for reference in references]
        if roundtrip != expected:
            raise AssertionError("reference/order roundtrip mismatch")
        second = ActionPlan(
            "roundtrip",
            guild,
            actor.user_id,
            Action.PLAYLIST_IMPORT,
            {
                "name": "재가져오기 시험",
                "references": roundtrip,
                "complete": True,
                "unavailable_count": 0,
                "accept_partial": False,
                "allow_duplicates": True,
            },
        )
        restored = executor.execute(second, actor, confirmation=executor.preview(second, actor))
        with db.transaction() as conn:
            known = sum(
                json.loads(row[0]).get("duration_seconds") is not None
                for row in conn.execute("SELECT metadata_json FROM tracks")
            )
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "scope": "isolated DB; synthetic actor; real API snapshot",
                    "imported": result["count"],
                    "roundtrip_count": restored["count"],
                    "duration_known": known,
                    "confirmation_required": True,
                    "order_preserved": True,
                    "audio_fetched": False,
                    "discord_mutated": False,
                }
            )
        )


if __name__ == "__main__":
    main()
