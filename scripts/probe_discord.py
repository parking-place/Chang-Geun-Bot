"""Explicit, isolated Discord voice feasibility probe; execute on DiscordBotLXC only."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import discord


class CountedAudio(discord.AudioSource):
    def __init__(self, source: discord.AudioSource) -> None:
        self.source = source
        self.frames = 0

    def read(self) -> bytes:
        data = self.source.read()
        if data:
            self.frames += 1
        return data

    def is_opus(self) -> bool:
        return self.source.is_opus()

    def cleanup(self) -> None:
        self.source.cleanup()


async def probe(config: dict[str, Any], token: str) -> dict[str, Any]:
    intents = discord.Intents.none()
    intents.guilds = True
    intents.voice_states = True
    client = discord.Client(intents=intents)
    result: dict[str, Any] = {}
    ready = asyncio.Event()

    @client.event
    async def on_ready() -> None:
        ready.set()

    runner = asyncio.create_task(client.start(token, reconnect=False))
    voice: discord.VoiceClient | None = None
    try:
        await asyncio.wait_for(ready.wait(), 30)
        guild = client.get_guild(int(config["guild_id"]))
        if guild is None:
            raise ValueError("configured guild unavailable")
        channel = guild.get_channel(int(config["voice_channel_id"]))
        if not isinstance(channel, discord.VoiceChannel):
            raise ValueError("configured channel is not ordinary voice")
        if guild.me is None:
            raise ValueError("bot member unavailable")
        permissions = channel.permissions_for(guild.me)
        if not permissions.connect or not permissions.speak:
            raise ValueError("voice permissions missing")
        voice = await channel.connect(timeout=20, reconnect=False)
        result["gateway_connected"] = True
        result["voice_connected"] = voice.is_connected()
        result["discord_py"] = discord.__version__
        result["dave_protocol_version"] = getattr(voice._connection, "dave_protocol_version", None)
        # Self-generated 2-second test tone; no external audio rights involved.
        source = CountedAudio(
            discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(
                    "sine=frequency=440:duration=2",
                    before_options="-f lavfi",
                    options="-vn -loglevel error",
                ),
                volume=0.1,
            )
        )
        finished = asyncio.Event()
        errors: list[str] = []
        loop = asyncio.get_running_loop()

        def after(error: Exception | None) -> None:
            if error:
                errors.append(type(error).__name__)
            loop.call_soon_threadsafe(finished.set)

        voice.play(source, after=after)
        await asyncio.wait_for(finished.wait(), 10)
        result["audio_frames_sent"] = source.frames
        result["audio_errors"] = errors
        result["human_audibility_verified"] = False
        if source.frames < 90 or errors:
            raise ValueError("audio transmission failed")
        return result
    finally:
        if voice:
            await voice.disconnect(force=True)
            result["voice_left"] = not voice.is_connected()
        await client.close()
        await asyncio.gather(runner, return_exceptions=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--token-env", type=Path, required=True)
    args = parser.parse_args()
    token = args.token_env.read_text().split("=", 1)[1].strip()
    config = json.loads(args.config.read_text())
    logging.disable(logging.CRITICAL)
    try:
        result = asyncio.run(probe(config, token))
        print(json.dumps({"status": "PASS", **result}))
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
