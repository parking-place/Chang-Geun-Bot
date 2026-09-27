"""Small synthetic Korean development probe on DiscordBotLXC; never held-out acceptance."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

from changgeun.application.executor import Executor
from changgeun.config import BotConfig
from changgeun.domain.models import Action, ActionPlan, Actor
from changgeun.nlp.client import GatewayClient
from changgeun.nlp.pipeline import Pipeline, Selection
from changgeun.storage.database import Database


class CountedPort:
    def __init__(self, client: GatewayClient) -> None:
        self.client = client
        self.provider, self.profile_id, self.config_hash = (
            client.provider,
            client.profile_id,
            client.config_hash,
        )
        self.stages = 0
        self.trace: list[dict[str, Any]] = []

    async def choose(self, payload: dict[str, Any], timeout: float) -> Selection:
        self.stages += 1
        selected = await self.client.choose(payload, timeout)
        self.trace.append(
            {
                "stage": payload["stage_index"],
                "task": payload["task"],
                "selected_id": selected.selected_id,
                "probabilities": selected.probabilities,
                "reported_calls_total": selected.calls,
            }
        )
        return selected


async def run(config_path: Path, dataset: Path | None = None, output: Path | None = None) -> None:
    if output is not None and output.exists():
        raise ValueError("evaluation report must use a new path")
    config = BotConfig.read(config_path)
    if config.inference is None:
        raise ValueError("explicit profile required")
    client = GatewayClient(config.inference)
    await client.ready()
    guild = next(iter(config.policy.guild_ids))
    actor = Actor(
        guild,
        "999999999999999999",
        config.policy.dj_role_ids,
        next(iter(config.policy.text_channel_ids)),
        next(iter(config.policy.voice_channel_ids)),
        next(iter(config.policy.voice_channel_ids)),
    )
    # Synthetic actor and isolated copied fixture. This is not actual Discord role acceptance.
    with tempfile.TemporaryDirectory(dir="/opt/changgeun-dev/runs") as temporary:
        path = Path(temporary) / "fixture.db"
        original = Path("/opt/changgeun-dev/runs/structured-baseline/bot.db")
        with (
            sqlite3.connect(f"file:{original}?mode=ro", uri=True) as source,
            sqlite3.connect(path) as target,
        ):
            source.backup(target)
        db = Database(path)
        executor = Executor(db, config.policy)
        with db.transaction() as conn:
            tracks = [
                row[0]
                for row in conn.execute(
                    "SELECT id FROM tracks WHERE guild_id=? ORDER BY external_id", (guild,)
                )
            ]
            version = conn.execute(
                "SELECT version FROM sessions WHERE guild_id=?", (guild,)
            ).fetchone()[0]
        executor.execute(
            ActionPlan(
                "probe-enqueue",
                guild,
                actor.user_id,
                Action.QUEUE_ENQUEUE,
                {"track_ids": tracks},
                {"queue": version},
            ),
            actor,
        )
        playlists = []
        for index, name in enumerate(("새벽 노동요", "새벽 작업곡")):
            identifier = executor.execute(
                ActionPlan(
                    f"probe-create-{index}",
                    guild,
                    actor.user_id,
                    Action.PLAYLIST_CREATE,
                    {"name": name},
                ),
                actor,
            )["playlist_id"]
            executor.execute(
                ActionPlan(
                    f"probe-add-{index}",
                    guild,
                    actor.user_id,
                    Action.PLAYLIST_ADD,
                    {"playlist_id": identifier, "track_ids": tracks},
                    {identifier: 0},
                ),
                actor,
            )
            playlists.append(identifier)
        with db.transaction() as conn:
            conn.execute(
                "UPDATE sessions SET current_entry_id='probe-current',"
                "current_track_id=? WHERE guild_id=?",
                (tracks[0], guild),
            )
        cases = [
            ("exact-removal", "대기열 세 번째 곡 빼줘", Action.QUEUE_REMOVE),
            ("ambiguous-playlist", "새벽 노동요 혹은 새벽 작업곡 재생해줘", None),
            (
                "context-positive-action",
                "지금 틀지 말고 아까 그 목록에 지금 곡만 넣어줘",
                Action.PLAYLIST_ADD,
            ),
        ]
        rows = (
            [
                {"id": name, "text": text, "action": expected, "kind": "development"}
                for name, text, expected in cases
            ]
            if dataset is None
            else json.loads(dataset.read_text())["cases"]
        )
        if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
            raise ValueError("invalid development case count")
        results = []
        for row in rows:
            name, text, expected = row["id"], row["text"], row["action"]
            port = CountedPort(client)
            decision = config.inference["decision"]
            pipeline = Pipeline(
                db,
                config.policy,
                port,
                confidence=decision["confidence_threshold"],
                margin=decision["margin_threshold"],
                prompt_version=decision["prompt_version"],
            )
            pipeline.context.remember(actor, playlists[0], "새벽 노동요")
            started = time.monotonic()
            error = None
            try:
                plan = await pipeline.interpret(text, actor)
            except Exception as exc:
                plan = None
                error = type(exc).__name__
            actual = plan.action if plan is not None else None
            target_correct = True
            if "video_id" in row and plan is not None:
                target_correct = plan.arguments.get("track_id") == "youtube:" + row["video_id"]
            if "playlist" in row and plan is not None:
                index = ("새벽 노동요", "새벽 작업곡").index(row["playlist"])
                target_correct = plan.arguments.get("playlist_id") == playlists[index]
            if "queue_index" in row and plan is not None:
                with db.transaction() as conn:
                    entry = conn.execute(
                        "SELECT id FROM queue_entries WHERE guild_id=? "
                        "ORDER BY position LIMIT 1 OFFSET ?",
                        (guild, row["queue_index"]),
                    ).fetchone()[0]
                target_correct = plan.arguments.get("entry_id") == entry
            results.append(
                {
                    "case": name,
                    "expected": expected,
                    "actual": actual,
                    "stages": port.stages,
                    "correct": actual == expected and target_correct and error is None,
                    "kind": row["kind"],
                    "target_correct": target_correct,
                    "error_type": error,
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                    "trace": port.trace,
                }
            )
        report = {
            "provider": client.provider,
            "profile_id": client.profile_id,
            "config_hash": client.config_hash,
            "scope": "synthetic development only; no execution; never held-out acceptance",
            "results": results,
            "correct": sum(row["correct"] for row in results),
            "total": len(results),
            "clear_correct": sum(row["correct"] for row in results if row["kind"] == "clear"),
            "clear_total": sum(row["kind"] == "clear" for row in results),
            "unsafe_plans": sum(
                row["actual"] is not None for row in results if row["expected"] is None
            ),
        }
        if output is not None:
            with output.open("x") as stream:
                stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            output.chmod(0o600)
        print(
            json.dumps(
                {key: value for key, value in report.items() if key != "results"}
                if output
                else report
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path)
    try:
        args = parser.parse_args()
        asyncio.run(run(args.config, args.dataset, args.output))
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
