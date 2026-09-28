import asyncio
import socket
from unittest.mock import AsyncMock, Mock

import pytest

from changgeun.domain.models import DomainError
from changgeun.providers.network_guard import PinnedDNS, check_url, public_address
from changgeun.providers.youtube_audio import MediaResolver, WorkerAudio


@pytest.mark.parametrize(
    "url",
    [
        "http://rr1.googlevideo.com/videoplayback",
        "https://127.0.0.1/audio",
        "https://localhost/audio",
        "https://youtube.com.evil/audio",
        "https://user:pass@rr1.googlevideo.com/audio",
        "https://rr1.googlevideo.com:8443/audio",
        "file:///etc/passwd",
        "https://rr1.googlevideo.com./audio",
    ],
)
def test_untrusted_network_never_fetches(url):
    with pytest.raises(DomainError, match="media_network_denied"):
        check_url(url, media=True)


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.1", "::1", "fe80::1", "::ffff:8.8.8.8"],
)
def test_nonpublic_and_mapped_addresses_rejected(address):
    assert not public_address(address)


def test_dns_checked_and_pinned_against_rebinding():
    dns = PinnedDNS()
    dns.original = Mock(
        side_effect=[
            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
            [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
        ]
    )
    first = dns.resolve("rr1.googlevideo.com", 443)
    assert dns.resolve("rr1.googlevideo.com", 443) == first
    assert dns.original.call_count == 1
    with pytest.raises(DomainError):
        dns.resolve("rr2.googlevideo.com", 443)


def test_mixed_dns_result_rejects_all():
    dns = PinnedDNS()
    dns.original = Mock(
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
    )
    with pytest.raises(DomainError):
        dns.resolve("www.youtube.com", 443)


@pytest.mark.asyncio
async def test_worker_failure_is_audio_error_not_successful_completion():
    reader = asyncio.StreamReader()
    reader.feed_eof()
    process = Mock(pid=None, stdout=reader, wait=AsyncMock(return_value=2))
    source = WorkerAudio(process)
    await source.pump()
    with pytest.raises(DomainError, match="youtube_stream_failed"):
        source.read()


@pytest.mark.asyncio
async def test_preparation_cancellation_reaps_process_group(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "changgeun.providers.youtube_audio.subprocess.check_output",
        lambda *args, **kwargs: "v22.0.0",
    )
    resolver = MediaResolver(tmp_path, {}, True)
    reader = asyncio.StreamReader()
    process = Mock(
        pid=123456789, stdout=reader, stdin=Mock(drain=AsyncMock()), wait=AsyncMock(return_value=-9)
    )
    create = AsyncMock(return_value=process)
    killed = []
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)

    def killed_worker(pid, signal):
        killed.append(pid)
        reader.feed_eof()

    monkeypatch.setattr("changgeun.providers.youtube_audio.os.killpg", killed_worker)
    task = asyncio.create_task(resolver.prepare("youtube", "ABCDEFGHIJK"))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert killed == [123456789]
    assert process.wait.await_count == 1
    assert resolver.pending == 0
    assert "ABCDEFGHIJK" not in str(create.call_args.args)
    assert "https://" not in str(create.call_args.args)
    assert create.call_args.kwargs["stderr"] == asyncio.subprocess.DEVNULL


@pytest.mark.asyncio
async def test_capacity_limit_does_not_spawn(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "changgeun.providers.youtube_audio.subprocess.check_output",
        lambda *args, **kwargs: "v22.0.0",
    )
    resolver = MediaResolver(tmp_path, {}, True)
    resolver.pending = 5
    create = AsyncMock()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    with pytest.raises(DomainError, match="media_capacity"):
        await resolver.prepare("youtube", "ABCDEFGHIJK")
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_first_pcm_stage_reports_safe_stream_failure(monkeypatch, tmp_path):
    resolver = MediaResolver(tmp_path, {})
    monkeypatch.setattr(resolver, "validate", lambda *_: None)
    reader = asyncio.StreamReader()
    reader.feed_data(b'{"duration":10}\n{"error":"youtube_stream_unavailable"}\n')
    reader.feed_eof()
    process = Mock(
        pid=None,
        stdout=reader,
        stdin=Mock(drain=AsyncMock()),
        wait=AsyncMock(return_value=2),
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))

    with pytest.raises(DomainError, match="youtube_stream_unavailable"):
        await resolver.prepare("youtube", "ABCDEFGHIJK")
    assert resolver.pending == 0


@pytest.mark.asyncio
async def test_first_pcm_stage_rejects_invalid_marker(monkeypatch, tmp_path):
    resolver = MediaResolver(tmp_path, {})
    monkeypatch.setattr(resolver, "validate", lambda *_: None)
    reader = asyncio.StreamReader()
    reader.feed_data(b'{"duration":10}\n{"ready":false}\n')
    reader.feed_eof()
    process = Mock(
        pid=None,
        stdout=reader,
        stdin=Mock(drain=AsyncMock()),
        wait=AsyncMock(return_value=2),
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))

    with pytest.raises(DomainError, match="youtube_invalid_response"):
        await resolver.prepare("youtube", "ABCDEFGHIJK")
    assert resolver.pending == 0


def test_unsupported_javascript_runtime_rejected_before_start(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "changgeun.providers.youtube_audio.subprocess.check_output",
        lambda *args, **kwargs: "v20.19.2",
    )
    with pytest.raises(DomainError, match="media_runtime_unsupported"):
        MediaResolver(tmp_path, {}, True)
