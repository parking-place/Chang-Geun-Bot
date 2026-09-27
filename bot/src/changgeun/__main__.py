"""Nonroot bot entry point. Secrets come from restricted files/environment."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from dataclasses import replace
from pathlib import Path

import discord

from changgeun.config import BotConfig
from changgeun.discord_adapter.client import ChangGeunClient
from changgeun.discord_adapter.prefix import PrefixConfig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--token-env", type=Path)
    args = parser.parse_args()
    token = (
        args.token_env.read_text().split("=", 1)[1].strip()
        if args.token_env
        else os.environ.get("DISCORD_BOT_TOKEN", "")
    )
    if not token:
        parser.error("Discord bot token required")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    config = BotConfig.read(args.config)

    async def run() -> None:
        try:
            async with ChangGeunClient(config) as client:
                await client.start(token, reconnect=True)
        except discord.PrivilegedIntentsRequired:
            if not config.prefix.enabled:
                raise
            logging.getLogger(__name__).warning(
                "Message Content Intent denied; prefix disabled, structured commands recovering"
            )
            recovered = replace(config, prefix=PrefixConfig())
            async with ChangGeunClient(recovered) as client:
                await client.start(token, reconnect=True)

    asyncio.run(run())


if __name__ == "__main__":
    main()
