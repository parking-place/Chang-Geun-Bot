import pytest

from changgeun.config import BotConfig
from changgeun.discord_adapter.client import ChangGeunClient
from changgeun.domain.models import Actor, Policy
from changgeun.parser.contracts import ParseError


@pytest.fixture
def service(tmp_path):
    policy = Policy(frozenset({"1"}), frozenset({"2"}), frozenset({"3"}), frozenset({"4"}))
    bot = ChangGeunClient(BotConfig(tmp_path / "db", policy, tmp_path / "audio", {}))
    return bot.command_service, policy


def test_public_registry_comes_from_all_actual_slash_options(service):
    commands, policy = service
    assert set(commands.specs) == {f"C{n:02}" for n in range(1, 48)}
    assert {a.name for a in commands.specs["C07"].arguments} == {
        "이름", "곡수", "태그", "제외태그", "제작자", "최근제외일", "최대초", "시드"}
    assert len(commands.specs["C08"].arguments) == 7
    assert commands.specs["C11"].arguments[0].collection == "playlists"
    assert commands.specs["C11"].arguments[1].collection == "tracks"
    assert commands.specs["C12"].arguments[1].depends_on == "목록"
    actor = Actor("1", "10", frozenset(), "3")
    assert commands.specs["C01"].allowed(actor, policy)
    assert not commands.specs["C39"].allowed(actor, policy)
    assert not commands.specs["C40"].allowed(actor, policy)


def test_values_defaults_and_exclusive_modes_are_not_truthy(service):
    specs = service[0].specs
    assert specs["C28"].validate({"값": 0}) == {"값": 0}
    for bad in (True, -1, 101, "20"):
        with pytest.raises(ParseError):
            specs["C28"].validate({"값": bad})
    assert specs["C11"].validate({"목록": "list", "곡": "track"})["중복허용"] is False
    with pytest.raises(ParseError):
        specs["C23"].validate({"목록": "list", "검색어": "query"})
    with pytest.raises(ParseError):
        specs["C08"].validate({"이름": "new", "링크": "url", "교체": True})


@pytest.mark.asyncio
async def test_closed_service_uses_handler_and_checks_role_first(service):
    commands, policy = service
    called = []

    async def capture(entry, values):
        called.append(values)

    commands.handlers["C28"] = capture
    guest = Actor("1", "10", frozenset(), "3")
    with pytest.raises(ParseError):
        await commands.invoke("C28", {"값": 20}, None, guest, policy)
    assert not called
    dj = Actor("1", "10", frozenset({"2"}), "3")
    await commands.invoke("C28", {"값": 20}, None, dj, policy)
    assert called == [{"값": 20}]
