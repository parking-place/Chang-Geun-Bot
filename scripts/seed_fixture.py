"""Create isolated, self-generated audio references through the real executor on LXC."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from changgeun.application.executor import Executor
from changgeun.config import BotConfig
from changgeun.domain.models import Action, ActionPlan, Actor
from changgeun.storage.database import Database


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--discovered", type=Path, required=True)
    parser.add_argument("--token-env", type=Path, required=True)
    args = parser.parse_args()
    config = BotConfig.read(args.config)
    ids = json.loads(args.discovered.read_text())
    token = args.token_env.read_text().split("=", 1)[1].strip()
    request = urllib.request.Request(
        "https://discord.com/api/v10/guilds/" + ids["guild_id"] + "/members/" + ids["dj_member_id"],
        headers={"Authorization": "Bot " + token, "User-Agent": "ChangGeun/0.0.0"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        member = json.load(response)
    db = Database(config.database_path)
    db.ensure_guild(ids["guild_id"])
    actor = Actor(
        ids["guild_id"], ids["dj_member_id"], frozenset(member["roles"]), ids["text_channel_id"]
    )
    executor = Executor(db, config.policy)
    tracks = []
    for n in range(1, 4):
        plan = ActionPlan(
            "seed-tone-" + str(n),
            actor.guild_id,
            actor.user_id,
            Action.CATALOG_REGISTER,
            {
                "source_type": "approved_audio",
                "external_id": "tone-" + str(n),
                "title": "시험음 " + str(n),
            },
        )
        tracks.append(executor.execute(plan, actor)["track_id"])
    create = ActionPlan(
        "seed-playlist",
        actor.guild_id,
        actor.user_id,
        Action.PLAYLIST_CREATE,
        {"name": "시험음 목록"},
    )
    playlist = executor.execute(create, actor)["playlist_id"]
    add = ActionPlan(
        "seed-playlist-tracks",
        actor.guild_id,
        actor.user_id,
        Action.PLAYLIST_ADD,
        {"playlist_id": playlist, "track_ids": tracks},
        {playlist: 0},
    )
    executor.execute(add, actor)
    print("Fixture ready: three approved self-generated tones and one stored playlist.")


if __name__ == "__main__":
    main()
