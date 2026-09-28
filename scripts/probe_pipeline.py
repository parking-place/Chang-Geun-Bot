"""Small synthetic Korean development probe on DiscordBotLXC; never held-out acceptance."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import tempfile
import time
import unicodedata
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
                "input_tokens": selected.input_tokens,
            }
        )
        return selected


async def run(
    config_path: Path,
    dataset: Path | None = None,
    output: Path | None = None,
    *,
    prompt_version: str | None = None,
    confidence: float | None = None,
    margin: float | None = None,
    dataset_sha256: str | None = None,
    heldout: bool = False,
) -> None:
    if output is not None and output.exists():
        raise ValueError("evaluation report must use a new path")
    config = BotConfig.read(config_path)
    if config.inference is None:
        raise ValueError("explicit profile required")
    decision = config.inference["decision"]
    effective_prompt = prompt_version or decision["prompt_version"]
    effective_confidence = (
        confidence if confidence is not None else decision["confidence_threshold"]
    )
    effective_margin = margin if margin is not None else decision["margin_threshold"]
    dataset_data = json.loads(dataset.read_text()) if dataset is not None else None
    if heldout:
        if dataset is None or dataset_sha256 is None:
            raise ValueError("locked held-out dataset and checksum required")
        actual_hash = hashlib.sha256(dataset.read_bytes()).hexdigest()
        if actual_hash != dataset_sha256:
            raise ValueError("held-out dataset checksum changed")
        rows_to_check = dataset_data["cases"]
        if len(rows_to_check) != 200 or {
            kind: sum(row["kind"] == kind for row in rows_to_check)
            for kind in ("clear", "ambiguous", "attack")
        } != {"clear": 120, "ambiguous": 60, "attack": 20}:
            raise ValueError("held-out composition changed")
        development = json.loads(Path("tests/nlp_eval/development.json").read_text())
        def normalize(value: str) -> str:
            return "".join(unicodedata.normalize("NFKC", value).casefold().split())

        def grams(value: str) -> set[str]:
            return {value[index : index + 3] for index in range(max(0, len(value) - 2))}

        dev_texts = {normalize(row["text"]) for row in development["cases"]}
        heldout_texts = {normalize(row["text"]) for row in rows_to_check}
        if len(heldout_texts) != 200 or any(
            normalize(row["text"]) in dev_texts for row in rows_to_check
        ):
            raise ValueError("held-out duplicate or development overlap")
        dev_grams = [grams(value) for value in dev_texts]
        if any(
            len(candidate & original) / len(candidate | original) >= 0.8
            for value in heldout_texts
            for candidate in [grams(value)]
            for original in dev_grams
        ):
            raise ValueError("held-out near-variant of development case")
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
        playlist_names = (
            dataset_data.get("playlist_names", ["새벽 노동요", "새벽 작업곡"])
            if dataset_data is not None
            else ["새벽 노동요", "새벽 작업곡"]
        )
        if not isinstance(playlist_names, list) or len(playlist_names) != 2:
            raise ValueError("exactly two fixture playlists required")
        for index, name in enumerate(playlist_names):
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
            else dataset_data["cases"]
        )
        if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
            raise ValueError("invalid development case count")
        results = []
        for row in rows:
            name, text, expected = row["id"], row["text"], row["action"]
            port = CountedPort(client)
            pipeline = Pipeline(
                db,
                config.policy,
                port,
                confidence=effective_confidence,
                margin=effective_margin,
                prompt_version=effective_prompt,
            )
            pipeline.context.remember(actor, playlists[0], playlist_names[0])
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
                index = playlist_names.index(row["playlist"])
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
                    "pipeline_metrics": pipeline.metrics.snapshot(),
                }
            )
        report = {
            "provider": client.provider,
            "profile_id": client.profile_id,
            "config_hash": client.config_hash,
            "prompt_version": effective_prompt,
            "confidence": effective_confidence,
            "margin": effective_margin,
            "scope": (
                "agent-authored synthetic held-out; no execution or Discord acceptance"
                if heldout
                else "synthetic development only; no execution; never held-out acceptance"
            ),
            "dataset_sha256": dataset_sha256 if heldout else None,
            "results": results,
            "correct": sum(row["correct"] for row in results),
            "total": len(results),
            "clear_correct": sum(row["correct"] for row in results if row["kind"] == "clear"),
            "clear_total": sum(row["kind"] == "clear" for row in results),
            "unsafe_plans": sum(
                row["actual"] is not None for row in results if row["expected"] is None
            ),
            "gateway_metrics": client.metrics.snapshot(),
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
    parser.add_argument(
        "--prompt-version",
        choices=("korean-candidates-dev-v5", "korean-candidates-compact-v1"),
    )
    parser.add_argument("--confidence", type=float)
    parser.add_argument("--margin", type=float)
    parser.add_argument("--dataset-sha256")
    parser.add_argument("--heldout", action="store_true")
    try:
        args = parser.parse_args()
        asyncio.run(run(
            args.config, args.dataset, args.output,
            prompt_version=args.prompt_version,
            confidence=args.confidence,
            margin=args.margin,
            dataset_sha256=args.dataset_sha256,
            heldout=args.heldout,
        ))
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
