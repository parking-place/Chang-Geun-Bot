import pytest

from changgeun.config import BotConfig


def test_parser_v2_requires_explicit_version_and_existing_gateway(tmp_path):
    path = tmp_path / 'bot.yaml'
    base = '''app:
  guild_allowlist: ["123"]
permissions:
  dj_role_ids: ["456"]
commands:
  allowed_text_channel_ids: ["789"]
  natural_parser_version: {version}
  parser_llm_fallback: {fallback}
voice:
  allowed_channel_ids: ["987"]
storage:
  database_path: {database}
'''
    def write(version, fallback):
        path.write_text(base.format(version=version, fallback=fallback,
                                    database=tmp_path / 'db.sqlite3'))
    write('v1', 'disabled')
    assert BotConfig.read(path).natural_parser_version == 'v1'
    write('v2', 'disabled')
    with pytest.raises(ValueError, match='natural parser'):
        BotConfig.read(path)
    path.write_text(path.read_text() + 'active_inference:\n  provider: jev-api\n')
    assert BotConfig.read(path).natural_parser_version == 'v2'
    write('unknown', 'disabled')
    with pytest.raises(ValueError, match='natural parser'):
        BotConfig.read(path)
    write('v1', 'gpt-5-nano')
    with pytest.raises(ValueError, match='LLM fallback'):
        BotConfig.read(path)
