"""Read-only installed watch candidate/Discord command verification on DiscordBotLXC."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from changgeun.application.watch import WatchStore
from changgeun.config import BotConfig
from changgeun.storage.database import Database


async def probe(config: BotConfig, token_file: Path) -> dict[str, object]:
    token = token_file.read_text().split("=", 1)[1].strip()
    async with httpx.AsyncClient(
        base_url="https://discord.com/api/v10",
        headers={"Authorization": "Bot " + token},
        timeout=10,
        follow_redirects=False,
    ) as client:
        response = await client.get("/oauth2/applications/@me")
        response.raise_for_status()
        app = response.json()
        groups = []
        for guild in config.policy.guild_ids:
            response = await client.get(f"/applications/{app['id']}/guilds/{guild}/commands")
            response.raise_for_status()
            group = next(c for c in response.json() if c["name"] == "주시")
            names = sorted(c["name"] for c in group["options"])
            assert names == sorted(["추가", "제거", "목록", "켜기", "끄기", "점검"])
            assert int(group["default_member_permissions"]) & 32
            groups.append({"subcommands": names, "default_manage_guild": True})
    db = Database(config.database_path)
    store = WatchStore(db)
    states = [
        {
            "registered": len(store.channels(g)),
            "enabled": bool(store.state(g)["enabled"]),
            "seed_applied": bool(store.state(g)["seed_applied"]),
        }
        for g in config.policy.guild_ids
    ]
    with db.connect() as conn:
        unknown = conn.execute(
            "SELECT count(*) FROM audio_admissions WHERE origin='legacy_unknown'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT count(*) FROM message_requests WHERE state IN ('running','waiting')"
        ).fetchone()[0]
    status = json.loads((config.database_path.parent / "prefix-status.json").read_text())
    return {
        "status": "PASS",
        "discord_watch_groups": groups,
        "watch_states": states,
        "prefix_status": status["status"],
        "legacy_unknown_admissions": unknown,
        "pending_requests": pending,
        "provider_calls": 0,
        "human_interaction_verified": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--token-env", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                asyncio.run(probe(BotConfig.read(args.config), args.token_env)), ensure_ascii=False
            )
        )
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
