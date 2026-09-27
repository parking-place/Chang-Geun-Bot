import httpx
import pytest

from changgeun.domain.models import DomainError
from changgeun.providers.youtube import YouTubeData, duration_seconds, playlist_id

VIDEO1, VIDEO2 = "ABCDEFGHIJK", "LMNOPQRSTUV"


def video(identifier):
    return {
        "id": identifier,
        "snippet": {"title": "참조", "channelTitle": "출처"},
        "status": {"privacyStatus": "public"},
        "contentDetails": {"duration": "PT2M3S"},
    }


def page(ids, **extra):
    return {
        "items": [{"snippet": {"resourceId": {"videoId": identifier}}} for identifier in ids],
        **extra,
    }


@pytest.mark.parametrize(
    "value,expected",
    [
        ("PT2M3S", 123),
        ("PT1H", 3600),
        ("P1DT1S", 86401),
        ("PT", None),
        ("unknown", None),
        (None, None),
        ({"duration": "PT1S"}, None),
    ],
)
def test_iso_duration(value, expected):
    assert duration_seconds(value) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://www.youtube.com/playlist?list=PLabcdefghijk",
        "https://untrusted.invalid/playlist?list=PLabcdefghijk",
        "https://www.youtube.com/playlist?list=a",
        "https://www.youtube.com/playlist?list=PLabcdefghijk&list=PLotherplaylist",
        "https://user:pass@www.youtube.com/playlist?list=PLabcdefghijk",
    ],
)
def test_import_does_not_follow_arbitrary_urls(url):
    with pytest.raises(DomainError):
        playlist_id(url)


@pytest.mark.asyncio
async def test_two_pages_preserve_order_duplicates_and_count_unavailable():
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.host == "www.googleapis.com"
        if request.url.path.endswith("playlistItems"):
            if request.url.params.get("pageToken") == "next":
                return httpx.Response(200, json=page([VIDEO1, VIDEO2]))
            return httpx.Response(200, json=page([VIDEO1], nextPageToken="next"))
        return httpx.Response(200, json={"items": [video(VIDEO1)]})

    provider = YouTubeData("synthetic-key", transport=httpx.MockTransport(handle))
    snapshot = await provider.playlist("https://www.youtube.com/playlist?list=PLabcdefghijk")
    assert snapshot.complete and snapshot.reason is None
    assert [item.external_id for item in snapshot.items] == [VIDEO1, VIDEO1]
    assert snapshot.unavailable_count == 1
    assert snapshot.items[0].duration_seconds == 123
    assert len(calls) == 4


@pytest.mark.asyncio
async def test_later_quota_failure_is_partial_and_no_retry():
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path.endswith("playlistItems"):
            if request.url.params.get("pageToken"):
                return httpx.Response(403)
            return httpx.Response(200, json=page([VIDEO1], nextPageToken="next"))
        return httpx.Response(200, json={"items": [video(VIDEO1)]})

    provider = YouTubeData("synthetic-key", transport=httpx.MockTransport(handle))
    snapshot = await provider.playlist("https://www.youtube.com/playlist?list=PLabcdefghijk")
    assert not snapshot.complete and snapshot.reason == "youtube_quota_or_access"
    assert len(snapshot.items) == 1 and len(calls) == 3


@pytest.mark.asyncio
async def test_item_limit_never_claims_complete_playlist():
    def handle(request):
        if request.url.path.endswith("playlistItems"):
            return httpx.Response(200, json=page([VIDEO1], nextPageToken="more"))
        return httpx.Response(200, json={"items": [video(VIDEO1)]})

    snapshot = await YouTubeData("synthetic-key", transport=httpx.MockTransport(handle)).playlist(
        "https://www.youtube.com/playlist?list=PLabcdefghijk", limit=1
    )
    assert not snapshot.complete and snapshot.reason == "item_limit"


@pytest.mark.parametrize("status", [307, 403, 429, 500])
@pytest.mark.asyncio
async def test_errors_redact_key_and_redirects_are_not_followed(status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "https://untrusted.invalid/"})

    with pytest.raises(DomainError) as error:
        await YouTubeData("synthetic-key", transport=httpx.MockTransport(handle)).search("창팝")
    assert "synthetic-key" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "resource,items",
    [
        ("search", [{"id": None}]),
        ("videos", [{"id": VIDEO1, "status": None}]),
        ("playlistItems", [{"snippet": {"resourceId": None}}]),
    ],
)
@pytest.mark.asyncio
async def test_malformed_nested_metadata_fails_closed(resource, items):
    def handle(request):
        return httpx.Response(200, json={"items": items})

    provider = YouTubeData("synthetic-key", transport=httpx.MockTransport(handle))
    with pytest.raises(DomainError, match="youtube_invalid_response"):
        if resource == "search":
            await provider.search("참조")
        elif resource == "videos":
            await provider.videos([VIDEO1])
        else:
            await provider.playlist("https://www.youtube.com/playlist?list=PLabcdefghijk")
